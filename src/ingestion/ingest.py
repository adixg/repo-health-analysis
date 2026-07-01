from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from src.database.models import Repository
from src.ingestion.github_client import GitHubClient

logger = logging.getLogger(__name__)


def parse_repo_slug(slug: str) -> tuple[str, str]:
    owner, _, repo = slug.partition("/")
    if not owner or not repo:
        raise ValueError(f"Invalid repository slug: {slug!r}. Expected owner/repo.")
    return owner, repo


def ingest_repository(session: Session, slug: str, client: GitHubClient | None = None) -> Repository:
    """Fetch repository metadata from GitHub and upsert it locally."""
    client = client or GitHubClient()
    owner, repo_name = parse_repo_slug(slug)
    payload = client.get_repository(owner, repo_name)

    repository = session.get(Repository, payload["id"])
    if repository is None:
        repository = Repository(id=payload["id"])
        session.add(repository)

    repository.full_name = payload["full_name"]
    repository.owner = owner
    repository.name = repo_name
    repository.description = payload.get("description")
    repository.stars = payload.get("stargazers_count", 0)
    repository.forks = payload.get("forks_count", 0)
    repository.open_issues = payload.get("open_issues_count", 0)
    repository.default_branch = payload.get("default_branch")
    repository.language = payload.get("language")
    repository.html_url = payload.get("html_url")
    repository.pushed_at = payload.get("pushed_at")
    repository.raw_metadata = payload

    session.commit()
    session.refresh(repository)
    logger.info("Ingested repository %s", repository.full_name)
    return repository
