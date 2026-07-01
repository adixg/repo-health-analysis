from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    github_token: str = ""
    github_api_base_url: str = "https://api.github.com"

    postgres_user: str = "reposense"
    postgres_password: str = "reposense"
    postgres_db: str = "reposense"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: str = ""

    log_level: str = "INFO"
    cache_dir: Path = Path("data/cache")
    sample_repos: str = ""
    issues_max_pages: int | None = None
    stale_issue_days: int = 90

    @field_validator("issues_max_pages", mode="before")
    @classmethod
    def empty_issues_max_pages_is_none(cls, value: Any) -> Any:
        if value == "" or value is None:
            return None
        return value

    @computed_field
    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def sample_repo_list(self) -> list[str]:
        if not self.sample_repos.strip():
            return []
        return [repo.strip() for repo in self.sample_repos.split(",") if repo.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
