from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.database.models import Issue, Repository


@dataclass
class RepositoryHealthSummary:
    full_name: str
    stars: int
    forks: int
    open_issues: int
    language: str | None
    default_branch: str | None


@dataclass
class IssueMetrics:
    full_name: str
    total_issues: int
    open_issues: int
    closed_issues: int
    closure_rate: float
    stale_open_issues: int
    stale_issue_pct: float
    median_resolution_days: float | None


def summarize_repository(repository: Repository) -> RepositoryHealthSummary:
    return RepositoryHealthSummary(
        full_name=repository.full_name,
        stars=repository.stars,
        forks=repository.forks,
        open_issues=repository.open_issues,
        language=repository.language,
        default_branch=repository.default_branch,
    )


def summarize_all_repositories(session: Session) -> list[dict]:
    repositories = session.scalars(select(Repository).order_by(Repository.full_name)).all()
    return [asdict(summarize_repository(repo)) for repo in repositories]


def _resolution_days(issue: Issue) -> float | None:
    if issue.closed_at is None:
        return None
    delta = issue.closed_at - issue.created_at
    return delta.total_seconds() / 86400


def calculate_issue_metrics(
    session: Session,
    repository: Repository,
    *,
    stale_days: int | None = None,
) -> IssueMetrics:
    stale_days = stale_days or get_settings().stale_issue_days
    cutoff = datetime.now(UTC) - timedelta(days=stale_days)

    issues = session.scalars(
        select(Issue).where(Issue.repository_id == repository.id)
    ).all()
    open_issues = [issue for issue in issues if issue.state == "open"]
    closed_issues = [issue for issue in issues if issue.state == "closed"]
    stale_open = [issue for issue in open_issues if issue.created_at <= cutoff]

    total = len(issues)
    closed_count = len(closed_issues)
    closure_rate = (closed_count / total) if total else 0.0
    stale_pct = (len(stale_open) / len(open_issues)) if open_issues else 0.0

    resolution_days = [
        days for issue in closed_issues if (days := _resolution_days(issue)) is not None
    ]
    median_resolution = median(resolution_days) if resolution_days else None

    return IssueMetrics(
        full_name=repository.full_name,
        total_issues=total,
        open_issues=len(open_issues),
        closed_issues=closed_count,
        closure_rate=round(closure_rate, 3),
        stale_open_issues=len(stale_open),
        stale_issue_pct=round(stale_pct, 3),
        median_resolution_days=round(median_resolution, 1) if median_resolution is not None else None,
    )


def calculate_all_issue_metrics(session: Session) -> list[dict]:
    repositories = session.scalars(select(Repository).order_by(Repository.full_name)).all()
    return [asdict(calculate_issue_metrics(session, repo)) for repo in repositories]


def top_stale_issues(session: Session, repository_id: int, limit: int = 10) -> list[dict]:
    cutoff = datetime.now(UTC) - timedelta(days=get_settings().stale_issue_days)
    issues = session.scalars(
        select(Issue)
        .where(
            Issue.repository_id == repository_id,
            Issue.state == "open",
            Issue.created_at <= cutoff,
        )
        .order_by(Issue.created_at.asc())
        .limit(limit)
    ).all()
    return [
        {
            "number": issue.number,
            "title": issue.title,
            "created_at": issue.created_at.isoformat(),
            "labels": issue.labels or [],
            "url": issue.html_url,
        }
        for issue in issues
    ]
