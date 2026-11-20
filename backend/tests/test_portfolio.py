import httpx

from backend.app.models.schemas import Activity, Comparison, Insights


def test_comparison_keeps_owners_metrics_separate(api, profile, repository):
    def serve(req):
        path = req.url.path
        username = path.split("/")[2]
        if path == f"/users/{username}":
            return httpx.Response(200, json=dict(profile, login=username))
        if path.endswith("/repos"):
            stars, forks = (4, 1) if username == "alice" else (10, 3)
            row = dict(
                repository, owner={"login": username}, stargazers_count=stars, forks_count=forks
            )
            return httpx.Response(200, json=[row])
        language = "Ruby" if username == "alice" else "Go"
        return httpx.Response(200, json={language: 20})

    with api(serve) as test:
        result = Comparison.model_validate(
            test.get("/api/v1/compare", params={"user1": "alice", "user2": "bob"}).json()
        )
        assert [
            (
                side.username,
                side.analytics.total_stars,
                side.analytics.total_forks,
                side.analytics.languages[0].name,
            )
            for side in result.profiles
        ] == [("alice", 4, 1, "Ruby"), ("bob", 10, 3, "Go")]


def test_comparison_partial_and_cached(api, profile, repository):
    calls = []

    def serve(req):
        calls.append(req.url.path)
        if req.url.path.endswith("missing"):
            return httpx.Response(404)
        if req.url.path.endswith("alice"):
            return httpx.Response(200, json=profile)
        if req.url.path.endswith("/repos"):
            return httpx.Response(200, json=[repository])
        return httpx.Response(503)

    with api(serve) as test:
        route = "/api/v1/compare?user1=alice&user2=missing"
        for _ in range(2):
            data = Comparison.model_validate(test.get(route).json())
            left, right = data.profiles
            assert left.analytics.repository_count == 1 and left.analytics.language_analyzed == 0
            assert left.analytics.warnings and right.error and right.analytics is None
        assert calls.count("/users/alice") == 1
        assert calls.count("/repos/alice/sample/languages") == 2


def test_activity(api, repository):
    def serve(req):
        if req.url.path.endswith("/repos"):
            return httpx.Response(200, json=[repository])
        assert req.url.params["per_page"] == "30"
        return httpx.Response(
            200,
            json=[
                {
                    "sha": "abc",
                    "commit": {
                        "message": "Subject\nBody",
                        "author": {"name": "Another author"},
                        "committer": {"date": "2020-02-01T00:00:00Z"},
                    },
                }
            ],
            headers={"Link": '<https://api.github.com/more>; rel="next"'},
        )

    with api(serve) as test:
        data = Activity.model_validate(test.get("/api/v1/users/alice/activity?repo=sample").json())
        assert data.retrieved == 1 and data.has_more
        assert data.commits[0].message == "Subject" and data.commits[0].author == "Another author"
        assert test.get("/api/v1/users/alice/activity?repo=private").status_code == 404


def test_insights_excludes_unavailable(api, repository):
    def serve(req):
        if req.url.path.endswith("/repos"):
            return httpx.Response(
                200,
                json=[
                    dict(repository, description="A project", topics=["cli"]),
                    dict(repository, name="other"),
                ],
            )
        if req.url.path.endswith("/readme"):
            assert req.method == "HEAD"
            return httpx.Response(404 if "other" in req.url.path else 200)
        if "other" in req.url.path:
            return httpx.Response(500)
        return httpx.Response(200, json=[{"name": "test_api.py", "type": "file"}])

    with api(serve) as test:
        data = Insights.model_validate(test.get("/api/v1/users/alice/insights").json())
        rules = {r.label: r for r in data.rules}
        assert (
            rules["READMEs"].percentage
            == rules["Descriptions"].percentage
            == rules["Topics"].percentage
            == 50
        )
        assert rules["Licenses"].percentage == 0 and rules["READMEs"].recommendation
        assert rules["Root test files"].matched == rules["Root test files"].checked == 1
        assert data.warnings
