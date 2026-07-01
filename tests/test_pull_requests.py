from datetime import UTC, datetime

from src.ingestion.pull_requests import upsert_pull_request
from src.ingestion.utils import parse_github_datetime


def test_parse_github_datetime() -> None:
    parsed = parse_github_datetime("2024-01-15T10:00:00Z")
    assert parsed == datetime(2024, 1, 15, 10, 0, tzinfo=UTC)


def test_upsert_pull_request_merged_flag() -> None:
    from unittest.mock import MagicMock

    from src.database.models import Repository

    repository = Repository(id=1, full_name="o/r", owner="o", name="r")
    session = MagicMock()
    session.get.return_value = None

    payload = {
        "id": 999,
        "number": 12,
        "title": "Add feature",
        "state": "closed",
        "user": {"login": "dev1"},
        "labels": [],
        "comments": 2,
        "html_url": "https://example.com/pull/12",
        "created_at": "2024-01-01T00:00:00Z",
        "closed_at": "2024-01-02T00:00:00Z",
        "merged_at": "2024-01-02T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
    }

    pull_request = upsert_pull_request(session, repository, payload)
    assert pull_request.merged is True
    assert pull_request.author_login == "dev1"
