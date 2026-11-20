import asyncio
import re
from urllib.parse import quote

from backend.app.clients.github_client import GitHubClient, upstream_error
from backend.app.models.schemas import Activity, Commit, ComparedProfile, Insights, PortfolioRule
from backend.app.services.analytics import analytics, detail_sample
from backend.app.utils.errors import GitHubError


async def compare_profile(github: GitHubClient, username: str) -> ComparedProfile:
    side = ComparedProfile(username=username)
    try:
        side.profile = await github.profile(username)
        side.analytics = await analytics(github, username)
    except GitHubError as exc:
        side.error = exc.message
    return side


async def activity(github: GitHubClient, username: str, repo: str) -> Activity:
    # Only repository names in the public owner listing can reach the detail endpoint.
    repos = await github.repositories(username)
    found = next((r for r in repos.items if r.name.casefold() == repo.casefold()), None)
    if found is None:
        raise GitHubError(404, "Repository was not found in the analyzed public listing.")
    result = Activity(repository=found.name, commits=[], retrieved=0, has_more=False)
    try:
        response = await github.request(
            f"/repos/{username}/{quote(found.name, safe='')}/commits", per_page=30, page=1
        )
    except GitHubError as exc:
        if exc.status == 409 and exc.message == "The Git repository is empty.":
            return result
        raise
    try:
        rows = response.json()
        if not isinstance(rows, list):
            raise upstream_error()
        for row in rows:
            info = row["commit"]
            result.commits.append(
                Commit(
                    sha=row["sha"],
                    message=info["message"].partition("\n")[0],
                    author=(info.get("author") or {}).get("name"),
                    committed_at=(info.get("committer") or {}).get("date"),
                )
            )
    except (KeyError, TypeError, ValueError, AttributeError):
        raise upstream_error() from None
    result.has_more = "next" in response.links
    result.retrieved = len(result.commits)
    return result


def rule(
    label: str, description: str, observations: list[bool], suggestion: str | None
) -> PortfolioRule:
    checked = len(observations)
    matched = sum(observations)
    return PortfolioRule(
        label=label,
        rule=description,
        matched=matched,
        checked=checked,
        percentage=100 * matched / checked if checked else None,
        recommendation=suggestion if matched < checked else None,
    )


async def insights(github: GitHubClient, username: str) -> Insights:
    repos = await github.repositories(username)
    items = repos.items
    warnings = list(repos.warnings)

    async def inspect(name: str, resource: str):
        try:
            response = await github.request(
                f"/repos/{username}/{quote(name, safe='')}/{resource}", head=resource == "readme"
            )
            if resource == "readme":
                return True
            files = response.json()
            if not isinstance(files, list):
                raise upstream_error()
            return any(
                f["type"] == "file"
                and re.search(
                    r"(^test_.+\.py$|_test\.(py|go)$|\.(test|spec)\.[cm]?[jt]sx?$)", f["name"]
                )
                for f in files
            )
        except GitHubError as exc:
            if resource == "readme" and exc.status == 404:
                return False
            warnings.append(f"{name} {resource} check unavailable. {exc.message}")
        except (TypeError, KeyError, ValueError):
            warnings.append(f"{name} {resource} check returned unexpected data.")
        return None

    selected = detail_sample(items)
    readmes, tests = await asyncio.gather(
        *(
            asyncio.gather(*(inspect(r.name, resource) for r in selected))
            for resource in ("readme", "contents")
        )
    )
    rules = [
        rule(
            "Descriptions",
            "A nonblank description on a listed repository.",
            [bool((r.description or "").strip()) for r in items],
            "Add a short description explaining the purpose of repositories that have none.",
        ),
        rule(
            "Topics",
            "At least one GitHub topic on a listed repository.",
            [bool(r.topics) for r in items],
            "Add relevant topics so visitors can find related work.",
        ),
        rule(
            "Licenses",
            "GitHub reports a license on a listed repository.",
            [bool(r.license_id) for r in items],
            "Review the licensing terms for repositories without a detected license.",
        ),
        rule(
            "READMEs",
            "GitHub's preferred README endpoint succeeds for a sampled repository.",
            [x for x in readmes if x is not None],
            "Add a README with setup and usage instructions where one is missing.",
        ),
        rule(
            "Root test files",
            "A sampled root listing contains a Python, Go, or JavaScript/TypeScript test filename. Tests in subdirectories and test execution are outside this check.",
            [x for x in tests if x is not None],
            None,
        ),
    ]
    return Insights(repository_count=len(items), rules=rules, warnings=sorted(warnings))
