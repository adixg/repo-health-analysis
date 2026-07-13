from __future__ import annotations

import base64
import binascii
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.database.models import Document, Repository
from src.ingestion.github_client import GitHubClient

logger = logging.getLogger(__name__)


def _decode_content(payload: dict) -> str | None:
    """Decode a GitHub contents-API payload (base64) into UTF-8 text."""
    content = payload.get("content")
    if content is None:
        return None
    if payload.get("encoding") == "base64":
        try:
            raw = base64.b64decode(content)
        except (binascii.Error, ValueError):
            logger.warning("Failed to base64-decode document content")
            return None
        return raw.decode("utf-8", errors="replace")
    return content


def upsert_document(session: Session, repository: Repository, payload: dict) -> Document:
    path = payload.get("path") or "README.md"
    document = session.scalar(
        select(Document).where(
            Document.repository_id == repository.id,
            Document.path == path,
        )
    )
    if document is None:
        document = Document(repository_id=repository.id, path=path)
        session.add(document)

    document.content = _decode_content(payload)
    document.sha = payload.get("sha")
    document.html_url = payload.get("html_url")
    return document


def ingest_documentation(
    session: Session,
    repository: Repository,
    client: GitHubClient | None = None,
    settings: Settings | None = None,
) -> int:
    """Fetch the repository README (and future docs) and store the decoded text."""
    client = client or GitHubClient()
    settings = settings or get_settings()

    ingested_count = 0
    readme = client.get_readme(repository.owner, repository.name)
    if readme is not None:
        upsert_document(session, repository, readme)
        ingested_count += 1

    repository.documents_last_synced_at = datetime.now(UTC)
    session.commit()
    logger.info("Ingested %s documents for %s", ingested_count, repository.full_name)
    return ingested_count
