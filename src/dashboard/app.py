import sys

from pathlib import Path



ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:

    sys.path.insert(0, str(ROOT))



import streamlit as st

from sqlalchemy import select

from sqlalchemy.orm import Session



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

st.caption("Checkpoint 2 — repository and issue health")



init_db()

session: Session = get_session_factory()()



try:

    summaries = summarize_all_repositories(session)

    issue_metrics = calculate_all_issue_metrics(session)



    if not summaries:

        st.info("No repositories ingested yet. Run `python scripts/verify_setup.py` first.")

    else:

        st.subheader("Repository overview")

        st.dataframe(summaries, width="stretch")



        st.subheader("Issue health metrics")

        if not any(row["total_issues"] > 0 for row in issue_metrics):

            st.info("No issues ingested yet. Re-run `python scripts/verify_setup.py`.")

        else:

            st.dataframe(issue_metrics, width="stretch")



            chart_data = {

                row["full_name"]: row["stale_open_issues"]

                for row in issue_metrics

                if row["stale_open_issues"] > 0

            }

            if chart_data:

                st.subheader("Stale open issues (90+ days)")

                st.bar_chart(chart_data)



            repo_names = [row["full_name"] for row in summaries]

            selected = st.selectbox("Inspect stale issues for", repo_names)

            repository = session.scalar(

                select(Repository).where(Repository.full_name == selected)

            )

            if repository is not None:

                metrics = calculate_issue_metrics(session, repository)

                cols = st.columns(4)

                cols[0].metric("Total issues", metrics.total_issues)

                cols[1].metric("Closure rate", f"{metrics.closure_rate:.0%}")

                cols[2].metric("Stale open", metrics.stale_open_issues)

                cols[3].metric(

                    "Median resolution",

                    f"{metrics.median_resolution_days} days"

                    if metrics.median_resolution_days is not None

                    else "N/A",

                )



                stale = top_stale_issues(session, repository.id)

                if stale:

                    st.subheader(f"Oldest stale issues — {selected}")

                    st.dataframe(stale, width="stretch")

finally:

    session.close()

