from unittest.mock import MagicMock

from src.database.models import Repository
from src.ingestion.commits import upsert_commit


def test_upsert_commit() -> None:
    repository = Repository(id=1, full_name="o/r", owner="o", name="r")
    session = MagicMock()
    session.get.return_value = None

    payload = {
        "sha": "abc123" * 5 + "abcd",
        "html_url": "https://example.com/commit/abc",
        "author": {"login": "dev1", "name": "Dev One"},
        "commit": {
            "message": "Fix bug",
            "author": {"name": "Dev One", "date": "2024-01-01T00:00:00Z"},
        },
    }

    commit = upsert_commit(session, repository, payload)
    assert commit.author_login == "dev1"
    assert commit.message == "Fix bug"
