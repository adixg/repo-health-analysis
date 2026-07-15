from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.database.models import Contributor, Repository
from src.ingestion.batch import maybe_commit_batch
from src.ingestion.github_client import GitHubClient

logger = logging.getLogger(__name__)


def upsert_contributor(session: Session, repository: Repository, payload: dict) -> Contributor:
    login = payload.get("login")
    if not login:
        raise ValueError("Contributor payload missing login")

    contributor = session.scalar(
        select(Contributor).where(
            Contributor.repository_id == repository.id,
            Contributor.login == login,
        )
    )
    if contributor is None:
        contributor = Contributor(repository_id=repository.id, login=login)
        session.add(contributor)

    contributor.contributions = payload.get("contributions", 0)
    contributor.html_url = payload.get("html_url")
    contributor.avatar_url = payload.get("avatar_url")
    contributor.raw_metadata = payload
    return contributor


def ingest_contributors(
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

    if incremental and repository.contributors_last_synced_at is not None:
        logger.info("Skipping contributor re-fetch for %s (already synced)", repository.full_name)
        return 0

    session.execute(delete(Contributor).where(Contributor.repository_id == repository.id))
    session.commit()

    ingested_count = 0
    for payload in client.list_contributors(
        repository.owner,
        repository.name,
        max_pages=max_pages,
    ):
        if not payload.get("login"):
            continue
        upsert_contributor(session, repository, payload)
        ingested_count += 1
        maybe_commit_batch(session, ingested_count)

    repository.contributors_last_synced_at = datetime.now(UTC)
    session.commit()
    logger.info("Ingested %s contributors for %s", ingested_count, repository.full_name)
    return ingested_count
