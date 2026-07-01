from src.ingestion.ingest import parse_repo_slug


def test_parse_repo_slug_valid() -> None:
    assert parse_repo_slug("octocat/Hello-World") == ("octocat", "Hello-World")


def test_parse_repo_slug_invalid() -> None:
    try:
        parse_repo_slug("invalid")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "owner/repo" in str(exc)
