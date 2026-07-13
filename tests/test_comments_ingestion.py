from unittest.mock import MagicMock

from src.database.models import Repository
from src.ingestion.comments import (
    _trailing_number,
    upsert_issue_comment,
    upsert_pull_request_comment,
)


def test_trailing_number_extracts_issue_id() -> None:
    assert _trailing_number("https://api.github.com/repos/psf/requests/issues/123") == 123
    assert _trailing_number("https://api.github.com/repos/psf/requests/pulls/456") == 456
    assert _trailing_number(None) is None
    assert _trailing_number("https://example.com/no-number/") is None


def test_upsert_issue_comment_maps_fields() -> None:
    repository = Repository(id=7, full_name="psf/requests", owner="psf", name="requests")
    session = MagicMock()
    session.get.return_value = None
    payload = {
        "id": 555,
        "issue_url": "https://api.github.com/repos/psf/requests/issues/42",
        "user": {"login": "octocat"},
        "body": "This still reproduces on 3.12.",
        "html_url": "https://github.com/psf/requests/issues/42#issuecomment-555",
        "created_at": "2024-01-02T03:04:05Z",
        "updated_at": "2024-01-02T03:04:05Z",
    }

    comment = upsert_issue_comment(session, repository, payload)

    assert comment.id == 555
    assert comment.repository_id == 7
    assert comment.issue_number == 42
    assert comment.author_login == "octocat"
    assert comment.body == "This still reproduces on 3.12."
    assert comment.created_at is not None
    session.add.assert_called_once()


def test_upsert_pull_request_comment_maps_pull_number() -> None:
    repository = Repository(id=7, full_name="psf/requests", owner="psf", name="requests")
    session = MagicMock()
    session.get.return_value = None
    payload = {
        "id": 999,
        "pull_request_url": "https://api.github.com/repos/psf/requests/pulls/900",
        "user": {"login": "reviewer"},
        "body": "nit: rename this variable",
        "created_at": "2024-02-02T00:00:00Z",
        "updated_at": "2024-02-02T00:00:00Z",
    }

    comment = upsert_pull_request_comment(session, repository, payload)

    assert comment.pull_number == 900
    assert comment.author_login == "reviewer"
    assert comment.body == "nit: rename this variable"
