from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from pydantic import BaseModel, HttpUrl
from app.db import get_db, Repository, Event, PullRequest, HealthHistory, Notification, RiskLevel
from app.tasks.indexing import index_repository
from app.tasks.monitoring import compute_health_score
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class RepositoryCreate(BaseModel):
    github_url: str
    default_branch: str = "main"


class RepositoryResponse(BaseModel):
    id: int
    github_url: str
    name: str
    owner: str
    default_branch: str
    indexed_at: Optional[datetime]
    health_score: Optional[float]
    is_active: bool
    indexing_status: str
    total_files_indexed: int
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class PRResponse(BaseModel):
    id: int
    repo_id: int
    github_pr_number: int
    title: str
    author: str
    author_avatar_url: Optional[str]
    github_pr_url: str
    base_branch: Optional[str]
    head_branch: Optional[str]
    risk_level: Optional[str]
    debt_score: Optional[float]
    blast_radius_count: int
    files_changed: int
    lines_added: int
    lines_removed: int
    analysis_json: Optional[dict]
    analysis_status: str
    created_at: Optional[datetime]
    merged_at: Optional[datetime]
    is_stale: bool
    labels_applied: Optional[list]

    class Config:
        from_attributes = True


class EventResponse(BaseModel):
    id: int
    repo_id: Optional[int]
    event_type: str
    github_delivery_id: Optional[str]
    received_at: Optional[datetime]
    processed_at: Optional[datetime]
    processing_status: str
    celery_task_id: Optional[str]
    error_message: Optional[str]

    class Config:
        from_attributes = True


# ── Repository endpoints ───────────────────────────────────────────────────────

@router.post("/repositories", response_model=RepositoryResponse, status_code=201)
def create_repository(data: RepositoryCreate, db: Session = Depends(get_db)):
    """Add a new repository to monitor."""
    url = data.github_url.rstrip("/")
    existing = db.query(Repository).filter(Repository.github_url == url).first()
    if existing:
        raise HTTPException(status_code=409, detail="Repository already exists")

    # Parse owner/name from URL
    parts = url.rstrip("/").split("/")
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL")
    name = parts[-1]
    owner = parts[-2]

    repo = Repository(
        github_url=url,
        name=name,
        owner=owner,
        default_branch=data.default_branch,
        is_active=True,
        indexing_status="pending",
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    logger.info(f"Created repository {owner}/{name}")
    return repo


@router.get("/repositories", response_model=List[RepositoryResponse])
def list_repositories(
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    q = db.query(Repository)
    if active_only:
        q = q.filter(Repository.is_active == True)
    return q.order_by(desc(Repository.created_at)).all()


@router.get("/repositories/{repo_id}", response_model=RepositoryResponse)
def get_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo


@router.post("/repositories/{repo_id}/index")
def trigger_index(repo_id: int, db: Session = Depends(get_db)):
    """Trigger a manual re-index of the repository."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.indexing_status == "indexing":
        raise HTTPException(status_code=409, detail="Indexing already in progress")

    repo.indexing_status = "pending"
    db.commit()

    task = index_repository.apply_async(args=[repo_id], queue="indexing")
    return {"message": "Indexing started", "task_id": task.id, "repo_id": repo_id}


@router.get("/repositories/{repo_id}/status")
def get_indexing_status(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return {
        "repo_id": repo_id,
        "indexing_status": repo.indexing_status,
        "total_files_indexed": repo.total_files_indexed,
        "indexed_at": repo.indexed_at,
        "health_score": repo.health_score,
    }


@router.delete("/repositories/{repo_id}")
def delete_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    from app.services.vector_store import delete_repo_collection
    delete_repo_collection(repo_id)
    db.delete(repo)
    db.commit()
    return {"message": "Repository deleted"}


# ── Pull Request endpoints ─────────────────────────────────────────────────────

@router.get("/prs", response_model=List[PRResponse])
def list_prs(
    repo_id: Optional[int] = None,
    risk_level: Optional[str] = None,
    author: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(PullRequest)
    if repo_id:
        q = q.filter(PullRequest.repo_id == repo_id)
    if risk_level and risk_level.upper() in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        q = q.filter(PullRequest.risk_level == RiskLevel(risk_level.upper()))
    if author:
        q = q.filter(PullRequest.author.ilike(f"%{author}%"))
    return q.order_by(desc(PullRequest.created_at)).offset(offset).limit(limit).all()


@router.get("/prs/{pr_id}", response_model=PRResponse)
def get_pr(pr_id: int, db: Session = Depends(get_db)):
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found")
    return pr


# ── Health history ─────────────────────────────────────────────────────────────

@router.get("/health-history/{repo_id}")
def get_health_history(
    repo_id: int,
    days: int = Query(default=30, le=365),
    db: Session = Depends(get_db),
):
    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(days=days)
    history = db.query(HealthHistory).filter(
        HealthHistory.repo_id == repo_id,
        HealthHistory.calculated_at >= since,
    ).order_by(HealthHistory.calculated_at).all()

    return [
        {
            "score": h.score,
            "calculated_at": h.calculated_at,
            "metrics": h.metrics_json,
        }
        for h in history
    ]


# ── Events ─────────────────────────────────────────────────────────────────────

@router.get("/events", response_model=List[EventResponse])
def list_events(
    repo_id: Optional[int] = None,
    event_type: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Event)
    if repo_id:
        q = q.filter(Event.repo_id == repo_id)
    if event_type:
        q = q.filter(Event.event_type == event_type)
    return q.order_by(desc(Event.received_at)).limit(limit).all()


# ── Stats ──────────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(repo_id: Optional[int] = None, db: Session = Depends(get_db)):
    from datetime import timedelta
    q = db.query(PullRequest)
    if repo_id:
        q = q.filter(PullRequest.repo_id == repo_id)

    total_prs = q.count()
    high_risk = q.filter(PullRequest.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL])).count()
    conflicts = q.filter(
        PullRequest.analysis_json.isnot(None)
    ).all()
    conflict_count = sum(
        1 for pr in conflicts
        if pr.analysis_json and pr.analysis_json.get("conflicts")
    )
    debt_scores = [pr.debt_score for pr in q.all() if pr.debt_score is not None]
    avg_debt = round(sum(debt_scores) / len(debt_scores), 1) if debt_scores else 0

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent = q.filter(PullRequest.created_at >= week_ago).count()

    repos = db.query(Repository).filter(Repository.is_active == True).all()
    avg_health = round(
        sum(r.health_score for r in repos if r.health_score) / max(len(repos), 1), 1
    ) if repos else 0

    return {
        "total_prs_analyzed": total_prs,
        "high_risk_caught": high_risk,
        "conflicts_detected": conflict_count,
        "avg_debt_score": avg_debt,
        "prs_this_week": recent,
        "repositories_monitored": len(repos),
        "avg_health_score": avg_health,
    }
