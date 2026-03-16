import hashlib
import hmac
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.logging import get_logger
from app.core.websocket import manager
from app.db import get_db, Repository, Event
from app.tasks.pr_analysis import analyze_pull_request
from app.tasks.monitoring import process_push_event

router = APIRouter()
logger = get_logger(__name__)


def verify_github_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not signature_header:
        return False
    if not settings.GITHUB_WEBHOOK_SECRET:
        logger.warning("GITHUB_WEBHOOK_SECRET not set — skipping signature verification")
        return True
    hash_object = hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)


def find_or_create_repo(db: Session, payload: dict, event_type: str) -> Repository | None:
    """Extract repo info from payload and find/create DB record."""
    repo_data = payload.get("repository", {})
    if not repo_data:
        return None

    github_url = repo_data.get("html_url") or repo_data.get("url", "")
    owner = repo_data.get("owner", {}).get("login", "")
    name = repo_data.get("name", "")

    if not github_url or not owner or not name:
        return None

    repo = db.query(Repository).filter(Repository.github_url == github_url).first()
    if not repo:
        repo = Repository(
            github_url=github_url,
            name=name,
            owner=owner,
            default_branch=repo_data.get("default_branch", "main"),
            is_active=True,
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)
        logger.info(f"Auto-registered repository: {owner}/{name}")

    return repo


@router.post("/webhook/github")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive and process GitHub webhook events."""
    payload_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    event_type = request.headers.get("X-GitHub-Event", "unknown")
    delivery_id = request.headers.get("X-GitHub-Delivery", "")

    # Verify signature
    if not verify_github_signature(payload_bytes, signature):
        logger.warning(f"Invalid webhook signature for delivery {delivery_id}")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    logger.info(f"Received webhook: event={event_type} delivery={delivery_id}")

    # Broadcast to WebSocket clients
    await manager.broadcast_event(
        event_type=event_type,
        data={"delivery_id": delivery_id, "action": payload.get("action", "")},
        status="received",
    )

    # Handle ping event
    if event_type == "ping":
        return {"message": "pong", "zen": payload.get("zen", "")}

    # Find or create repository
    repo = find_or_create_repo(db, payload, event_type)

    # Check for duplicate delivery
    if delivery_id:
        existing = db.query(Event).filter(Event.github_delivery_id == delivery_id).first()
        if existing:
            logger.info(f"Duplicate delivery {delivery_id} — skipping")
            return {"status": "duplicate", "delivery_id": delivery_id}

    # Store event in DB
    event = Event(
        repo_id=repo.id if repo else None,
        event_type=event_type,
        github_delivery_id=delivery_id or None,
        payload=payload,
        raw_headers=dict(request.headers),
        processing_status="pending",
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # Route to appropriate Celery task
    task_id = None
    if event_type == "pull_request" and repo:
        action = payload.get("action", "")
        if action in ("opened", "synchronize", "reopened"):
            pr_number = payload.get("number")
            task = analyze_pull_request.apply_async(
                args=[repo.id, pr_number, event.id],
                queue="analysis",
            )
            task_id = task.id
            logger.info(f"Queued PR analysis task {task_id} for PR #{pr_number}")
            await manager.broadcast_agent_step(
                pr_number=pr_number,
                step="webhook_received",
                detail=f"PR #{pr_number} '{payload.get('pull_request', {}).get('title', '')}' queued for analysis",
                status="queued",
            )

    elif event_type == "push" and repo:
        task = process_push_event.apply_async(
            args=[repo.id, event.id],
            queue="monitoring",
        )
        task_id = task.id

    # Update event with task id
    if task_id:
        event.celery_task_id = task_id
        event.processing_status = "queued"
        db.commit()

    return {
        "status": "accepted",
        "event_id": event.id,
        "event_type": event_type,
        "task_id": task_id,
    }
