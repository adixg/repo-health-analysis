from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.database.models import Issue, Repository
from src.ingestion.github_client import GitHubClient
from src.ingestion.utils import parse_github_datetime

logger = logging.getLogger(__name__)

ISSUE_BATCH_SIZE = 100


def is_pull_request(payload: dict) -> bool:
    return "pull_request" in payload


def upsert_issue(session: Session, repository: Repository, payload: dict) -> Issue:
    issue = session.get(Issue, payload["id"])
    if issue is None:
        issue = Issue(id=payload["id"])
        session.add(issue)

    issue.repository_id = repository.id
    issue.number = payload["number"]
    issue.title = payload.get("title") or ""
    issue.state = payload.get("state") or "open"
    issue.author_login = (payload.get("user") or {}).get("login")
    issue.labels = [label.get("name") for label in payload.get("labels", []) if label.get("name")]
    issue.comments_count = payload.get("comments", 0)
    issue.html_url = payload.get("html_url")
    issue.created_at = parse_github_datetime(payload.get("created_at")) or datetime.now(UTC)
    issue.closed_at = parse_github_datetime(payload.get("closed_at"))
    issue.updated_at = parse_github_datetime(payload.get("updated_at")) or issue.created_at
    issue.raw_metadata = payload
    return issue


def ingest_issues(
    session: Session,
    repository: Repository,
    client: GitHubClient | None = None,
    settings: Settings | None = None,
    *,
    incremental: bool = True,
) -> int:
    """Fetch GitHub issues (excluding PRs) and upsert them for a repository."""
    client = client or GitHubClient()
    settings = settings or get_settings()

    since: str | None = None
    if incremental and repository.issues_last_synced_at is not None:
        since = repository.issues_last_synced_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    ingested_count = 0
    for payload in client.list_issues(
        repository.owner,
        repository.name,
        state="all",
        since=since,
        max_pages=settings.issues_max_pages,
    ):
        if is_pull_request(payload):
            continue
        upsert_issue(session, repository, payload)
        ingested_count += 1
        if ingested_count % ISSUE_BATCH_SIZE == 0:
            session.commit()

    repository.issues_last_synced_at = datetime.now(UTC)
    session.commit()
    logger.info("Ingested %s issues for %s", ingested_count, repository.full_name)
    return ingested_count
