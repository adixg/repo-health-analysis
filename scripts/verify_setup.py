"""Setup verification and sample ingestion."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.exc import OperationalError

from src.config import get_settings
from src.database.session import get_session_factory, init_db
from src.ingestion.github_client import GitHubClient
from src.ingestion.ingest import ingest_repository, ingest_repository_data


def print_db_help() -> None:
    print(
        "\nPostgreSQL is not running or not reachable on the configured host/port.\n"
        "\nFix options:\n"
        "  1. Windows Service: open services.msc, start 'postgresql-x64-18'\n"
        "  2. Or run in an admin PowerShell: Start-Service postgresql-x64-18\n"
        "  3. Or use Docker: docker compose up -d\n"
        "\nThen confirm your .env settings match your database:\n"
        "  POSTGRES_HOST=localhost\n"
        "  POSTGRES_PORT=5432\n"
        "  POSTGRES_USER=reposense\n"
        "  POSTGRES_DB=reposense\n"
    )


def main() -> int:
    settings = get_settings()

    if not settings.github_token:
        print("ERROR: GITHUB_TOKEN is not set. Copy .env.example to .env and add your token.")
        return 1

    print("Checking GitHub authentication...")
    client = GitHubClient(settings)
    user = client.verify_authentication()
    print(f"  OK — authenticated as {user.get('login')}")

    print("Initializing database...")
    try:
        init_db()
    except OperationalError:
        print("  ERROR — could not connect to PostgreSQL.")
        print_db_help()
        return 1
    print("  OK — tables ready")

    repos = settings.sample_repo_list or ["octocat/Hello-World"]
    session = get_session_factory()()
    try:
        for slug in repos:
            print(f"Ingesting {slug}...")
            repository = ingest_repository(session, slug, client=client)
            print(f"  OK — {repository.full_name} ({repository.stars} stars)")
            counts = ingest_repository_data(session, repository, client=client, settings=settings)
            print(f"  OK — {counts.issues} issues synced")
            print(f"  OK — {counts.pull_requests} pull requests synced")
            print(f"  OK — {counts.commits} commits synced")
            print(f"  OK — {counts.contributors} contributors synced")
            print(f"  OK — {counts.releases} releases synced")
            print(f"  OK — {counts.issue_comments} issue comments synced")
            print(f"  OK — {counts.pull_request_comments} pull-request comments synced")
            print(f"  OK — {counts.documents} documents synced")
    finally:
        session.close()

    print("\nSetup complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
