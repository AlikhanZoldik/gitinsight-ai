import time

import httpx
import pytest

from backend.app.models.schemas import RepositoryList


def test_pagination(api, repository):
    pages = []

    def serve(req):
        pages.append(req.url.params["page"])
        if pages == ["1"]:
            return httpx.Response(
                200,
                json=[repository],
                headers={"Link": '<https://api.github.com/next>; rel="next"'},
            )
        assert req.url.host == "api.github.com"
        return httpx.Response(200, json=[dict(repository, name="other")])

    with api(serve) as test:
        data = RepositoryList.model_validate(test.get("/api/v1/users/alice/repositories").json())
        assert data.complete and len(data.items) == 2
        assert pages == ["1", "2"]


def test_timeout(api):
    def serve(req):
        raise httpx.ReadTimeout("secret diagnostics", request=req)

    with api(serve) as test:
        result = test.get("/api/v1/users/alice")
        assert result.status_code == 504 and "secret" not in result.text


@pytest.mark.parametrize("status", [403, 429])
def test_rate_limit_blocks_further_calls(api, status):
    calls = []

    def serve(req):
        calls.append(req)
        return httpx.Response(status, headers={"Retry-After": "90"})

    with api(serve) as test:
        for name in ("alice", "bob"):
            result = test.get(f"/api/v1/users/{name}")
            assert result.status_code == 429
            assert 1 <= int(result.headers["Retry-After"]) <= 90
        assert len(calls) == 1


def test_partial_list(api, repository):
    def serve(req):
        if req.url.params["page"] == "1":
            return httpx.Response(
                200,
                json=[repository],
                headers={"Link": '<https://api.github.com/next>; rel="next"'},
            )
        return httpx.Response(500)

    with api(serve) as test:
        data = test.get("/api/v1/users/alice/repositories").json()
        assert len(data["items"]) == 1 and data["warnings"] and not data["complete"]


def test_last_success_before_reset_stays_available(api, profile):
    calls = []

    def serve(req):
        calls.append(req)
        return httpx.Response(
            200,
            json=profile,
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(int(time.time()) + 60)},
        )

    with api(serve) as test:
        assert test.get("/api/v1/users/alice").status_code == 200
        assert test.get("/api/v1/users/bob").status_code == 429
        assert test.get("/api/v1/users/alice").status_code == 200
        assert len(calls) == 1
