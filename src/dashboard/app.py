import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agent.grounded_chat import GroundedChatAgent, check_ollama_available, format_evidence
from src.analytics.correlation import POPULARITY_METRICS
from src.config import get_settings
from src.dashboard.data_loaders import (
    get_data_fingerprint,
    load_correlation_views,
    load_dashboard_bundle,
    load_repo_details,
    load_repository_report,
)
from src.database.models import Repository
from src.database.session import get_session_factory, init_db
from src.reporting.report import export_report
from src.retrieval.corpus import SemanticRetriever

st.set_page_config(page_title="RepoSense", layout="wide")
st.title("RepoSense Dashboard")
st.caption("Checkpoint 3 — analytics, grounded chat, correlations, and reports")

init_db()
fingerprint = get_data_fingerprint()
bundle = load_dashboard_bundle(fingerprint)
summaries = bundle["summaries"]

if not summaries:
    st.info("No repositories ingested yet. Run `python scripts/verify_setup.py` first.")
else:
    repo_names = [row["full_name"] for row in summaries]
    selected_repo = st.selectbox("Select repository", repo_names)
    repo_details = load_repo_details(fingerprint, selected_repo)

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

    issue_metrics = bundle["issue_metrics"]
    pr_metrics = bundle["pr_metrics"]
    commit_metrics = bundle["commit_metrics"]
    contributor_metrics = bundle["contributor_metrics"]
    release_metrics = bundle["release_metrics"]
    comparison = bundle["comparison"]

    with overview_tab:
        st.subheader("Repository overview")
        st.dataframe(summaries, width="stretch")
        if repo_details:
            cols = st.columns(4)
            cols[0].metric(
                "Issue closure rate",
                f"{repo_details['issue_metrics']['closure_rate']:.0%}",
            )
            cols[1].metric("PR merge rate", f"{repo_details['pr_metrics']['merge_rate']:.0%}")
            cols[2].metric(
                "Commits (6 mo)",
                repo_details["commit_metrics"]["commits_last_6_months"],
            )
            cols[3].metric(
                "Releases (12 mo)",
                repo_details["release_metrics"]["releases_last_12_months"],
            )

    with issues_tab:
        st.dataframe(issue_metrics, width="stretch")
        if repo_details:
            metrics = repo_details["issue_metrics"]
            st.metric("Stale open issues", metrics["stale_open_issues"])
            stale = repo_details["stale_issues"]
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

            label_rows = repo_details["label_rows"]
            if label_rows:
                st.subheader(f"Issue label distribution — {selected_repo}")
                st.dataframe(label_rows, width="stretch")
                st.bar_chart({row["label"]: row["count"] for row in label_rows})

    with prs_tab:
        st.dataframe(pr_metrics, width="stretch")
        merge_chart = {
            row["full_name"]: row["merge_rate"] for row in pr_metrics if row["total_prs"] > 0
        }
        if merge_chart:
            st.subheader("PR merge rate by repository")
            st.bar_chart(merge_chart)

    with commits_tab:
        st.dataframe(commit_metrics, width="stretch")
        activity_chart = {
            row["full_name"]: row["commits_last_6_months"]
            for row in commit_metrics
            if row["commits_last_6_months"] > 0
        }
        if activity_chart:
            st.subheader("Commits in the last 6 months")
            st.bar_chart(activity_chart)
        monthly_rows = repo_details.get("monthly_commits", []) if repo_details else []
        if monthly_rows:
            monthly = pd.DataFrame(monthly_rows)
            st.subheader(f"Monthly commit activity — {selected_repo}")
            st.line_chart(monthly.set_index("month"))

    with contributors_tab:
        st.dataframe(contributor_metrics, width="stretch")
        concentration_chart = {
            row["full_name"]: row["top_contributor_share"]
            for row in contributor_metrics
            if row["contributor_count"] > 0
        }
        if concentration_chart:
            st.subheader("Top contributor concentration")
            st.bar_chart(concentration_chart)
        leaders = repo_details.get("top_contributors", []) if repo_details else []
        if leaders:
            st.subheader(f"Top contributors — {selected_repo}")
            st.dataframe(leaders, width="stretch")
            st.bar_chart({row["login"]: row["contributions"] for row in leaders})

    with releases_tab:
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
        st.subheader("Cross-repository health comparison")
        st.dataframe(comparison, width="stretch")
        if comparison:
            st.subheader("Issue closure vs PR merge rate")
            compare_frame = {row["full_name"]: row["issue_closure_rate"] for row in comparison}
            st.bar_chart(compare_frame)

    @st.cache_resource(show_spinner="Building search index…")
    def _retriever_for_repo(full_name: str, _fingerprint: tuple[int, int, int, int]) -> SemanticRetriever:
        session = get_session_factory()()
        try:
            repository = session.scalar(
                select(Repository).where(Repository.full_name == full_name)
            )
            return SemanticRetriever.from_session(session, repository)
        finally:
            session.close()

    @st.fragment
    def grounded_chat_panel() -> None:
        st.subheader("Grounded chat")
        st.caption(
            "Answers are grounded in retrieved issues, comments, and documentation "
            f"via Ollama ({get_settings().ollama_model}). Metrics are precomputed, not "
            "estimated by the model."
        )
        if not repo_details:
            st.info("Select a repository to chat about its health.")
            return

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
        if not question:
            return

        st.session_state.chat_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        metrics = repo_details["issue_metrics"]
        pr = repo_details["pr_metrics"]
        commits = repo_details["commit_metrics"]
        metrics_context = (
            f"issue_closure_rate={metrics['closure_rate']:.3f}, "
            f"stale_open_issues={metrics['stale_open_issues']}, "
            f"pr_merge_rate={pr['merge_rate']:.3f}, "
            f"commits_last_6_months={commits['commits_last_6_months']}"
        )

        session: Session = get_session_factory()()
        try:
            repository = session.scalar(
                select(Repository).where(Repository.full_name == selected_repo)
            )
            with st.chat_message("assistant"):
                try:
                    check_ollama_available()
                    retriever = _retriever_for_repo(selected_repo, fingerprint)
                    agent = GroundedChatAgent(session, repository=repository, retriever=retriever)
                    settings = get_settings()
                    with st.spinner(
                        f"Generating answer with {settings.ollama_model} "
                        f"(may take up to {int(settings.ollama_request_timeout)}s on first reply)…"
                    ):
                        result = agent.answer(question, metrics_context=metrics_context)
                    st.markdown(result.answer)
                    evidence_text = format_evidence(
                        result.evidence,
                        max_chars=settings.retrieval_evidence_max_chars,
                    )
                    with st.expander("Retrieved evidence"):
                        st.text(evidence_text)
                    st.session_state.chat_messages.append(
                        {
                            "role": "assistant",
                            "content": result.answer,
                            "evidence": evidence_text,
                        }
                    )
                except TimeoutError as exc:
                    st.error(
                        "Ollama timed out. The model is running but the reply took too long. "
                        "Try a shorter question, wait for CPU/GPU load to drop, or increase "
                        "`OLLAMA_REQUEST_TIMEOUT` in `.env`."
                    )
                    st.caption(str(exc))
                except (ConnectionError, ValueError) as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error("Chat failed while calling Ollama.")
                    st.caption(str(exc))
        finally:
            session.close()

    with chat_tab:
        grounded_chat_panel()

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
            rows, matrix_rows = load_correlation_views(
                fingerprint,
                comparison,
                summaries,
                popularity=popularity,
                method="spearman",
            )
            st.dataframe(rows, width="stretch")
            chart_data = {
                row["maintenance_metric"]: row["coefficient"]
                for row in rows
                if row["coefficient"] is not None
            }
            if chart_data:
                st.bar_chart(chart_data)

            st.subheader("Full correlation matrix")
            if matrix_rows:
                st.dataframe(pd.DataFrame(matrix_rows), width="stretch")

    with reports_tab:
        st.subheader("Exportable health report")
        if st.button("Generate report preview", type="primary"):
            st.session_state.report_repo = selected_repo
            st.session_state.report_md = load_repository_report(fingerprint, selected_repo)

        report_md = st.session_state.get("report_md")
        if report_md and st.session_state.get("report_repo") == selected_repo:
            st.markdown(report_md)
            st.download_button(
                label="Download Markdown report",
                data=report_md,
                file_name=f"health_report_{selected_repo.replace('/', '__')}.md",
                mime="text/markdown",
            )
            if st.button("Save to outputs/"):
                session = get_session_factory()()
                try:
                    path = export_report(session, selected_repo)
                    st.success(f"Saved {path}")
                finally:
                    session.close()
        else:
            st.info("Click **Generate report preview** to render the Markdown report.")

    if st.sidebar.button("Refresh cached metrics"):
        st.cache_data.clear()
        st.rerun()
