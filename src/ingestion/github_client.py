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

# GitHub REST API rejects page numbers above 100 (max 10,000 items at per_page=100).
GITHUB_MAX_PAGE = 100
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
MAX_REQUEST_RETRIES = 5


class GitHubClient:
    """Thin wrapper around the GitHub REST API with optional response caching."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.github_api_base_url.rstrip("/")
        self.cache_dir = Path(self.settings.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._http: httpx.Client | None = None

    def close(self) -> None:
        if self._http is not None:
            self._http.close()
            self._http = None

    def _client(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(headers=self._headers, timeout=30.0)
        return self._http

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

    def _request(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        client = self._client()
        last_response: httpx.Response | None = None

        for attempt in range(MAX_REQUEST_RETRIES):
            try:
                response = client.get(url, params=params)
            except httpx.TransportError as exc:
                if attempt + 1 >= MAX_REQUEST_RETRIES:
                    raise
                wait_seconds = 2**attempt
                logger.warning(
                    "GitHub request failed (%s); retrying in %ss (attempt %s/%s)",
                    exc,
                    wait_seconds,
                    attempt + 1,
                    MAX_REQUEST_RETRIES,
                )
                time.sleep(wait_seconds)
                continue

            if response.status_code == 403 and "rate limit" in response.text.lower():
                reset = response.headers.get("X-RateLimit-Reset")
                if reset:
                    wait_seconds = max(int(reset) - int(time.time()), 0) + 1
                    logger.warning("Rate limited; sleeping %s seconds", wait_seconds)
                    time.sleep(wait_seconds)
                    continue

            if response.status_code in RETRYABLE_STATUS_CODES and attempt + 1 < MAX_REQUEST_RETRIES:
                wait_seconds = 2**attempt
                logger.warning(
                    "GitHub returned %s for %s; retrying in %ss (attempt %s/%s)",
                    response.status_code,
                    url,
                    wait_seconds,
                    attempt + 1,
                    MAX_REQUEST_RETRIES,
                )
                time.sleep(wait_seconds)
                last_response = response
                continue

            return response

        if last_response is not None:
            return last_response
        raise RuntimeError(f"GitHub request failed after {MAX_REQUEST_RETRIES} attempts: {url}")

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
        response = self._request(url, params=params)
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
        page_limit = min(max_pages, GITHUB_MAX_PAGE) if max_pages is not None else GITHUB_MAX_PAGE
        while True:
            if page > page_limit:
                if max_pages is None and page > GITHUB_MAX_PAGE:
                    logger.warning(
                        "Reached GitHub pagination limit (%s pages) for %s; "
                        "remaining items are skipped. Use incremental sync (since=) "
                        "or per-resource endpoints for large repositories.",
                        GITHUB_MAX_PAGE,
                        path,
                    )
                break
            try:
                batch = self.get(
                    path,
                    params={**(params or {}), "per_page": 100, "page": page},
                    use_cache=use_cache,
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 422:
                    logger.warning(
                        "GitHub pagination rejected page %s for %s; stopping early.",
                        page,
                        path,
                    )
                    break
                raise
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

    def list_issue_comments(
        self,
        owner: str,
        repo: str,
        *,
        since: str | None = None,
        max_pages: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        params: dict[str, Any] = {"sort": "created", "direction": "asc"}
        if since:
            params["since"] = since
        yield from self.paginate(
            f"repos/{owner}/{repo}/issues/comments",
            params=params,
            max_pages=max_pages,
        )

    def list_pull_request_comments(
        self,
        owner: str,
        repo: str,
        *,
        since: str | None = None,
        max_pages: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        params: dict[str, Any] = {"sort": "created", "direction": "asc"}
        if since:
            params["since"] = since
        yield from self.paginate(
            f"repos/{owner}/{repo}/pulls/comments",
            params=params,
            max_pages=max_pages,
        )

    def get_readme(self, owner: str, repo: str) -> dict[str, Any] | None:
        """Return the repository README payload (base64 content), or None if absent."""
        try:
            return self.get(f"repos/{owner}/{repo}/readme")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.info("No README found for %s/%s", owner, repo)
                return None
            raise

    def verify_authentication(self) -> dict[str, Any]:
        """Return the authenticated user profile; raises if the token is invalid."""
        return self.get("/user", use_cache=False)
