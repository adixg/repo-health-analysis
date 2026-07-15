from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from statistics import median

from sqlalchemy import func, select
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


@dataclass
class LabelCount:
    label: str
    count: int
    share: float


@dataclass
class LabelDistribution:
    full_name: str
    total_issues: int
    labeled_issues: int
    unlabeled_issues: int
    top_labels: list[LabelCount]


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
    repo_filter = Issue.repository_id == repository.id

    total = session.scalar(select(func.count()).select_from(Issue).where(repo_filter)) or 0
    open_count = (
        session.scalar(
            select(func.count()).select_from(Issue).where(repo_filter, Issue.state == "open")
        )
        or 0
    )
    closed_count = (
        session.scalar(
            select(func.count()).select_from(Issue).where(repo_filter, Issue.state == "closed")
        )
        or 0
    )
    stale_open = (
        session.scalar(
            select(func.count())
            .select_from(Issue)
            .where(
                repo_filter,
                Issue.state == "open",
                Issue.created_at <= cutoff,
            )
        )
        or 0
    )

    closure_rate = (closed_count / total) if total else 0.0
    stale_pct = (stale_open / open_count) if open_count else 0.0

    closed_rows = session.execute(
        select(Issue.created_at, Issue.closed_at).where(
            repo_filter,
            Issue.state == "closed",
            Issue.closed_at.isnot(None),
        )
    ).all()
    resolution_days = [
        (closed_at - created_at).total_seconds() / 86400
        for created_at, closed_at in closed_rows
        if created_at is not None and closed_at is not None
    ]
    median_resolution = median(resolution_days) if resolution_days else None

    return IssueMetrics(
        full_name=repository.full_name,
        total_issues=total,
        open_issues=open_count,
        closed_issues=closed_count,
        closure_rate=round(closure_rate, 3),
        stale_open_issues=stale_open,
        stale_issue_pct=round(stale_pct, 3),
        median_resolution_days=round(median_resolution, 1) if median_resolution is not None else None,
    )


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


def calculate_all_issue_metrics(session: Session) -> list[dict]:
    repositories = session.scalars(select(Repository).order_by(Repository.full_name)).all()
    return [asdict(calculate_issue_metrics(session, repo)) for repo in repositories]


def calculate_label_distribution(
    session: Session,
    repository: Repository,
    *,
    limit: int = 15,
) -> LabelDistribution:
    """Count how often each issue label appears for a repository."""
    label_rows = session.scalars(
        select(Issue.labels).where(Issue.repository_id == repository.id)
    ).all()

    label_counts: Counter[str] = Counter()
    labeled_issues = 0
    for labels in label_rows:
        normalized = labels or []
        if not normalized:
            continue
        labeled_issues += 1
        label_counts.update(normalized)

    total_issues = len(label_rows)
    total_assignments = sum(label_counts.values())
    top_labels = [
        LabelCount(
            label=label,
            count=count,
            share=round(count / total_assignments, 3) if total_assignments else 0.0,
        )
        for label, count in label_counts.most_common(limit)
    ]

    return LabelDistribution(
        full_name=repository.full_name,
        total_issues=total_issues,
        labeled_issues=labeled_issues,
        unlabeled_issues=total_issues - labeled_issues,
        top_labels=top_labels,
    )


def label_distribution_as_rows(distribution: LabelDistribution) -> list[dict]:
    return [
        {
            "label": label.label,
            "count": label.count,
            "share": label.share,
        }
        for label in distribution.top_labels
    ]
