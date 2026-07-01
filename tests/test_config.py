from src.config import Settings


def test_database_url_built_from_postgres_fields() -> None:
    settings = Settings(
        postgres_user="user",
        postgres_password="pass",
        postgres_host="db",
        postgres_port=5433,
        postgres_db="reposense",
    )
    assert settings.sqlalchemy_database_url == (
        "postgresql+psycopg2://user:pass@db:5433/reposense"
    )


def test_sample_repo_list_parsing() -> None:
    settings = Settings(sample_repos="a/b, c/d ")
    assert settings.sample_repo_list == ["a/b", "c/d"]
