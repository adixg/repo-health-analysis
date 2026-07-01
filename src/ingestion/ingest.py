from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.database.models import Repository
from src.ingestion.commits import ingest_commits
from src.ingestion.contributors import ingest_contributors
from src.ingestion.github_client import GitHubClient
from src.ingestion.issues import ingest_issues
from src.ingestion.pull_requests import ingest_pull_requests
from src.ingestion.releases import ingest_releases

logger = logging.getLogger(__name__)


@dataclass
class IngestionCounts:
    issues: int = 0
    pull_requests: int = 0
    commits: int = 0
    contributors: int = 0
    releases: int = 0


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


def ingest_repository_data(
    session: Session,
    repository: Repository,
    client: GitHubClient | None = None,
    settings: Settings | None = None,
) -> IngestionCounts:
    """Ingest all supported GitHub data types for a repository."""
    client = client or GitHubClient()
    settings = settings or get_settings()

    return IngestionCounts(
        issues=ingest_issues(session, repository, client=client, settings=settings),
        pull_requests=ingest_pull_requests(session, repository, client=client, settings=settings),
        commits=ingest_commits(session, repository, client=client, settings=settings),
        contributors=ingest_contributors(session, repository, client=client, settings=settings),
        releases=ingest_releases(session, repository, client=client, settings=settings),
    )
