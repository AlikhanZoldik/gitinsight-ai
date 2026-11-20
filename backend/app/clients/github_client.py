import asyncio
import math
import os
import time
from collections import OrderedDict

import httpx

from backend.app.config import MAX_PAGES
from backend.app.models.schemas import Profile, Repository, RepositoryList
from backend.app.utils.errors import GitHubError


def upstream_error() -> GitHubError:
    return GitHubError(502, "GitHub returned an unexpected response. Please try again later.")


class GitHubClient:
    def __init__(self, http: httpx.AsyncClient):
        self.http = http
        self.slots = asyncio.Semaphore(
            max(1, min(8, int(os.getenv("AUDIT_GITHUB_CONCURRENCY", "4"))))
        )
        self.resume_at = 0.0
        self.cache: OrderedDict[tuple, tuple[float, httpx.Response]] = OrderedDict()
        self.cache_locks = [asyncio.Lock() for _ in range(64)]

    async def fresh(self, path: str) -> httpx.Response:
        return await self._request(path, False, {})

    async def request(
        self, path: str, *, head: bool = False, **params: str | int
    ) -> httpx.Response:
        key = (path, head, tuple(sorted(params.items())))
        async with self.cache_locks[hash(key) % len(self.cache_locks)]:
            entry = self.cache.get(key)
            if entry and entry[0] > time.monotonic():
                self.cache.move_to_end(key)
                return entry[1]
            response = await self._request(path, head, params)
            if len(response.content) <= 512_000:
                self.cache[key] = (time.monotonic() + 300, response)
                self.cache.move_to_end(key)
                if len(self.cache) > 128:
                    self.cache.popitem(last=False)
            return response

    async def _request(self, path: str, head: bool, params: dict) -> httpx.Response:
        async with self.slots:
            wait = math.ceil(self.resume_at - time.monotonic())
            if wait > 0:
                raise GitHubError(429, "GitHub's request limit has been reached.", wait)
            try:
                response = await self.http.request("HEAD" if head else "GET", path, params=params)
            except httpx.TimeoutException:
                raise GitHubError(
                    504, "GitHub took too long to respond. Please try again."
                ) from None
            except httpx.RequestError:
                raise GitHubError(502, "GitHub could not be reached. Please try again.") from None
            status = response.status_code
            headers = response.headers
            remaining = headers.get("x-ratelimit-remaining")
            reset = headers.get("x-ratelimit-reset", "")
            if remaining == "0" and reset.isdigit():
                until_reset = max(1, int(reset) - int(time.time()))
                self.resume_at = max(self.resume_at, time.monotonic() + until_reset)
            limited = status == 403 and (
                remaining == "0"
                or "retry-after" in headers
                or "rate limit" in response.text[:500].lower()
            )
            if status == 429 or limited:
                delay = 60
                retry = headers.get("retry-after", "")
                if retry.isdigit():
                    delay = max(1, int(retry))
                if reset.isdigit() and remaining == "0":
                    delay = max(
                        math.ceil(self.resume_at - time.monotonic()),
                        int(retry) if retry.isdigit() else 1,
                    )
                self.resume_at = max(self.resume_at, time.monotonic() + delay)
                raise GitHubError(429, "GitHub's request limit has been reached.", delay)
            if status == 404:
                raise GitHubError(404, "GitHub could not find this public resource.")
            if status == 409:
                if "repository is empty" in response.text.lower():
                    raise GitHubError(409, "The Git repository is empty.")
                raise GitHubError(409, "GitHub reports a repository conflict.")
            if status in (401, 403):
                raise GitHubError(
                    503, "GitHub denied access. Check the server's GitHub configuration."
                )
            if status != 200:
                raise upstream_error()
            return response

    async def profile(self, username: str) -> Profile:
        response = await self.request(f"/users/{username}")
        try:
            return Profile.model_validate(response.json())
        except ValueError:
            raise upstream_error() from None

    async def repositories(self, username: str) -> RepositoryList:
        items = {}
        for page in range(1, MAX_PAGES + 1):
            try:
                response = await self.request(
                    f"/users/{username}/repos",
                    type="owner",
                    sort="full_name",
                    direction="asc",
                    per_page=100,
                    page=page,
                )
                for item in public_page(response, username):
                    items[item.name.casefold()] = item
            except GitHubError as exc:
                if page == 1:
                    raise
                return RepositoryList(
                    items=list(items.values()),
                    complete=False,
                    warnings=[f"Repository listing stopped before page {page}. {exc.message}"],
                )
            if "next" not in response.links:
                return RepositoryList(items=list(items.values()), complete=True)
        return RepositoryList(
            items=list(items.values()),
            complete=False,
            warnings=[f"Showing the first {MAX_PAGES} GitHub pages of repositories."],
        )


def public_page(response: httpx.Response, username: str) -> list[Repository]:
    """Validate the whole page before committing its records to the listing."""
    try:
        rows = response.json()
        if not isinstance(rows, list):
            raise upstream_error()
        return [
            Repository.model_validate({**row, "license_id": (row.get("license") or {}).get("key")})
            for row in rows
            if row["private"] is False and row["owner"]["login"].casefold() == username.casefold()
        ]
    except (KeyError, AttributeError, TypeError, ValueError):
        raise upstream_error() from None
