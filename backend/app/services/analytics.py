import asyncio
from collections import Counter
from urllib.parse import quote

from backend.app.clients.github_client import GitHubClient, upstream_error
from backend.app.config import DETAIL_LIMIT
from backend.app.models.schemas import Analytics, Language, Repository, RepositoryList
from backend.app.utils.errors import GitHubError


def detail_sample(repos: list[Repository]) -> list[Repository]:
    return sorted(repos, key=lambda r: (-r.updated_at.timestamp(), r.name.casefold()))[
        :DETAIL_LIMIT
    ]


def language_distribution(samples: list[dict[str, int]]) -> list[Language]:
    counts = Counter()
    for sample in samples:
        counts.update(sample)
    total = counts.total()
    return [
        Language(name=name, bytes=size, percentage=100 * size / total)
        for name, size in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
        if size > 0
    ]


def summarize(
    repos: RepositoryList, samples: list[dict[str, int]], attempted: int, warnings: list[str]
) -> Analytics:
    items = repos.items
    stars = sum(r.stargazers_count for r in items)
    return Analytics(
        repository_count=len(items),
        repositories_complete=repos.complete,
        total_stars=stars,
        total_forks=sum(r.forks_count for r in items),
        average_stars=stars / len(items) if items else None,
        latest_push=max((r.pushed_at for r in items if r.pushed_at), default=None),
        top_repositories=sorted(items, key=lambda r: (-r.stargazers_count, r.name.casefold()))[:5],
        languages=language_distribution(samples),
        language_attempted=attempted,
        language_analyzed=len(samples),
        warnings=[*repos.warnings, *warnings],
    )


async def analytics(
    github: GitHubClient, username: str, repos: RepositoryList | None = None
) -> Analytics:
    if repos is None:
        repos = await github.repositories(username)
    selected = detail_sample(repos.items)

    async def languages(repo: Repository):
        try:
            response = await github.request(
                f"/repos/{username}/{quote(repo.name, safe='')}/languages"
            )
            data = response.json()
            if not isinstance(data, dict) or any(
                type(v) is not int or v < 0 for v in data.values()
            ):
                raise upstream_error()
            return data
        except ValueError:
            return upstream_error()
        except GitHubError as exc:
            return exc

    results = await asyncio.gather(*(languages(repo) for repo in selected))
    warnings = [
        f"{repo.name} language statistics unavailable. {result.message}"
        for repo, result in zip(selected, results)
        if isinstance(result, GitHubError)
    ]
    return summarize(repos, [r for r in results if isinstance(r, dict)], len(selected), warnings)
