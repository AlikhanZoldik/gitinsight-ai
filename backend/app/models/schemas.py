from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

Username = Annotated[
    str, StringConstraints(min_length=1, max_length=39, pattern=r"^[A-Za-z0-9]+(-[A-Za-z0-9]+)*$")
]


class Profile(BaseModel):
    login: str
    name: str | None = None
    bio: str | None = None
    location: str | None = None
    avatar_url: str
    html_url: str
    followers: int
    following: int
    public_repos: int


class Repository(BaseModel):
    name: str
    description: str | None = None
    language: str | None = None
    html_url: str
    stargazers_count: int
    forks_count: int
    open_issues_count: int = Field(
        description="GitHub's combined open issue and pull request count"
    )
    created_at: datetime
    updated_at: datetime
    pushed_at: datetime | None = None
    archived: bool
    fork: bool
    topics: list[str] = Field(default_factory=list)
    license_id: str | None = None


class RepositoryList(BaseModel):
    items: list[Repository]
    complete: bool
    warnings: list[str] = Field(default_factory=list)


class Language(BaseModel):
    name: str
    bytes: int
    percentage: float


class Analytics(BaseModel):
    repository_count: int
    repositories_complete: bool
    total_stars: int
    total_forks: int
    average_stars: float | None
    top_repositories: list[Repository]
    latest_push: datetime | None
    languages: list[Language]
    language_attempted: int
    language_analyzed: int
    warnings: list[str]


class Dashboard(BaseModel):
    profile: Profile
    repositories: RepositoryList
    analytics: Analytics


RepoName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.-]{1,100}$")]


class ComparedProfile(BaseModel):
    username: str
    profile: Profile | None = None
    analytics: Analytics | None = None
    error: str | None = None


class Comparison(BaseModel):
    profiles: list[ComparedProfile]


class Commit(BaseModel):
    sha: str
    message: str
    author: str | None
    committed_at: datetime | None


class Activity(BaseModel):
    repository: str
    commits: list[Commit]
    retrieved: int
    has_more: bool


class PortfolioRule(BaseModel):
    label: str
    rule: str
    matched: int
    checked: int
    percentage: float | None
    recommendation: str | None


class Insights(BaseModel):
    repository_count: int
    rules: list[PortfolioRule]
    warnings: list[str]
