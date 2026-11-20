from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.clients.github_client import GitHubClient
from backend.app.main import app


@pytest.fixture
def api():
    @contextmanager
    def open_api(handler):
        with TestClient(app) as test:
            upstream = httpx.AsyncClient(
                base_url="https://api.github.com", transport=httpx.MockTransport(handler)
            )
            app.state.github = GitHubClient(upstream)
            try:
                yield test
            finally:
                test.portal.call(upstream.aclose)

    return open_api


@pytest.fixture
def profile():
    return dict(
        login="alice",
        avatar_url="https://avatars.githubusercontent.com/u/1",
        html_url="https://github.com/alice",
        public_repos=1,
        followers=2,
        following=0,
    )


@pytest.fixture
def repository():
    return dict(
        name="sample",
        html_url="https://github.com/alice/sample",
        private=False,
        owner={"login": "alice"},
        stargazers_count=0,
        forks_count=2,
        open_issues_count=3,
        created_at="2020-01-01T00:00:00Z",
        updated_at="2021-01-01T00:00:00Z",
        archived=False,
        fork=False,
    )
