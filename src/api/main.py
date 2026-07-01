import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from src.analytics.metrics import calculate_all_issue_metrics, summarize_all_repositories
from src.database.session import get_db_session, init_db

app = FastAPI(title="RepoSense API", version="0.1.0")


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
