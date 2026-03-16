import json
import re
from typing import Dict, Any, List, Optional
import google.generativeai as genai
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are GitSense, an elite autonomous code intelligence agent operating as a Principal Engineer at a FAANG-level company.

Your role: Analyze pull requests with the depth and rigor of a senior engineer who has seen thousands of production incidents. You think in systems — you don't just read code, you understand blast radius, failure modes, historical patterns, and team dynamics.

Your analysis framework:
1. BLAST RADIUS THINKING: What breaks if this change has a bug? What's the second and third-order effect?
2. HISTORICAL PATTERN RECOGNITION: Have we seen this pattern before? Was it safe last time?
3. RISK CALIBRATION: Be precise, not paranoid. Not every change is HIGH risk. Calibrate honestly.
4. ACTIONABLE RECOMMENDATIONS: Give specific, implementable suggestions — not generic advice.
5. REVIEWER SELECTION: Who has the most context on this code? Who should be the reviewer?

Output format: You MUST respond with valid JSON only. No preamble, no markdown fences, just the JSON object."""

ANALYSIS_PROMPT_TEMPLATE = """Analyze this pull request as a Principal Engineer. Think step by step through each dimension.

## PR METADATA
- Title: {pr_title}
- Author: {pr_author}
- Base branch: {base_branch}
- Files changed: {files_changed}
- Lines added: {lines_added} | Lines removed: {lines_removed}

## CHANGED FILES & DIFF
{diff_summary}

## BLAST RADIUS MAP
{blast_radius}

## HISTORICAL CONTEXT
Past PRs: {historical_prs}
Related issues: {related_issues}
File experts: {file_experts}

## TECHNICAL DEBT SCAN
{debt_analysis}

## CONFLICT DETECTION
{conflicts}

Respond with ONLY this JSON structure, no other text:
{{
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "summary": "2-3 sentence summary",
  "breaking_changes": [],
  "affected_modules": [],
  "debt_issues": [],
  "conflicts": [],
  "recommendations": [],
  "similar_past_prs": [],
  "reviewer_suggestions": [],
  "risk_reasoning": "why this risk level"
}}"""


def build_diff_summary(files: List[Dict]) -> str:
    lines = []
    for f in files[:20]:
        lines.append(f"### {f['filename']} ({f['status']}) +{f['additions']} -{f['deletions']}")
        if f.get("patch"):
            patch_lines = f["patch"].splitlines()[:60]
            lines.append("```diff")
            lines.extend(patch_lines)
            lines.append("```")
    return "\n".join(lines)


def build_blast_radius_text(search_results: List[Dict]) -> str:
    if not search_results:
        return "No semantically similar code found (isolated change)."
    lines = []
    seen_files = set()
    for r in search_results[:15]:
        meta = r.get("metadata", {})
        fp = meta.get("file_path", "unknown")
        if fp in seen_files:
            continue
        seen_files.add(fp)
        similarity = r.get("similarity", 0)
        chunk_type = meta.get("chunk_type", "block")
        name = meta.get("name", "")
        lines.append(f"- {fp} :: {chunk_type} `{name}` (similarity: {similarity:.2f})")
    return "\n".join(lines)


def analyze_technical_debt(files: List[Dict]) -> str:
    issues = []
    for f in files:
        patch = f.get("patch", "")
        if not patch:
            continue
        added_lines = [l[1:] for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")]

        func_line_count = 0
        in_func = False
        func_name = ""
        for line in added_lines:
            stripped = line.strip()
            if re.match(r"^(def |async def |function |const \w+ = )", stripped):
                if in_func and func_line_count > 50:
                    issues.append(f"{f['filename']}: function `{func_name}` may be too long ({func_line_count}+ lines)")
                in_func = True
                func_name = stripped[:60]
                func_line_count = 0
            elif in_func:
                func_line_count += 1

        magic_numbers = re.findall(r"(?<!\w)(?<!\.)\b(\d{2,})\b(?!\w)(?!\.)", " ".join(added_lines))
        magic_numbers = [n for n in magic_numbers if n not in {"100", "200", "404", "500", "1000"}]
        if len(magic_numbers) > 3:
            issues.append(f"{f['filename']}: {len(magic_numbers)} magic numbers detected")

        urls = re.findall(r'https?://[^\s\'"]+', " ".join(added_lines))
        if urls:
            issues.append(f"{f['filename']}: Hardcoded URLs: {', '.join(urls[:2])}")

        debt_markers = [l for l in added_lines if re.search(r"\b(TODO|FIXME|HACK|XXX|TEMP)\b", l, re.I)]
        if debt_markers:
            issues.append(f"{f['filename']}: {len(debt_markers)} debt marker(s)")

        deep_nesting = [l for l in added_lines if len(l) - len(l.lstrip()) > 24]
        if len(deep_nesting) > 5:
            issues.append(f"{f['filename']}: Deep nesting detected")

        if f["filename"].endswith(".py"):
            func_matches = [l for l in added_lines if re.match(r"\s*def ", l)]
            docstring_count = sum(1 for l in added_lines if '"""' in l or "'''" in l)
            if len(func_matches) > docstring_count:
                issues.append(f"{f['filename']}: {len(func_matches) - docstring_count} function(s) may lack docstrings")

    if not issues:
        return "No significant technical debt patterns detected."
    return "\n".join(f"- {i}" for i in issues)


def compute_debt_score(files: List[Dict]) -> float:
    debt_text = analyze_technical_debt(files)
    issues = [l for l in debt_text.splitlines() if l.startswith("-")]
    score = min(100.0, len(issues) * 15.0)
    total_lines = sum(f.get("additions", 0) for f in files)
    if total_lines > 500:
        score = min(100.0, score + 20.0)
    elif total_lines > 200:
        score = min(100.0, score + 10.0)
    return round(score, 1)


def run_claude_analysis(
    pr_data: Dict,
    blast_radius: List[Dict],
    historical_prs: List[Dict],
    related_issues: List[Dict],
    file_experts: Dict[str, List[Dict]],
    open_prs: List[Dict],
) -> Dict[str, Any]:
    """Run the full Gemini multi-step analysis."""
    genai.configure(api_key=settings.GOOGLE_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT,
        generation_config=genai.GenerationConfig(
            temperature=0.2,
            max_output_tokens=2000,
        ),
    )

    expert_lines = []
    for filepath, commits in list(file_experts.items())[:5]:
        authors = list({c["author"] for c in commits[:3]})
        expert_lines.append(f"- {filepath}: {', '.join(authors)}")

    changed_files = {f["filename"] for f in pr_data["files"]}
    conflicting = []
    for opr in open_prs:
        if opr["number"] == pr_data["number"]:
            continue
        overlap = changed_files & set(opr["files"])
        if overlap:
            conflicting.append(
                f"PR #{opr['number']} '{opr['title']}' by @{opr['author']} — "
                f"overlaps on: {', '.join(list(overlap)[:3])}"
            )

    hist_lines = []
    for hpr in historical_prs[:5]:
        rl = hpr.get("risk_level") or "UNKNOWN"
        hist_lines.append(
            f"- PR #{hpr['github_pr_number']} '{hpr['title']}' by @{hpr['author']} "
            f"[risk: {rl}, debt: {hpr.get('debt_score', 'N/A')}]"
        )

    prompt = ANALYSIS_PROMPT_TEMPLATE.format(
        pr_title=pr_data["title"],
        pr_author=pr_data["author"],
        base_branch=pr_data["base_branch"],
        files_changed=pr_data["changed_files"],
        lines_added=pr_data["total_additions"],
        lines_removed=pr_data["total_deletions"],
        diff_summary=build_diff_summary(pr_data["files"]),
        blast_radius=build_blast_radius_text(blast_radius),
        historical_prs="\n".join(hist_lines) if hist_lines else "None.",
        related_issues="\n".join(
            f"- Issue #{i['number']}: {i['title']} [{i['state']}]" for i in related_issues
        ) if related_issues else "None.",
        file_experts="\n".join(expert_lines) if expert_lines else "None.",
        debt_analysis=analyze_technical_debt(pr_data["files"]),
        conflicts="\n".join(f"- {c}" for c in conflicting) if conflicting else "No conflicts.",
    )

    logger.info(f"Sending PR analysis request to Gemini for PR #{pr_data['number']}")

    response = model.generate_content(prompt)
    response_text = response.text.strip()

    # Strip markdown fences if present
    response_text = re.sub(r"^```(?:json)?\n?", "", response_text)
    response_text = re.sub(r"\n?```$", "", response_text)

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned invalid JSON: {e}\nRaw: {response_text[:500]}")
        result = {
            "risk_level": "MEDIUM",
            "summary": "Analysis parsing failed — manual review recommended.",
            "breaking_changes": [],
            "affected_modules": [],
            "debt_issues": [],
            "conflicts": conflicting,
            "recommendations": ["Manual review required due to analysis parsing error"],
            "similar_past_prs": [],
            "reviewer_suggestions": [],
            "risk_reasoning": "Could not parse automated analysis.",
        }

    required_keys = [
        "risk_level", "summary", "breaking_changes", "affected_modules",
        "debt_issues", "conflicts", "recommendations", "similar_past_prs",
        "reviewer_suggestions",
    ]
    for k in required_keys:
        if k not in result:
            result[k] = [] if k not in ("risk_level", "summary", "risk_reasoning") else ""

    if result.get("risk_level") not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        result["risk_level"] = "MEDIUM"

    return result
