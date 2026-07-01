"""Setup verification and sample ingestion."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import get_settings
from src.database.session import get_session_factory, init_db
from src.ingestion.github_client import GitHubClient
from src.ingestion.ingest import ingest_repository
from src.ingestion.issues import ingest_issues


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
    init_db()
    print("  OK — tables ready")

    repos = settings.sample_repo_list or ["octocat/Hello-World"]
    session = get_session_factory()()
    try:
        for slug in repos:
            print(f"Ingesting {slug}...")
            repository = ingest_repository(session, slug, client=client)
            print(f"  OK — {repository.full_name} ({repository.stars} stars)")
            issue_count = ingest_issues(session, repository, client=client, settings=settings)
            print(f"  OK — {issue_count} issues synced")
    finally:
        session.close()

    print("\nSetup complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
