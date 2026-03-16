from typing import Dict, Any
from app.core.config import settings

RISK_EMOJI = {
    "LOW": "🟢",
    "MEDIUM": "🟡",
    "HIGH": "🔴",
    "CRITICAL": "🚨",
}

RISK_BADGE = {
    "LOW": "![LOW](https://img.shields.io/badge/risk-LOW-brightgreen)",
    "MEDIUM": "![MEDIUM](https://img.shields.io/badge/risk-MEDIUM-yellow)",
    "HIGH": "![HIGH](https://img.shields.io/badge/risk-HIGH-red)",
    "CRITICAL": "![CRITICAL](https://img.shields.io/badge/risk-CRITICAL-darkred)",
}


def format_pr_comment(analysis: Dict[str, Any], pr_data: Dict[str, Any], debt_score: float, pr_db_id: int) -> str:
    risk = analysis.get("risk_level", "MEDIUM")
    emoji = RISK_EMOJI.get(risk, "⚪")
    badge = RISK_BADGE.get(risk, "")
    dashboard_url = f"{settings.FRONTEND_URL}/pr/{pr_db_id}"

    lines = [
        f"## {emoji} GitSense Analysis {badge}",
        "",
        f"> **{analysis.get('summary', 'Analysis complete.')}**",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Risk Level | **{risk}** |",
        f"| Technical Debt Score | **{debt_score}/100** |",
        f"| Blast Radius | **{len(analysis.get('affected_modules', []))} modules** |",
        f"| Files Changed | **{pr_data.get('changed_files', 0)}** |",
        f"| Lines | **+{pr_data.get('total_additions', 0)} / -{pr_data.get('total_deletions', 0)}** |",
        "",
    ]

    # Breaking changes
    breaking = analysis.get("breaking_changes", [])
    if breaking:
        lines += [
            "<details>",
            "<summary>⚠️ Breaking Changes</summary>",
            "",
        ]
        for bc in breaking:
            lines.append(f"- {bc}")
        lines += ["", "</details>", ""]

    # Affected modules
    affected = analysis.get("affected_modules", [])
    if affected:
        lines += [
            "<details>",
            "<summary>💥 Blast Radius — Potentially Affected Modules</summary>",
            "",
        ]
        for mod in affected:
            lines.append(f"- `{mod}`")
        lines += ["", "</details>", ""]

    # Recommendations
    recs = analysis.get("recommendations", [])
    if recs:
        lines += ["### 🎯 Recommendations", ""]
        for i, rec in enumerate(recs, 1):
            lines.append(f"{i}. {rec}")
        lines.append("")

    # Conflicts
    conflicts = analysis.get("conflicts", [])
    if conflicts:
        lines += [
            "<details>",
            "<summary>⚡ Merge Conflict Risks</summary>",
            "",
        ]
        for c in conflicts:
            lines.append(f"- {c}")
        lines += ["", "</details>", ""]

    # Technical Debt
    debt_issues = analysis.get("debt_issues", [])
    if debt_issues:
        lines += [
            "<details>",
            "<summary>🏚️ Technical Debt Detected</summary>",
            "",
        ]
        for d in debt_issues:
            lines.append(f"- {d}")
        lines += ["", "</details>", ""]

    # Reviewer suggestions
    reviewers = analysis.get("reviewer_suggestions", [])
    if reviewers:
        lines += [
            "<details>",
            "<summary>👥 Suggested Reviewers</summary>",
            "",
        ]
        for r in reviewers:
            lines.append(f"- {r}")
        lines += ["", "</details>", ""]

    # Similar past PRs
    past_prs = analysis.get("similar_past_prs", [])
    if past_prs:
        lines += [
            "<details>",
            "<summary>📚 Similar Past PRs</summary>",
            "",
        ]
        for p in past_prs:
            lines.append(f"- {p}")
        lines += ["", "</details>", ""]

    # Risk reasoning
    risk_reasoning = analysis.get("risk_reasoning", "")
    if risk_reasoning:
        lines += [
            "<details>",
            "<summary>🧠 Risk Assessment Reasoning</summary>",
            "",
            f"_{risk_reasoning}_",
            "",
            "</details>",
            "",
        ]

    lines += [
        "---",
        f"*🤖 Analyzed by [GitSense]({dashboard_url}) — Autonomous Codebase Intelligence*",
    ]

    return "\n".join(lines)


def get_pr_labels(risk_level: str, debt_score: float, has_conflicts: bool) -> list:
    labels = []
    label_map = {
        "LOW": "gitsense:low-risk",
        "MEDIUM": "gitsense:medium-risk",
        "HIGH": "gitsense:high-risk",
        "CRITICAL": "gitsense:critical-risk",
    }
    if risk_level in label_map:
        labels.append(label_map[risk_level])
    if debt_score >= 40:
        labels.append("gitsense:tech-debt")
    if has_conflicts:
        labels.append("gitsense:conflict-detected")
    return labels
