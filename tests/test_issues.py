from datetime import UTC, datetime, timedelta

from src.ingestion.issues import is_pull_request
from src.ingestion.utils import parse_github_datetime


def test_parse_github_datetime() -> None:
    parsed = parse_github_datetime("2024-01-15T10:00:00Z")
    assert parsed == datetime(2024, 1, 15, 10, 0, tzinfo=UTC)


def test_is_pull_request() -> None:
    assert is_pull_request({"pull_request": {"url": "https://example.com"}}) is True
    assert is_pull_request({"number": 1}) is False
