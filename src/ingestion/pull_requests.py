from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.database.models import PullRequest, Repository
from src.ingestion.batch import maybe_commit_batch
from src.ingestion.github_client import GitHubClient
from src.ingestion.utils import parse_github_datetime

logger = logging.getLogger(__name__)


def upsert_pull_request(session: Session, repository: Repository, payload: dict) -> PullRequest:
    pull_request = session.get(PullRequest, payload["id"])
    if pull_request is None:
        pull_request = PullRequest(id=payload["id"])
        session.add(pull_request)

    merged_at = parse_github_datetime(payload.get("merged_at"))
    pull_request.repository_id = repository.id
    pull_request.number = payload["number"]
    pull_request.title = payload.get("title") or ""
    pull_request.state = payload.get("state") or "open"
    pull_request.author_login = (payload.get("user") or {}).get("login")
    pull_request.merged = merged_at is not None
    pull_request.labels = [
        label.get("name") for label in payload.get("labels", []) if label.get("name")
    ]
    pull_request.comments_count = payload.get("comments", 0)
    pull_request.html_url = payload.get("html_url")
    pull_request.created_at = parse_github_datetime(payload.get("created_at")) or datetime.now(UTC)
    pull_request.closed_at = parse_github_datetime(payload.get("closed_at"))
    pull_request.merged_at = merged_at
    pull_request.updated_at = parse_github_datetime(payload.get("updated_at")) or pull_request.created_at
    pull_request.raw_metadata = payload
    return pull_request


def ingest_pull_requests(
    session: Session,
    repository: Repository,
    client: GitHubClient | None = None,
    settings: Settings | None = None,
) -> int:
    client = client or GitHubClient()
    settings = settings or get_settings()
    max_pages = settings.resolved_ingestion_max_pages()

    ingested_count = 0
    for payload in client.list_pull_requests(
        repository.owner,
        repository.name,
        state="all",
        max_pages=max_pages,
    ):
        upsert_pull_request(session, repository, payload)
        ingested_count += 1
        maybe_commit_batch(session, ingested_count)

    repository.pulls_last_synced_at = datetime.now(UTC)
    session.commit()
    logger.info("Ingested %s pull requests for %s", ingested_count, repository.full_name)
    return ingested_count
