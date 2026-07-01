from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from hashlib import sha256
from pathlib import Path
from typing import Any

import httpx

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


class GitHubClient:
    """Thin wrapper around the GitHub REST API with optional response caching."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.github_api_base_url.rstrip("/")
        self.cache_dir = Path(self.settings.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        return headers

    def _cache_path(self, path: str, params: dict[str, Any] | None) -> Path:
        key = f"{path}?{json.dumps(params or {}, sort_keys=True)}"
        digest = sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> Any:
        cache_file = self._cache_path(path, params)
        if use_cache and cache_file.exists():
            logger.debug("Cache hit: %s", path)
            return json.loads(cache_file.read_text(encoding="utf-8"))

        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        with httpx.Client(headers=self._headers, timeout=30.0) as client:
            response = client.get(url, params=params)
            if response.status_code == 403 and "rate limit" in response.text.lower():
                reset = response.headers.get("X-RateLimit-Reset")
                if reset:
                    wait_seconds = max(int(reset) - int(time.time()), 0) + 1
                    logger.warning("Rate limited; sleeping %s seconds", wait_seconds)
                    time.sleep(wait_seconds)
                    response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        cache_file.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def paginate(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
        max_pages: int | None = None,
    ) -> Iterator[Any]:
        page = 1
        while True:
            if max_pages is not None and page > max_pages:
                break
            batch = self.get(
                path,
                params={**(params or {}), "per_page": 100, "page": page},
                use_cache=use_cache,
            )
            if not batch:
                break
            yield from batch
            if len(batch) < 100:
                break
            page += 1

    def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        return self.get(f"repos/{owner}/{repo}")

    def list_issues(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "all",
        since: str | None = None,
        max_pages: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        params: dict[str, Any] = {"state": state, "sort": "updated", "direction": "asc"}
        if since:
            params["since"] = since
        yield from self.paginate(
            f"repos/{owner}/{repo}/issues",
            params=params,
            max_pages=max_pages,
        )

    def list_pull_requests(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "all",
        max_pages: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        yield from self.paginate(
            f"repos/{owner}/{repo}/pulls",
            params={"state": state, "sort": "updated", "direction": "asc"},
            max_pages=max_pages,
        )

    def list_commits(
        self,
        owner: str,
        repo: str,
        *,
        since: str | None = None,
        max_pages: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        params: dict[str, Any] = {}
        if since:
            params["since"] = since
        yield from self.paginate(
            f"repos/{owner}/{repo}/commits",
            params=params,
            max_pages=max_pages,
        )

    def list_contributors(
        self,
        owner: str,
        repo: str,
        *,
        max_pages: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        yield from self.paginate(
            f"repos/{owner}/{repo}/contributors",
            params={"anon": "false"},
            max_pages=max_pages,
        )

    def list_releases(
        self,
        owner: str,
        repo: str,
        *,
        max_pages: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        yield from self.paginate(
            f"repos/{owner}/{repo}/releases",
            max_pages=max_pages,
        )

    def verify_authentication(self) -> dict[str, Any]:
        """Return the authenticated user profile; raises if the token is invalid."""
        return self.get("/user", use_cache=False)
