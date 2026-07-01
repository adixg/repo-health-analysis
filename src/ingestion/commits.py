from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.database.models import Commit, Repository
from src.ingestion.batch import maybe_commit_batch
from src.ingestion.github_client import GitHubClient
from src.ingestion.utils import parse_github_datetime

logger = logging.getLogger(__name__)


def upsert_commit(session: Session, repository: Repository, payload: dict) -> Commit:
    commit = session.get(Commit, payload["sha"])
    if commit is None:
        commit = Commit(sha=payload["sha"])
        session.add(commit)

    commit_data = payload.get("commit") or {}
    author = payload.get("author") or commit_data.get("author") or {}
    commit.repository_id = repository.id
    commit.message = (commit_data.get("message") or "")[:4000]
    commit.author_login = author.get("login")
    commit.author_name = author.get("name") or (commit_data.get("author") or {}).get("name")
    commit.committed_at = (
        parse_github_datetime((commit_data.get("author") or {}).get("date"))
        or parse_github_datetime((commit_data.get("committer") or {}).get("date"))
        or datetime.now(UTC)
    )
    commit.html_url = payload.get("html_url")
    commit.raw_metadata = payload
    return commit


def ingest_commits(
    session: Session,
    repository: Repository,
    client: GitHubClient | None = None,
    settings: Settings | None = None,
    *,
    incremental: bool = True,
) -> int:
    client = client or GitHubClient()
    settings = settings or get_settings()
    max_pages = settings.resolved_ingestion_max_pages()

    since: str | None = None
    if incremental and repository.commits_last_synced_at is not None:
        since = repository.commits_last_synced_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    ingested_count = 0
    for payload in client.list_commits(
        repository.owner,
        repository.name,
        since=since,
        max_pages=max_pages,
    ):
        upsert_commit(session, repository, payload)
        ingested_count += 1
        maybe_commit_batch(session, ingested_count)

    repository.commits_last_synced_at = datetime.now(UTC)
    session.commit()
    logger.info("Ingested %s commits for %s", ingested_count, repository.full_name)
    return ingested_count
