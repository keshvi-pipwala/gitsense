from datetime import datetime, timezone, timedelta
from celery import shared_task
from app.core.celery_app import celery_app
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.db.models import Repository, PullRequest, Event, HealthHistory, RiskLevel

logger = get_logger(__name__)

RISK_WEIGHTS = {"LOW": 0, "MEDIUM": 10, "HIGH": 30, "CRITICAL": 60}


def compute_health_score(repo_id: int, db) -> tuple[float, dict]:
    """Compute 0-100 health score for a repository."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    recent_prs = db.query(PullRequest).filter(
        PullRequest.repo_id == repo_id,
        PullRequest.created_at >= week_ago,
        PullRequest.analysis_status == "complete",
    ).all()

    if not recent_prs:
        # No data = assume healthy
        return 85.0, {"reason": "No recent PRs analyzed"}

    # Risk score component (0-40 points deducted)
    total_risk_penalty = 0
    risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for pr in recent_prs:
        if pr.risk_level:
            level = pr.risk_level.value
            risk_counts[level] = risk_counts.get(level, 0) + 1
            total_risk_penalty += RISK_WEIGHTS.get(level, 0)
    avg_risk_penalty = min(40, total_risk_penalty / max(len(recent_prs), 1))

    # Debt score component (0-25 points deducted)
    debt_scores = [pr.debt_score for pr in recent_prs if pr.debt_score is not None]
    avg_debt = sum(debt_scores) / len(debt_scores) if debt_scores else 0
    debt_penalty = min(25, avg_debt * 0.25)

    # Stale PR component (0-20 points deducted)
    stale_prs = db.query(PullRequest).filter(
        PullRequest.repo_id == repo_id,
        PullRequest.merged_at == None,
        PullRequest.closed_at == None,
        PullRequest.last_activity_at <= now - timedelta(days=7),
    ).count()
    stale_penalty = min(20, stale_prs * 5)

    # Conflict rate component (0-15 points deducted)
    conflict_prs = sum(
        1 for pr in recent_prs
        if pr.analysis_json and pr.analysis_json.get("conflicts")
    )
    conflict_penalty = min(15, (conflict_prs / max(len(recent_prs), 1)) * 15)

    score = 100.0 - avg_risk_penalty - debt_penalty - stale_penalty - conflict_penalty
    score = round(max(0.0, min(100.0, score)), 1)

    metrics = {
        "total_prs_analyzed": len(recent_prs),
        "risk_distribution": risk_counts,
        "average_debt_score": round(avg_debt, 1),
        "stale_prs": stale_prs,
        "conflict_count": conflict_prs,
        "penalties": {
            "risk": round(avg_risk_penalty, 1),
            "debt": round(debt_penalty, 1),
            "stale": round(stale_penalty, 1),
            "conflicts": round(conflict_penalty, 1),
        },
    }
    return score, metrics


@celery_app.task(name="app.tasks.monitoring.run_health_checks")
def run_health_checks():
    """Calculate and store health scores for all active repositories."""
    db = SessionLocal()
    try:
        repos = db.query(Repository).filter(Repository.is_active == True).all()
        for repo in repos:
            try:
                score, metrics = compute_health_score(repo.id, db)
                repo.health_score = score
                db.add(HealthHistory(
                    repo_id=repo.id,
                    score=score,
                    metrics_json=metrics,
                ))
                db.commit()
                logger.info(f"Health score for {repo.owner}/{repo.name}: {score}")
            except Exception as e:
                logger.error(f"Health check failed for repo {repo.id}: {e}")
        logger.info(f"Health checks complete for {len(repos)} repos")
    finally:
        db.close()


@celery_app.task(name="app.tasks.monitoring.detect_stale_prs")
def detect_stale_prs():
    """Flag PRs open longer than STALE_PR_DAYS with no activity."""
    from app.core.config import settings
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.STALE_PR_DAYS)
        stale = db.query(PullRequest).filter(
            PullRequest.merged_at == None,
            PullRequest.closed_at == None,
            PullRequest.last_activity_at <= cutoff,
            PullRequest.is_stale == False,
        ).all()

        for pr in stale:
            pr.is_stale = True
            logger.info(f"Marked PR #{pr.github_pr_number} as stale")

        db.commit()
        logger.info(f"Detected {len(stale)} stale PRs")
    finally:
        db.close()


@celery_app.task(name="app.tasks.monitoring.process_push_event")
def process_push_event(repo_id: int, event_id: int):
    """Process a push event — update last_activity for affected PRs."""
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            return

        payload = event.payload or {}
        ref = payload.get("ref", "")
        branch = ref.replace("refs/heads/", "")

        # Find open PR for this branch and mark activity
        pr = db.query(PullRequest).filter(
            PullRequest.repo_id == repo_id,
            PullRequest.head_branch == branch,
            PullRequest.merged_at == None,
            PullRequest.closed_at == None,
        ).first()

        if pr:
            pr.last_activity_at = datetime.now(timezone.utc)
            pr.is_stale = False

        event.processing_status = "complete"
        event.processed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        logger.error(f"Push event processing failed: {e}")
    finally:
        db.close()
