"""Cached data loaders for the Streamlit dashboard."""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st
from sqlalchemy import func, select

from src.analytics.correlation import MAINTENANCE_METRICS, _clean
from src.analytics.health_metrics import (
    calculate_commit_activity_metrics,
    calculate_contributor_metrics,
    calculate_pull_request_metrics,
    calculate_release_metrics,
    monthly_commit_counts,
    top_contributors,
)
from src.analytics.metrics import (
    calculate_issue_metrics,
    calculate_label_distribution,
    label_distribution_as_rows,
    summarize_repository,
    top_stale_issues,
)
from src.database.models import Issue, IssueComment, Repository
from src.database.session import get_session_factory
from src.reporting.report import generate_repository_report


@st.cache_data(ttl=300, show_spinner=False)
def get_data_fingerprint() -> tuple[int, int, int, int]:
    """Cheap row counts used to invalidate cached dashboard payloads after ingestion."""
    session = get_session_factory()()
    try:
        repos = session.scalar(select(func.count()).select_from(Repository)) or 0
        issues = session.scalar(select(func.count()).select_from(Issue)) or 0
        comments = session.scalar(select(func.count()).select_from(IssueComment)) or 0
        return (repos, issues, comments, repos + issues + comments)
    finally:
        session.close()


@st.cache_data(ttl=300, show_spinner="Loading repository metrics…")
def load_dashboard_bundle(_fingerprint: tuple[int, int, int, int]) -> dict:
    """Load all cross-repo metrics in one pass per repository."""
    session = get_session_factory()()
    try:
        from src.analytics.health_metrics import (
            calculate_commit_activity_metrics,
            calculate_contributor_metrics,
            calculate_pull_request_metrics,
            calculate_release_metrics,
        )

        repositories = session.scalars(
            select(Repository).order_by(Repository.full_name)
        ).all()
        summaries = [asdict(summarize_repository(repo)) for repo in repositories]

        issue_metrics: list[dict] = []
        pr_metrics: list[dict] = []
        commit_metrics: list[dict] = []
        contributor_metrics: list[dict] = []
        release_metrics: list[dict] = []
        comparison: list[dict] = []

        for repo in repositories:
            issue_m = calculate_issue_metrics(session, repo)
            pr_m = calculate_pull_request_metrics(session, repo)
            commit_m = calculate_commit_activity_metrics(session, repo)
            contributor_m = calculate_contributor_metrics(session, repo)
            release_m = calculate_release_metrics(session, repo)

            issue_metrics.append(asdict(issue_m))
            pr_metrics.append(asdict(pr_m))
            commit_metrics.append(asdict(commit_m))
            contributor_metrics.append(asdict(contributor_m))
            release_metrics.append(asdict(release_m))
            comparison.append(
                {
                    "full_name": repo.full_name,
                    "stars": repo.stars,
                    "issue_closure_rate": issue_m.closure_rate,
                    "pr_merge_rate": pr_m.merge_rate,
                    "stale_open_issues": issue_m.stale_open_issues,
                    "commits_last_6_months": commit_m.commits_last_6_months,
                    "contributor_count": contributor_m.contributor_count,
                    "top_contributor_share": contributor_m.top_contributor_share,
                    "releases_last_12_months": release_m.releases_last_12_months,
                }
            )

        return {
            "summaries": summaries,
            "issue_metrics": issue_metrics,
            "pr_metrics": pr_metrics,
            "commit_metrics": commit_metrics,
            "contributor_metrics": contributor_metrics,
            "release_metrics": release_metrics,
            "comparison": comparison,
        }
    finally:
        session.close()


@st.cache_data(ttl=300, show_spinner=False)
def load_repo_details(_fingerprint: tuple[int, int, int, int], full_name: str) -> dict:
    """Load per-repository detail used by multiple tabs."""
    session = get_session_factory()()
    try:
        repository = session.scalar(
            select(Repository).where(Repository.full_name == full_name)
        )
        if repository is None:
            return {}

        issue_m = calculate_issue_metrics(session, repository)
        pr_m = calculate_pull_request_metrics(session, repository)
        commit_m = calculate_commit_activity_metrics(session, repository)
        release_m = calculate_release_metrics(session, repository)
        contributor_m = calculate_contributor_metrics(session, repository)
        label_distribution = calculate_label_distribution(session, repository)
        monthly = monthly_commit_counts(session, repository)
        stale = top_stale_issues(session, repository.id)
        leaders = top_contributors(session, repository.id)

        return {
            "issue_metrics": asdict(issue_m),
            "pr_metrics": asdict(pr_m),
            "commit_metrics": asdict(commit_m),
            "release_metrics": asdict(release_m),
            "contributor_metrics": asdict(contributor_m),
            "label_rows": label_distribution_as_rows(label_distribution),
            "monthly_commits": monthly.to_dict(orient="records") if not monthly.empty else [],
            "stale_issues": stale,
            "top_contributors": leaders,
        }
    finally:
        session.close()


@st.cache_data(ttl=300, show_spinner=False)
def load_correlation_views(
    _fingerprint: tuple[int, int, int, int],
    comparison: list[dict],
    summaries: list[dict],
    popularity: str,
    method: str,
) -> tuple[list[dict], list[dict]]:
    """Derive correlation tables from the already-loaded comparison frame."""
    if len(comparison) < 2:
        return [], []

    frame = pd.DataFrame(comparison).set_index("full_name")
    forks_by_name = {row["full_name"]: row.get("forks", 0) for row in summaries}
    frame["forks"] = [forks_by_name.get(name, 0) for name in frame.index]

    popularity_rows: list[dict] = []
    if popularity in frame.columns:
        for metric in MAINTENANCE_METRICS:
            if metric not in frame.columns:
                continue
            pair = frame[[popularity, metric]].dropna()
            coefficient = (
                pair[popularity].corr(pair[metric], method=method)
                if len(pair) >= 2
                else None
            )
            popularity_rows.append(
                {
                    "maintenance_metric": metric,
                    "coefficient": _clean(coefficient),
                    "n": int(len(pair)),
                    "method": method,
                }
            )

    numeric = frame.select_dtypes(include="number")
    matrix = numeric.corr(method=method).round(4).reset_index().to_dict(orient="records")
    return popularity_rows, matrix


@st.cache_data(ttl=300, show_spinner="Generating report…")
def load_repository_report(_fingerprint: tuple[int, int, int, int], full_name: str) -> str:
    session = get_session_factory()()
    try:
        return generate_repository_report(session, full_name)
    finally:
        session.close()
