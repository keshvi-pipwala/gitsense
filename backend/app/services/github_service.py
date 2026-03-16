import os
import tempfile
import subprocess
import time
from typing import List, Dict, Any, Optional, Tuple
from github import Github, GithubException, RateLimitExceededException
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_github_client() -> Github:
    return Github(settings.GITHUB_TOKEN, per_page=100)


def get_repo(owner: str, name: str):
    g = get_github_client()
    try:
        return g.get_repo(f"{owner}/{name}")
    except GithubException as e:
        logger.error(f"Failed to get repo {owner}/{name}: {e}")
        raise


def get_pr_details(owner: str, name: str, pr_number: int) -> Dict[str, Any]:
    """Fetch full PR details including files and diff."""
    g = get_github_client()
    try:
        repo = g.get_repo(f"{owner}/{name}")
        pr = repo.get_pull(pr_number)
        files = list(pr.get_files())

        diff_content = []
        for f in files:
            diff_content.append({
                "filename": f.filename,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions,
                "changes": f.changes,
                "patch": f.patch or "",
            })

        return {
            "number": pr.number,
            "title": pr.title,
            "body": pr.body or "",
            "author": pr.user.login,
            "author_avatar": pr.user.avatar_url,
            "base_branch": pr.base.ref,
            "head_branch": pr.head.ref,
            "url": pr.html_url,
            "state": pr.state,
            "created_at": pr.created_at.isoformat(),
            "updated_at": pr.updated_at.isoformat(),
            "files": diff_content,
            "total_additions": pr.additions,
            "total_deletions": pr.deletions,
            "changed_files": pr.changed_files,
            "mergeable": pr.mergeable,
            "labels": [label.name for label in pr.labels],
        }
    except RateLimitExceededException:
        logger.error("GitHub rate limit exceeded")
        raise
    except GithubException as e:
        logger.error(f"GitHub API error fetching PR #{pr_number}: {e}")
        raise


def get_open_prs(owner: str, name: str) -> List[Dict[str, Any]]:
    """Get all currently open PRs for conflict detection."""
    g = get_github_client()
    try:
        repo = g.get_repo(f"{owner}/{name}")
        prs = []
        for pr in repo.get_pulls(state="open"):
            files = [f.filename for f in pr.get_files()]
            prs.append({
                "number": pr.number,
                "title": pr.title,
                "author": pr.user.login,
                "url": pr.html_url,
                "files": files,
                "updated_at": pr.updated_at.isoformat(),
                "created_at": pr.created_at.isoformat(),
            })
        return prs
    except GithubException as e:
        logger.error(f"Failed to fetch open PRs: {e}")
        return []


def get_recent_issues(owner: str, name: str, files: List[str]) -> List[Dict[str, Any]]:
    """Fetch recent issues that mention specific files."""
    g = get_github_client()
    relevant_issues = []
    try:
        repo = g.get_repo(f"{owner}/{name}")
        for issue in repo.get_issues(state="all", sort="updated", direction="desc"):
            if issue.pull_request:
                continue  # skip PRs listed as issues
            body = (issue.body or "").lower()
            title = issue.title.lower()
            for file_path in files[:5]:  # check first 5 files only to avoid rate limit
                filename = os.path.basename(file_path).lower()
                if filename in body or filename in title:
                    relevant_issues.append({
                        "number": issue.number,
                        "title": issue.title,
                        "url": issue.html_url,
                        "state": issue.state,
                        "created_at": issue.created_at.isoformat(),
                    })
                    break
            if len(relevant_issues) >= 5:
                break
    except GithubException as e:
        logger.error(f"Failed to fetch issues: {e}")
    return relevant_issues


def post_pr_comment(owner: str, name: str, pr_number: int, comment_body: str) -> int:
    """Post a comment to a PR. Returns comment ID."""
    g = get_github_client()
    try:
        repo = g.get_repo(f"{owner}/{name}")
        pr = repo.get_pull(pr_number)
        comment = pr.create_issue_comment(comment_body)
        logger.info(f"Posted comment {comment.id} to PR #{pr_number}")
        return comment.id
    except GithubException as e:
        logger.error(f"Failed to post PR comment: {e}")
        return -1


def add_pr_labels(owner: str, name: str, pr_number: int, labels: List[str]) -> bool:
    """Add labels to a PR, creating them if they don't exist."""
    g = get_github_client()
    try:
        repo = g.get_repo(f"{owner}/{name}")

        # Ensure labels exist in the repo
        label_colors = {
            "gitsense:high-risk": "d73a4a",
            "gitsense:critical-risk": "b60205",
            "gitsense:tech-debt": "e4e669",
            "gitsense:conflict-detected": "0075ca",
            "gitsense:low-risk": "0e8a16",
            "gitsense:medium-risk": "fbca04",
        }
        for label_name in labels:
            try:
                repo.get_label(label_name)
            except GithubException:
                color = label_colors.get(label_name, "ededed")
                try:
                    repo.create_label(name=label_name, color=color)
                except GithubException:
                    pass

        pr = repo.get_pull(pr_number)
        pr.add_to_labels(*labels)
        return True
    except GithubException as e:
        logger.error(f"Failed to add labels to PR #{pr_number}: {e}")
        return False


def get_file_commit_history(owner: str, name: str, file_path: str, limit: int = 10) -> List[Dict]:
    """Get recent commit authors for a specific file."""
    g = get_github_client()
    try:
        repo = g.get_repo(f"{owner}/{name}")
        commits = []
        for commit in repo.get_commits(path=file_path)[:limit]:
            author_login = commit.author.login if commit.author else "unknown"
            commits.append({
                "sha": commit.sha[:8],
                "author": author_login,
                "message": commit.commit.message.split("\n")[0][:100],
                "date": commit.commit.author.date.isoformat(),
            })
        return commits
    except GithubException as e:
        logger.error(f"Failed to get commit history for {file_path}: {e}")
        return []


def clone_repo(github_url: str, target_dir: str) -> bool:
    """Clone a repository using git CLI."""
    try:
        token = settings.GITHUB_TOKEN
        # Inject token into URL for auth
        auth_url = github_url.replace("https://", f"https://{token}@")
        result = subprocess.run(
            ["git", "clone", "--depth=1", auth_url, target_dir],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            logger.error(f"Git clone failed: {result.stderr}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("Git clone timed out")
        return False
    except Exception as e:
        logger.error(f"Git clone error: {e}")
        return False


def walk_repo_files(repo_dir: str) -> List[Tuple[str, str]]:
    """Walk repo directory, return (relative_path, absolute_path) tuples."""
    from app.utils.chunker import should_skip_file
    import pathspec

    # Load .gitignore if present
    gitignore_path = os.path.join(repo_dir, ".gitignore")
    spec = None
    if os.path.exists(gitignore_path):
        with open(gitignore_path) as f:
            spec = pathspec.PathSpec.from_lines("gitwildmatch", f.readlines())

    files = []
    for dirpath, dirnames, filenames in os.walk(repo_dir):
        # Prune directories in-place
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d not in {"node_modules", "__pycache__", "venv", ".venv"}
        ]
        for filename in filenames:
            abs_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(abs_path, repo_dir)
            if should_skip_file(rel_path):
                continue
            if spec and spec.match_file(rel_path):
                continue
            try:
                size = os.path.getsize(abs_path)
                if size > 500_000:  # skip files > 500KB
                    continue
            except OSError:
                continue
            files.append((rel_path, abs_path))

    return files
