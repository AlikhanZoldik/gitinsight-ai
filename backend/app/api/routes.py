import asyncio

from fastapi import APIRouter, Request

from backend.app.clients.github_client import GitHubClient
from backend.app.models.schemas import (
    Activity,
    Analytics,
    Comparison,
    Dashboard,
    Insights,
    Profile,
    RepoName,
    RepositoryList,
    Username,
)
from backend.app.services.analytics import analytics
from backend.app.services.portfolio import activity, compare_profile, insights

router = APIRouter(prefix="/api/v1")


def client(request: Request) -> GitHubClient:
    return request.app.state.github


@router.get("/users/{username}", summary="Read a public GitHub profile")
async def user(username: Username, request: Request) -> Profile:
    return await client(request).profile(username)


@router.get(
    "/users/{username}/repositories",
    summary="List public owned repositories, with pagination coverage",
)
async def repositories(username: Username, request: Request) -> RepositoryList:
    return await client(request).repositories(username)


@router.get(
    "/users/{username}/analytics",
    summary="Aggregate repository popularity and sampled language bytes",
)
async def user_analytics(username: Username, request: Request) -> Analytics:
    return await analytics(client(request), username)


@router.get(
    "/users/{username}/dashboard", summary="Build the dashboard from one public repository listing"
)
async def dashboard(username: Username, request: Request) -> Dashboard:
    github = client(request)
    profile = await github.profile(username)
    repos = await github.repositories(username)
    return Dashboard(
        profile=profile, repositories=repos, analytics=await analytics(github, username, repos)
    )


@router.get(
    "/compare", summary="Compare two profiles, including available results when one side fails"
)
async def compare(user1: Username, user2: Username, request: Request) -> Comparison:
    sides = await asyncio.gather(
        *(compare_profile(client(request), name) for name in (user1, user2))
    )
    return Comparison(profiles=sides)


@router.get(
    "/users/{username}/activity", summary="Inspect up to 30 default-branch commits by any author"
)
async def user_activity(username: Username, repo: RepoName, request: Request) -> Activity:
    return await activity(client(request), username, repo)


@router.get(
    "/users/{username}/insights",
    summary="Explain portfolio metadata and sampled documentation checks",
)
async def user_insights(username: Username, request: Request) -> Insights:
    return await insights(client(request), username)
