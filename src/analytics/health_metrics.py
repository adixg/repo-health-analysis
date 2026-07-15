from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from statistics import median

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.database.models import Commit, Contributor, PullRequest, Release, Repository


@dataclass
class PullRequestMetrics:
    full_name: str
    total_prs: int
    open_prs: int
    merged_prs: int
    merge_rate: float
    median_merge_days: float | None


@dataclass
class CommitActivityMetrics:
    full_name: str
    total_commits: int
    commits_last_6_months: int
    commits_prior_6_months: int
    activity_change_pct: float | None


@dataclass
class ContributorMetrics:
    full_name: str
    contributor_count: int
    top_contributor: str | None
    top_contributor_share: float
    top_3_contributor_share: float


@dataclass
class ReleaseMetrics:
    full_name: str
    total_releases: int
    releases_last_12_months: int
    median_days_between_releases: float | None
    days_since_last_release: float | None


@dataclass
class RepositoryComparisonMetrics:
    full_name: str
    stars: int
    issue_closure_rate: float
    pr_merge_rate: float
    stale_open_issues: int
    commits_last_6_months: int
    contributor_count: int
    top_contributor_share: float
    releases_last_12_months: int


def _merge_days(pull_request: PullRequest) -> float | None:
    if pull_request.merged_at is None:
        return None
    delta = pull_request.merged_at - pull_request.created_at
    return delta.total_seconds() / 86400


def calculate_pull_request_metrics(session: Session, repository: Repository) -> PullRequestMetrics:
    repo_filter = PullRequest.repository_id == repository.id
    total = session.scalar(select(func.count()).select_from(PullRequest).where(repo_filter)) or 0
    open_prs = (
        session.scalar(
            select(func.count())
            .select_from(PullRequest)
            .where(repo_filter, PullRequest.state == "open")
        )
        or 0
    )
    merged_prs = (
        session.scalar(
            select(func.count())
            .select_from(PullRequest)
            .where(repo_filter, PullRequest.merged.is_(True))
        )
        or 0
    )
    merge_rate = (merged_prs / total) if total else 0.0

    merged_rows = session.execute(
        select(PullRequest.created_at, PullRequest.merged_at).where(
            repo_filter,
            PullRequest.merged.is_(True),
            PullRequest.merged_at.isnot(None),
        )
    ).all()
    merge_days = [
        (merged_at - created_at).total_seconds() / 86400
        for created_at, merged_at in merged_rows
        if created_at is not None and merged_at is not None
    ]
    median_merge = median(merge_days) if merge_days else None

    return PullRequestMetrics(
        full_name=repository.full_name,
        total_prs=total,
        open_prs=open_prs,
        merged_prs=merged_prs,
        merge_rate=round(merge_rate, 3),
        median_merge_days=round(median_merge, 1) if median_merge is not None else None,
    )


def calculate_commit_activity_metrics(
    session: Session,
    repository: Repository,
    *,
    now: datetime | None = None,
) -> CommitActivityMetrics:
    now = now or datetime.now(UTC)
    six_months_ago = now - timedelta(days=183)
    twelve_months_ago = now - timedelta(days=365)
    repo_filter = Commit.repository_id == repository.id

    total = session.scalar(select(func.count()).select_from(Commit).where(repo_filter)) or 0
    last_6 = (
        session.scalar(
            select(func.count())
            .select_from(Commit)
            .where(repo_filter, Commit.committed_at >= six_months_ago)
        )
        or 0
    )
    prior_6 = (
        session.scalar(
            select(func.count())
            .select_from(Commit)
            .where(
                repo_filter,
                Commit.committed_at >= twelve_months_ago,
                Commit.committed_at < six_months_ago,
            )
        )
        or 0
    )

    if prior_6:
        change_pct = ((last_6 - prior_6) / prior_6) * 100
    elif last_6:
        change_pct = 100.0
    else:
        change_pct = None

    return CommitActivityMetrics(
        full_name=repository.full_name,
        total_commits=total,
        commits_last_6_months=last_6,
        commits_prior_6_months=prior_6,
        activity_change_pct=round(change_pct, 1) if change_pct is not None else None,
    )


def monthly_commit_counts(session: Session, repository: Repository, months: int = 12) -> pd.DataFrame:
    now = datetime.now(UTC)
    start = now - timedelta(days=months * 31)
    commits = session.scalars(
        select(Commit)
        .where(Commit.repository_id == repository.id, Commit.committed_at >= start)
        .order_by(Commit.committed_at.asc())
    ).all()

    if not commits:
        return pd.DataFrame(columns=["month", "commits"])

    rows = [{"month": commit.committed_at.strftime("%Y-%m"), "commits": 1} for commit in commits]
    frame = pd.DataFrame(rows)
    grouped = frame.groupby("month", as_index=False)["commits"].sum()
    return grouped.sort_values("month")


def calculate_contributor_metrics(session: Session, repository: Repository) -> ContributorMetrics:
    contributors = session.scalars(
        select(Contributor)
        .where(Contributor.repository_id == repository.id)
        .order_by(Contributor.contributions.desc())
    ).all()
    total_contributions = sum(c.contributions for c in contributors)
    top = contributors[0] if contributors else None
    top_share = (top.contributions / total_contributions) if top and total_contributions else 0.0
    top_3 = sum(c.contributions for c in contributors[:3])
    top_3_share = (top_3 / total_contributions) if total_contributions else 0.0

    return ContributorMetrics(
        full_name=repository.full_name,
        contributor_count=len(contributors),
        top_contributor=top.login if top else None,
        top_contributor_share=round(top_share, 3),
        top_3_contributor_share=round(top_3_share, 3),
    )


def top_contributors(session: Session, repository_id: int, limit: int = 10) -> list[dict]:
    contributors = session.scalars(
        select(Contributor)
        .where(Contributor.repository_id == repository_id)
        .order_by(Contributor.contributions.desc())
        .limit(limit)
    ).all()
    return [
        {
            "login": contributor.login,
            "contributions": contributor.contributions,
            "profile_url": contributor.html_url,
        }
        for contributor in contributors
    ]


def calculate_release_metrics(
    session: Session,
    repository: Repository,
    *,
    now: datetime | None = None,
) -> ReleaseMetrics:
    now = now or datetime.now(UTC)
    twelve_months_ago = now - timedelta(days=365)
    releases = session.scalars(
        select(Release)
        .where(Release.repository_id == repository.id, Release.draft.is_(False))
        .order_by(Release.published_at.asc())
    ).all()
    published = [release for release in releases if release.published_at is not None]
    recent = [release for release in published if release.published_at >= twelve_months_ago]

    gaps = []
    for earlier, later in zip(published, published[1:], strict=False):
        if earlier.published_at and later.published_at:
            gaps.append((later.published_at - earlier.published_at).total_seconds() / 86400)
    median_gap = median(gaps) if gaps else None

    last_release = published[-1].published_at if published else None
    days_since = ((now - last_release).total_seconds() / 86400) if last_release else None

    return ReleaseMetrics(
        full_name=repository.full_name,
        total_releases=len(published),
        releases_last_12_months=len(recent),
        median_days_between_releases=round(median_gap, 1) if median_gap is not None else None,
        days_since_last_release=round(days_since, 1) if days_since is not None else None,
    )


def calculate_repository_comparison(
    session: Session,
    repository: Repository,
    *,
    issue_metrics_fn,
) -> RepositoryComparisonMetrics:
    issue_metrics = issue_metrics_fn(session, repository)
    pr_metrics = calculate_pull_request_metrics(session, repository)
    commit_metrics = calculate_commit_activity_metrics(session, repository)
    contributor_metrics = calculate_contributor_metrics(session, repository)
    release_metrics = calculate_release_metrics(session, repository)

    return RepositoryComparisonMetrics(
        full_name=repository.full_name,
        stars=repository.stars,
        issue_closure_rate=issue_metrics.closure_rate,
        pr_merge_rate=pr_metrics.merge_rate,
        stale_open_issues=issue_metrics.stale_open_issues,
        commits_last_6_months=commit_metrics.commits_last_6_months,
        contributor_count=contributor_metrics.contributor_count,
        top_contributor_share=contributor_metrics.top_contributor_share,
        releases_last_12_months=release_metrics.releases_last_12_months,
    )


def calculate_all_pull_request_metrics(session: Session) -> list[dict]:
    repositories = session.scalars(select(Repository).order_by(Repository.full_name)).all()
    return [asdict(calculate_pull_request_metrics(session, repo)) for repo in repositories]


def calculate_all_commit_activity_metrics(session: Session) -> list[dict]:
    repositories = session.scalars(select(Repository).order_by(Repository.full_name)).all()
    return [asdict(calculate_commit_activity_metrics(session, repo)) for repo in repositories]


def calculate_all_contributor_metrics(session: Session) -> list[dict]:
    repositories = session.scalars(select(Repository).order_by(Repository.full_name)).all()
    return [asdict(calculate_contributor_metrics(session, repo)) for repo in repositories]


def calculate_all_release_metrics(session: Session) -> list[dict]:
    repositories = session.scalars(select(Repository).order_by(Repository.full_name)).all()
    return [asdict(calculate_release_metrics(session, repo)) for repo in repositories]


def calculate_all_repository_comparisons(session: Session, issue_metrics_fn) -> list[dict]:
    repositories = session.scalars(select(Repository).order_by(Repository.full_name)).all()
    return [
        asdict(calculate_repository_comparison(session, repo, issue_metrics_fn=issue_metrics_fn))
        for repo in repositories
    ]
