import os
import tempfile
import shutil
from datetime import datetime, timezone
from celery import shared_task
from app.core.celery_app import celery_app
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.db.models import Repository
from app.services.github_service import clone_repo, walk_repo_files
from app.services.vector_store import index_chunks, delete_file_chunks, get_collection_stats
from app.utils.chunker import chunk_file

logger = get_logger(__name__)


@celery_app.task(bind=True, name="app.tasks.indexing.index_repository", max_retries=3)
def index_repository(self, repo_id: int):
    """Full index of a repository — clone, chunk, embed, store."""
    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            logger.error(f"Repository {repo_id} not found")
            return {"error": "Repository not found"}

        repo.indexing_status = "indexing"
        db.commit()

        with tempfile.TemporaryDirectory() as tmpdir:
            clone_dir = os.path.join(tmpdir, "repo")
            logger.info(f"Cloning {repo.github_url} to {clone_dir}")

            if not clone_repo(repo.github_url, clone_dir):
                repo.indexing_status = "failed"
                db.commit()
                return {"error": "Clone failed"}

            files = walk_repo_files(clone_dir)
            logger.info(f"Found {len(files)} files to index in {repo.owner}/{repo.name}")

            total_chunks = 0
            for rel_path, abs_path in files:
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    chunks = chunk_file(content, rel_path)
                    if chunks:
                        indexed = index_chunks(repo_id, chunks)
                        total_chunks += indexed
                except Exception as e:
                    logger.warning(f"Failed to index {rel_path}: {e}")
                    continue

            stats = get_collection_stats(repo_id)
            repo.indexed_at = datetime.now(timezone.utc)
            repo.indexing_status = "complete"
            repo.total_files_indexed = len(files)
            db.commit()

            logger.info(f"Indexed {total_chunks} chunks for repo {repo_id}")
            return {
                "repo_id": repo_id,
                "files_indexed": len(files),
                "chunks_indexed": total_chunks,
                "status": "complete",
            }

    except Exception as e:
        logger.error(f"Indexing failed for repo {repo_id}: {e}", exc_info=True)
        try:
            repo.indexing_status = "failed"
            db.commit()
        except Exception:
            pass
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@celery_app.task(name="app.tasks.indexing.incremental_reindex_all")
def incremental_reindex_all():
    """Re-index changed files for all active repositories."""
    db = SessionLocal()
    try:
        repos = db.query(Repository).filter(
            Repository.is_active == True,
            Repository.indexing_status == "complete"
        ).all()
        for repo in repos:
            incremental_reindex.apply_async(args=[repo.id], queue="indexing")
        logger.info(f"Triggered incremental reindex for {len(repos)} repos")
    finally:
        db.close()


@celery_app.task(bind=True, name="app.tasks.indexing.incremental_reindex", max_retries=2)
def incremental_reindex(self, repo_id: int):
    """Re-index only files changed since last index."""
    from github import Github
    from app.core.config import settings

    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo or not repo.indexed_at:
            return

        g = Github(settings.GITHUB_TOKEN)
        gh_repo = g.get_repo(f"{repo.owner}/{repo.name}")
        since = repo.indexed_at

        changed_files = set()
        for commit in gh_repo.get_commits(since=since):
            for f in commit.files:
                changed_files.add(f.filename)

        if not changed_files:
            logger.info(f"No changes since last index for repo {repo_id}")
            return

        logger.info(f"Re-indexing {len(changed_files)} changed files for repo {repo_id}")

        with tempfile.TemporaryDirectory() as tmpdir:
            clone_dir = os.path.join(tmpdir, "repo")
            if not clone_repo(repo.github_url, clone_dir):
                return

            for rel_path in changed_files:
                abs_path = os.path.join(clone_dir, rel_path)
                if not os.path.exists(abs_path):
                    delete_file_chunks(repo_id, rel_path)
                    continue
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    delete_file_chunks(repo_id, rel_path)
                    chunks = chunk_file(content, rel_path)
                    if chunks:
                        index_chunks(repo_id, chunks)
                except Exception as e:
                    logger.warning(f"Failed to reindex {rel_path}: {e}")

        repo.indexed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Incremental reindex complete for repo {repo_id}")

    except Exception as e:
        logger.error(f"Incremental reindex failed for repo {repo_id}: {e}")
        raise self.retry(exc=e, countdown=120)
    finally:
        db.close()
