import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agent.grounded_chat import GroundedChatAgent, format_evidence
from src.analytics.correlation import (
    POPULARITY_METRICS,
    correlation_matrix,
    popularity_correlations,
)
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
    calculate_label_distribution,
    label_distribution_as_rows,
    summarize_all_repositories,
    top_stale_issues,
)
from src.config import get_settings
from src.database.models import Repository
from src.database.session import get_session_factory, init_db
from src.reporting.report import export_report, generate_repository_report

st.set_page_config(page_title="RepoSense", layout="wide")
st.title("RepoSense Dashboard")
st.caption("Checkpoint 3 — analytics, grounded chat, correlations, and reports")

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

        (
            overview_tab,
            issues_tab,
            prs_tab,
            commits_tab,
            contributors_tab,
            releases_tab,
            compare_tab,
            chat_tab,
            correlation_tab,
            reports_tab,
        ) = st.tabs(
            [
                "Overview",
                "Issues",
                "Pull Requests",
                "Commits",
                "Contributors",
                "Releases",
                "Compare",
                "Chat",
                "Correlations",
                "Reports",
            ]
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

                label_distribution = calculate_label_distribution(session, repository)
                label_rows = label_distribution_as_rows(label_distribution)
                if label_rows:
                    st.subheader(f"Issue label distribution — {selected_repo}")
                    st.caption(
                        f"{label_distribution.labeled_issues} labeled issues, "
                        f"{label_distribution.unlabeled_issues} without labels"
                    )
                    st.dataframe(label_rows, width="stretch")
                    st.bar_chart({row["label"]: row["count"] for row in label_rows})

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

        with chat_tab:
            st.subheader("Grounded chat")
            st.caption(
                "Answers are grounded in retrieved issues, comments, and documentation "
                f"via Ollama ({get_settings().ollama_model}). Metrics are precomputed, not "
                "estimated by the model."
            )
            if repository is None:
                st.info("Select a repository to chat about its health.")
            else:
                if "chat_messages" not in st.session_state:
                    st.session_state.chat_messages = []
                if st.session_state.get("chat_repo") != selected_repo:
                    st.session_state.chat_messages = []
                    st.session_state.chat_repo = selected_repo

                for message in st.session_state.chat_messages:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])
                        if message.get("evidence"):
                            with st.expander("Retrieved evidence"):
                                st.text(message["evidence"])

                question = st.chat_input(f"Ask about {selected_repo}…")
                if question:
                    st.session_state.chat_messages.append({"role": "user", "content": question})
                    with st.chat_message("user"):
                        st.markdown(question)

                    issue_m = calculate_issue_metrics(session, repository)
                    pr_m = calculate_pull_request_metrics(session, repository)
                    commit_m = calculate_commit_activity_metrics(session, repository)
                    metrics_context = (
                        f"issue_closure_rate={issue_m.closure_rate:.3f}, "
                        f"stale_open_issues={issue_m.stale_open_issues}, "
                        f"pr_merge_rate={pr_m.merge_rate:.3f}, "
                        f"commits_last_6_months={commit_m.commits_last_6_months}"
                    )

                    with st.chat_message("assistant"):
                        try:
                            agent = GroundedChatAgent(session, repository=repository)
                            result = agent.answer(question, metrics_context=metrics_context)
                            st.markdown(result.answer)
                            evidence_text = format_evidence(result.evidence)
                            with st.expander("Retrieved evidence"):
                                st.text(evidence_text)
                            st.session_state.chat_messages.append(
                                {
                                    "role": "assistant",
                                    "content": result.answer,
                                    "evidence": evidence_text,
                                }
                            )
                        except Exception as exc:
                            st.error(
                                "Could not reach Ollama. Start it with `ollama serve` and ensure "
                                f"`{get_settings().ollama_model}` is pulled."
                            )
                            st.caption(str(exc))

        with correlation_tab:
            st.subheader("Exploratory correlations")
            st.caption(
                "Spearman rank correlations across ingested repositories. "
                "These are associations, not causal conclusions."
            )
            if len(summaries) < 2:
                st.info("Ingest at least two repositories to compute cross-repo correlations.")
            else:
                popularity = st.selectbox("Popularity metric", POPULARITY_METRICS, key="corr_pop")
                results = popularity_correlations(
                    session,
                    popularity=popularity,
                    method="spearman",
                    issue_metrics_fn=calculate_issue_metrics,
                )
                rows = [
                    {
                        "maintenance_metric": r.metric_b,
                        "coefficient": r.coefficient,
                        "n": r.n,
                        "method": r.method,
                    }
                    for r in results
                ]
                st.dataframe(rows, width="stretch")
                chart_data = {
                    row["maintenance_metric"]: row["coefficient"]
                    for row in rows
                    if row["coefficient"] is not None
                }
                if chart_data:
                    st.bar_chart(chart_data)

                st.subheader("Full correlation matrix")
                matrix = correlation_matrix(
                    session,
                    method="spearman",
                    issue_metrics_fn=calculate_issue_metrics,
                )
                st.dataframe(matrix, width="stretch")

        with reports_tab:
            st.subheader("Exportable health report")
            if repository is None:
                st.info("Select a repository to preview its report.")
            else:
                report_md = generate_repository_report(session, selected_repo)
                st.markdown(report_md)
                st.download_button(
                    label="Download Markdown report",
                    data=report_md,
                    file_name=f"health_report_{selected_repo.replace('/', '__')}.md",
                    mime="text/markdown",
                )
                if st.button("Save to outputs/"):
                    path = export_report(session, selected_repo)
                    st.success(f"Saved {path}")
finally:
    session.close()
