import asyncio
from datetime import datetime, timezone
from celery import shared_task
from app.core.celery_app import celery_app
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.db.models import Repository, Event, PullRequest, RiskLevel
from app.services.github_service import (
    get_pr_details, get_open_prs, get_recent_issues,
    get_file_commit_history, post_pr_comment, add_pr_labels
)
from app.services.vector_store import semantic_search
from app.agent.pr_agent import run_claude_analysis, compute_debt_score
from app.agent.comment_formatter import format_pr_comment, get_pr_labels
from app.tasks.notifications import send_notifications

logger = get_logger(__name__)


def broadcast_step(pr_number: int, step: str, detail: str, status: str = "processing"):
    """Broadcast agent step via Redis pub/sub for WebSocket relay."""
    try:
        import redis
        from app.core.config import settings
        import json
        r = redis.from_url(settings.REDIS_URL)
        r.publish("agent_steps", json.dumps({
            "pr_number": pr_number,
            "step": step,
            "detail": detail,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
    except Exception as e:
        logger.warning(f"Failed to broadcast step: {e}")


@celery_app.task(bind=True, name="app.tasks.pr_analysis.analyze_pull_request", max_retries=2)
def analyze_pull_request(self, repo_id: int, pr_number: int, event_id: int):
    """Full 7-step PR intelligence pipeline."""
    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            logger.error(f"Repo {repo_id} not found")
            return

        event = db.query(Event).filter(Event.id == event_id).first()
        if event:
            event.processing_status = "processing"
            db.commit()

        broadcast_step(pr_number, "started", f"Starting analysis for PR #{pr_number}", "processing")

        # ── STEP 1: Fetch PR diff ─────────────────────────────────────
        broadcast_step(pr_number, "diff_fetch", f"Fetching diff for PR #{pr_number}...", "processing")
        pr_data = get_pr_details(repo.owner, repo.name, pr_number)
        changed_files = [f["filename"] for f in pr_data["files"]]
        broadcast_step(pr_number, "diff_fetch", f"Got diff: {pr_data['changed_files']} files, +{pr_data['total_additions']}/-{pr_data['total_deletions']} lines", "done")

        # ── STEP 2: Blast radius detection ───────────────────────────
        broadcast_step(pr_number, "blast_radius", "Running semantic blast radius detection...", "processing")
        blast_radius_results = []
        for file_info in pr_data["files"][:10]:
            patch = file_info.get("patch", "")
            if patch:
                results = semantic_search(repo_id, patch[:500], n_results=5)
                blast_radius_results.extend(results)
        # Deduplicate by file_path
        seen = set()
        unique_blast = []
        for r in blast_radius_results:
            fp = r.get("metadata", {}).get("file_path", "")
            if fp and fp not in seen and fp not in changed_files:
                seen.add(fp)
                unique_blast.append(r)
        blast_radius_count = len(unique_blast)
        broadcast_step(pr_number, "blast_radius", f"Blast radius: {blast_radius_count} potentially affected modules", "done")

        # ── STEP 3: Historical intelligence ──────────────────────────
        broadcast_step(pr_number, "history", "Querying historical PR patterns...", "processing")
        historical_prs = db.query(PullRequest).filter(
            PullRequest.repo_id == repo_id,
            PullRequest.id != None,
        ).order_by(PullRequest.created_at.desc()).limit(50).all()

        # Filter to PRs that touched same files
        relevant_history = []
        for hpr in historical_prs:
            analysis = hpr.analysis_json or {}
            affected = set(analysis.get("affected_modules", []))
            if any(cf in " ".join(affected) for cf in changed_files[:5]):
                relevant_history.append({
                    "github_pr_number": hpr.github_pr_number,
                    "title": hpr.title,
                    "author": hpr.author,
                    "risk_level": hpr.risk_level.value if hpr.risk_level else None,
                    "debt_score": hpr.debt_score,
                })

        related_issues = get_recent_issues(repo.owner, repo.name, changed_files[:5])
        broadcast_step(pr_number, "history", f"Found {len(relevant_history)} related PRs, {len(related_issues)} related issues", "done")

        # ── STEP 4: Technical debt scoring ───────────────────────────
        broadcast_step(pr_number, "debt_scan", "Scanning for technical debt...", "processing")
        debt_score = compute_debt_score(pr_data["files"])
        broadcast_step(pr_number, "debt_scan", f"Technical debt score: {debt_score}/100", "done")

        # ── STEP 5: Conflict detection ────────────────────────────────
        broadcast_step(pr_number, "conflicts", "Checking for merge conflicts with open PRs...", "processing")
        open_prs = get_open_prs(repo.owner, repo.name)
        broadcast_step(pr_number, "conflicts", f"Checked {len(open_prs)} open PRs for conflicts", "done")

        # ── STEP 6: File experts ──────────────────────────────────────
        file_experts = {}
        for fp in changed_files[:5]:
            commits = get_file_commit_history(repo.owner, repo.name, fp, limit=5)
            if commits:
                file_experts[fp] = commits

        # ── STEP 6: Claude analysis ───────────────────────────────────
        broadcast_step(pr_number, "claude_analysis", "Sending to Claude for deep analysis...", "processing")
        analysis = run_claude_analysis(
            pr_data=pr_data,
            blast_radius=unique_blast,
            historical_prs=relevant_history,
            related_issues=related_issues,
            file_experts=file_experts,
            open_prs=open_prs,
        )
        risk_level = analysis.get("risk_level", "MEDIUM")
        broadcast_step(pr_number, "claude_analysis", f"Analysis complete — Risk: {risk_level}", "done")

        # ── Store PR in DB ────────────────────────────────────────────
        existing_pr = db.query(PullRequest).filter(
            PullRequest.repo_id == repo_id,
            PullRequest.github_pr_number == pr_number,
        ).first()

        if existing_pr:
            pr_db = existing_pr
        else:
            pr_db = PullRequest(repo_id=repo_id, github_pr_number=pr_number)
            db.add(pr_db)

        pr_db.title = pr_data["title"]
        pr_db.author = pr_data["author"]
        pr_db.author_avatar_url = pr_data.get("author_avatar", "")
        pr_db.github_pr_url = pr_data["url"]
        pr_db.base_branch = pr_data["base_branch"]
        pr_db.head_branch = pr_data["head_branch"]
        pr_db.risk_level = RiskLevel(risk_level)
        pr_db.debt_score = debt_score
        pr_db.blast_radius_count = blast_radius_count
        pr_db.files_changed = pr_data["changed_files"]
        pr_db.lines_added = pr_data["total_additions"]
        pr_db.lines_removed = pr_data["total_deletions"]
        pr_db.analysis_json = analysis
        pr_db.analysis_status = "complete"
        pr_db.last_activity_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(pr_db)

        # ── STEP 7: Post to GitHub ────────────────────────────────────
        broadcast_step(pr_number, "github_post", "Posting analysis comment to GitHub...", "processing")
        comment_body = format_pr_comment(analysis, pr_data, debt_score, pr_db.id)
        comment_id = post_pr_comment(repo.owner, repo.name, pr_number, comment_body)
        pr_db.github_comment_id = comment_id

        labels = get_pr_labels(risk_level, debt_score, bool(analysis.get("conflicts")))
        if labels:
            add_pr_labels(repo.owner, repo.name, pr_number, labels)
            pr_db.labels_applied = labels

        db.commit()
        broadcast_step(pr_number, "github_post", f"Posted comment #{comment_id} ✓", "done")

        # ── Notifications ─────────────────────────────────────────────
        notify_levels = ["HIGH", "CRITICAL"]
        if risk_level in notify_levels:
            send_notifications.apply_async(args=[pr_db.id], queue="notifications")
            broadcast_step(pr_number, "notifications", f"Sending {risk_level} risk alerts...", "processing")

        # Update event
        if event:
            event.processing_status = "complete"
            event.processed_at = datetime.now(timezone.utc)
            db.commit()

        broadcast_step(pr_number, "complete", f"PR #{pr_number} fully analyzed ✓", "complete")
        logger.info(f"PR #{pr_number} analysis complete. Risk: {risk_level}, Debt: {debt_score}")

        return {
            "pr_id": pr_db.id,
            "pr_number": pr_number,
            "risk_level": risk_level,
            "debt_score": debt_score,
            "blast_radius": blast_radius_count,
        }

    except Exception as e:
        logger.error(f"PR analysis failed for #{pr_number}: {e}", exc_info=True)
        if event:
            try:
                event.processing_status = "failed"
                event.error_message = str(e)
                db.commit()
            except Exception:
                pass
        broadcast_step(pr_number, "error", f"Analysis failed: {str(e)[:100]}", "error")
        raise self.retry(exc=e, countdown=30)
    finally:
        db.close()
