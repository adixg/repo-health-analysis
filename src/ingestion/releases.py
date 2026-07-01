from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.database.models import Release, Repository
from src.ingestion.batch import maybe_commit_batch
from src.ingestion.github_client import GitHubClient
from src.ingestion.utils import parse_github_datetime

logger = logging.getLogger(__name__)


def upsert_release(session: Session, repository: Repository, payload: dict) -> Release:
    release = session.scalar(
        select(Release).where(
            Release.repository_id == repository.id,
            Release.github_id == payload["id"],
        )
    )
    if release is None:
        release = Release(github_id=payload["id"])
        session.add(release)

    release.repository_id = repository.id
    release.tag_name = payload.get("tag_name") or ""
    release.name = payload.get("name")
    release.draft = bool(payload.get("draft"))
    release.prerelease = bool(payload.get("prerelease"))
    release.html_url = payload.get("html_url")
    release.published_at = parse_github_datetime(payload.get("published_at"))
    release.raw_metadata = payload
    return release


def ingest_releases(
    session: Session,
    repository: Repository,
    client: GitHubClient | None = None,
    settings: Settings | None = None,
) -> int:
    client = client or GitHubClient()
    settings = settings or get_settings()
    max_pages = settings.resolved_ingestion_max_pages()

    ingested_count = 0
    for payload in client.list_releases(
        repository.owner,
        repository.name,
        max_pages=max_pages,
    ):
        upsert_release(session, repository, payload)
        ingested_count += 1
        maybe_commit_batch(session, ingested_count)

    repository.releases_last_synced_at = datetime.now(UTC)
    session.commit()
    logger.info("Ingested %s releases for %s", ingested_count, repository.full_name)
    return ingested_count
