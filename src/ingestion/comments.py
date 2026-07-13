from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.database.models import IssueComment, PullRequestComment, Repository
from src.ingestion.batch import maybe_commit_batch
from src.ingestion.github_client import GitHubClient
from src.ingestion.utils import parse_github_datetime

logger = logging.getLogger(__name__)


def _trailing_number(url: str | None) -> int | None:
    """Extract the trailing integer from a GitHub resource URL.

    e.g. ``https://api.github.com/repos/psf/requests/issues/123`` -> ``123``.
    """
    if not url:
        return None
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else None


def upsert_issue_comment(
    session: Session, repository: Repository, payload: dict
) -> IssueComment:
    comment = session.get(IssueComment, payload["id"])
    if comment is None:
        comment = IssueComment(id=payload["id"])
        session.add(comment)

    comment.repository_id = repository.id
    comment.issue_number = _trailing_number(payload.get("issue_url"))
    comment.author_login = (payload.get("user") or {}).get("login")
    comment.body = payload.get("body")
    comment.html_url = payload.get("html_url")
    comment.created_at = parse_github_datetime(payload.get("created_at"))
    comment.updated_at = parse_github_datetime(payload.get("updated_at"))
    comment.raw_metadata = payload
    return comment


def upsert_pull_request_comment(
    session: Session, repository: Repository, payload: dict
) -> PullRequestComment:
    comment = session.get(PullRequestComment, payload["id"])
    if comment is None:
        comment = PullRequestComment(id=payload["id"])
        session.add(comment)

    comment.repository_id = repository.id
    comment.pull_number = _trailing_number(payload.get("pull_request_url"))
    comment.author_login = (payload.get("user") or {}).get("login")
    comment.body = payload.get("body")
    comment.html_url = payload.get("html_url")
    comment.created_at = parse_github_datetime(payload.get("created_at"))
    comment.updated_at = parse_github_datetime(payload.get("updated_at"))
    comment.raw_metadata = payload
    return comment


def ingest_issue_comments(
    session: Session,
    repository: Repository,
    client: GitHubClient | None = None,
    settings: Settings | None = None,
    *,
    incremental: bool = True,
) -> int:
    """Fetch all issue comments for a repository and upsert them."""
    client = client or GitHubClient()
    settings = settings or get_settings()
    max_pages = settings.resolved_ingestion_max_pages()

    since: str | None = None
    if incremental and repository.comments_last_synced_at is not None:
        since = repository.comments_last_synced_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    ingested_count = 0
    for payload in client.list_issue_comments(
        repository.owner,
        repository.name,
        since=since,
        max_pages=max_pages,
    ):
        upsert_issue_comment(session, repository, payload)
        ingested_count += 1
        maybe_commit_batch(session, ingested_count)

    session.commit()
    logger.info("Ingested %s issue comments for %s", ingested_count, repository.full_name)
    return ingested_count


def ingest_pull_request_comments(
    session: Session,
    repository: Repository,
    client: GitHubClient | None = None,
    settings: Settings | None = None,
    *,
    incremental: bool = True,
) -> int:
    """Fetch all pull-request review comments for a repository and upsert them."""
    client = client or GitHubClient()
    settings = settings or get_settings()
    max_pages = settings.resolved_ingestion_max_pages()

    since: str | None = None
    if incremental and repository.comments_last_synced_at is not None:
        since = repository.comments_last_synced_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    ingested_count = 0
    for payload in client.list_pull_request_comments(
        repository.owner,
        repository.name,
        since=since,
        max_pages=max_pages,
    ):
        upsert_pull_request_comment(session, repository, payload)
        ingested_count += 1
        maybe_commit_batch(session, ingested_count)

    repository.comments_last_synced_at = datetime.now(UTC)
    session.commit()
    logger.info(
        "Ingested %s pull-request comments for %s", ingested_count, repository.full_name
    )
    return ingested_count
