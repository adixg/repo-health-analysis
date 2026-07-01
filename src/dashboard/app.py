import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.analytics.health_metrics import (
    calculate_all_commit_activity_metrics,
    calculate_all_contributor_metrics,
    calculate_all_pull_request_metrics,
    calculate_all_release_metrics,
    calculate_all_repository_comparisons,
    calculate_commit_activity_metrics,
    calculate_contributor_metrics,
    calculate_pull_request_metrics,
    calculate_release_metrics,
    monthly_commit_counts,
    top_contributors,
)
from src.analytics.metrics import (
    calculate_all_issue_metrics,
    calculate_issue_metrics,
    summarize_all_repositories,
    top_stale_issues,
)
from src.database.models import Repository
from src.database.session import get_session_factory, init_db

st.set_page_config(page_title="RepoSense", layout="wide")
st.title("RepoSense Dashboard")
st.caption("Checkpoint 2 — repository health analytics")

init_db()
session: Session = get_session_factory()()

try:
    summaries = summarize_all_repositories(session)
    if not summaries:
        st.info("No repositories ingested yet. Run `python scripts/verify_setup.py` first.")
    else:
        repo_names = [row["full_name"] for row in summaries]
        selected_repo = st.selectbox("Select repository", repo_names)
        repository = session.scalar(
            select(Repository).where(Repository.full_name == selected_repo)
        )

        overview_tab, issues_tab, prs_tab, commits_tab, contributors_tab, releases_tab, compare_tab = (
            st.tabs(
                [
                    "Overview",
                    "Issues",
                    "Pull Requests",
                    "Commits",
                    "Contributors",
                    "Releases",
                    "Compare",
                ]
            )
        )

        with overview_tab:
            st.subheader("Repository overview")
            st.dataframe(summaries, width="stretch")
            if repository is not None:
                cols = st.columns(4)
                issue_m = calculate_issue_metrics(session, repository)
                pr_m = calculate_pull_request_metrics(session, repository)
                commit_m = calculate_commit_activity_metrics(session, repository)
                release_m = calculate_release_metrics(session, repository)
                cols[0].metric("Issue closure rate", f"{issue_m.closure_rate:.0%}")
                cols[1].metric("PR merge rate", f"{pr_m.merge_rate:.0%}")
                cols[2].metric("Commits (6 mo)", commit_m.commits_last_6_months)
                cols[3].metric("Releases (12 mo)", release_m.releases_last_12_months)

        with issues_tab:
            issue_metrics = calculate_all_issue_metrics(session)
            st.dataframe(issue_metrics, width="stretch")
            if repository is not None:
                metrics = calculate_issue_metrics(session, repository)
                stale = top_stale_issues(session, repository.id)
                st.metric("Stale open issues", metrics.stale_open_issues)
                if stale:
                    st.subheader(f"Oldest stale issues — {selected_repo}")
                    st.dataframe(stale, width="stretch")
                stale_chart = {
                    row["full_name"]: row["stale_open_issues"]
                    for row in issue_metrics
                    if row["stale_open_issues"] > 0
                }
                if stale_chart:
                    st.subheader("Stale open issues by repository")
                    st.bar_chart(stale_chart)

        with prs_tab:
            pr_metrics = calculate_all_pull_request_metrics(session)
            st.dataframe(pr_metrics, width="stretch")
            merge_chart = {
                row["full_name"]: row["merge_rate"] for row in pr_metrics if row["total_prs"] > 0
            }
            if merge_chart:
                st.subheader("PR merge rate by repository")
                st.bar_chart(merge_chart)

        with commits_tab:
            commit_metrics = calculate_all_commit_activity_metrics(session)
            st.dataframe(commit_metrics, width="stretch")
            activity_chart = {
                row["full_name"]: row["commits_last_6_months"]
                for row in commit_metrics
                if row["commits_last_6_months"] > 0
            }
            if activity_chart:
                st.subheader("Commits in the last 6 months")
                st.bar_chart(activity_chart)
            if repository is not None:
                monthly = monthly_commit_counts(session, repository)
                if not monthly.empty:
                    st.subheader(f"Monthly commit activity — {selected_repo}")
                    st.line_chart(monthly.set_index("month"))

        with contributors_tab:
            contributor_metrics = calculate_all_contributor_metrics(session)
            st.dataframe(contributor_metrics, width="stretch")
            concentration_chart = {
                row["full_name"]: row["top_contributor_share"]
                for row in contributor_metrics
                if row["contributor_count"] > 0
            }
            if concentration_chart:
                st.subheader("Top contributor concentration")
                st.bar_chart(concentration_chart)
            if repository is not None:
                leaders = top_contributors(session, repository.id)
                if leaders:
                    st.subheader(f"Top contributors — {selected_repo}")
                    st.dataframe(leaders, width="stretch")
                    st.bar_chart({row["login"]: row["contributions"] for row in leaders})

        with releases_tab:
            release_metrics = calculate_all_release_metrics(session)
            st.dataframe(release_metrics, width="stretch")
            release_chart = {
                row["full_name"]: row["releases_last_12_months"]
                for row in release_metrics
                if row["releases_last_12_months"] > 0
            }
            if release_chart:
                st.subheader("Releases in the last 12 months")
                st.bar_chart(release_chart)

        with compare_tab:
            comparison = calculate_all_repository_comparisons(
                session,
                issue_metrics_fn=calculate_issue_metrics,
            )
            st.subheader("Cross-repository health comparison")
            st.dataframe(comparison, width="stretch")
            if comparison:
                st.subheader("Issue closure vs PR merge rate")
                compare_frame = {
                    row["full_name"]: row["issue_closure_rate"] for row in comparison
                }
                st.bar_chart(compare_frame)
finally:
    session.close()
