import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dataclasses import asdict

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.analytics.correlation import popularity_correlations
from src.analytics.health_metrics import (
    calculate_all_commit_activity_metrics,
    calculate_all_contributor_metrics,
    calculate_all_pull_request_metrics,
    calculate_all_release_metrics,
    calculate_all_repository_comparisons,
)
from src.analytics.metrics import (
    calculate_all_issue_metrics,
    calculate_issue_metrics,
    calculate_label_distribution,
    label_distribution_as_rows,
    summarize_all_repositories,
)
from src.database.session import get_db_session, init_db
from src.reporting.report import generate_repository_report

app = FastAPI(title="RepoSense API", version="0.2.0")


class ChatRequest(BaseModel):
    question: str
    full_name: str
    top_k: int | None = None


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/repositories")
def list_repositories(session: Session = Depends(get_db_session)) -> list[dict]:
    return summarize_all_repositories(session)


@app.get("/metrics/issues")
def issue_metrics(session: Session = Depends(get_db_session)) -> list[dict]:
    return calculate_all_issue_metrics(session)


@app.get("/metrics/labels/{owner}/{repo}")
def label_metrics(owner: str, repo: str, session: Session = Depends(get_db_session)) -> dict:
    from sqlalchemy import select

    from src.database.models import Repository

    repository = session.scalar(
        select(Repository).where(Repository.full_name == f"{owner}/{repo}")
    )
    if repository is None:
        return {"error": "repository not found"}
    distribution = calculate_label_distribution(session, repository)
    return {
        **asdict(distribution),
        "top_labels": label_distribution_as_rows(distribution),
    }


@app.get("/metrics/pull-requests")
def pull_request_metrics(session: Session = Depends(get_db_session)) -> list[dict]:
    return calculate_all_pull_request_metrics(session)


@app.get("/metrics/commits")
def commit_metrics(session: Session = Depends(get_db_session)) -> list[dict]:
    return calculate_all_commit_activity_metrics(session)


@app.get("/metrics/contributors")
def contributor_metrics(session: Session = Depends(get_db_session)) -> list[dict]:
    return calculate_all_contributor_metrics(session)


@app.get("/metrics/releases")
def release_metrics(session: Session = Depends(get_db_session)) -> list[dict]:
    return calculate_all_release_metrics(session)


@app.get("/metrics/comparison")
def comparison_metrics(session: Session = Depends(get_db_session)) -> list[dict]:
    return calculate_all_repository_comparisons(session, issue_metrics_fn=calculate_issue_metrics)


@app.get("/metrics/correlations")
def correlation_metrics(
    popularity: str = "stars",
    method: str = "spearman",
    session: Session = Depends(get_db_session),
) -> list[dict]:
    results = popularity_correlations(
        session,
        popularity=popularity,
        method=method,
        issue_metrics_fn=calculate_issue_metrics,
    )
    return [asdict(r) for r in results]


@app.get("/reports/{owner}/{repo}")
def repository_report(owner: str, repo: str, session: Session = Depends(get_db_session)) -> dict:
    full_name = f"{owner}/{repo}"
    try:
        markdown = generate_repository_report(session, full_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"full_name": full_name, "markdown": markdown}


@app.post("/chat")
def grounded_chat(payload: ChatRequest, session: Session = Depends(get_db_session)) -> dict:
    from sqlalchemy import select

    from src.agent.grounded_chat import GroundedChatAgent
    from src.analytics.health_metrics import (
        calculate_commit_activity_metrics,
        calculate_pull_request_metrics,
    )
    from src.database.models import Repository

    repository = session.scalar(
        select(Repository).where(Repository.full_name == payload.full_name)
    )
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    issue_m = calculate_issue_metrics(session, repository)
    pr_m = calculate_pull_request_metrics(session, repository)
    commit_m = calculate_commit_activity_metrics(session, repository)
    metrics_context = (
        f"issue_closure_rate={issue_m.closure_rate:.3f}, "
        f"stale_open_issues={issue_m.stale_open_issues}, "
        f"pr_merge_rate={pr_m.merge_rate:.3f}, "
        f"commits_last_6_months={commit_m.commits_last_6_months}"
    )

    agent = GroundedChatAgent(session, repository=repository)
    result = agent.answer(
        payload.question,
        top_k=payload.top_k,
        metrics_context=metrics_context,
    )
    return {
        "question": result.question,
        "answer": result.answer,
        "evidence": [
            {
                "repository": chunk.repository_full_name,
                "source_type": chunk.source_type,
                "source_id": chunk.source_id,
                "title": chunk.title,
                "score": chunk.score,
            }
            for chunk in result.evidence
        ],
    }
