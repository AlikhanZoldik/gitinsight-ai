import httpx
import pytest

from backend.app.models.schemas import Analytics, Repository, RepositoryList
from backend.app.services.analytics import language_distribution, summarize


def test_language_weights():
    result = language_distribution([{"Python": 1}, {"Python": 2, "Go": 1}, {}])
    assert [(r.name, r.bytes, r.percentage) for r in result] == [("Python", 3, 75), ("Go", 1, 25)]
    assert language_distribution([{"C": 0}, {}]) == []


def test_empty():
    data = summarize(RepositoryList(items=[], complete=True), [], 0, [])
    assert data.total_stars == data.total_forks == data.repository_count == 0
    assert data.average_stars is None and data.top_repositories == []


def test_zero_and_ranking(repository):
    item = Repository.model_validate(repository)
    listing = RepositoryList(items=[item], complete=True)
    assert summarize(listing, [], 0, []).average_stars == 0
    listing.items += [item.model_copy(update={"name": "b", "stargazers_count": 8})]
    metrics = summarize(listing, [], 0, [])
    assert (metrics.total_stars, metrics.total_forks, metrics.average_stars) == (8, 4, 4)
    assert metrics.top_repositories[0].name == "b"


@pytest.mark.parametrize("status,analyzed", [(200, 1), (500, 0)])
def test_missing_language_data(api, repository, status, analyzed):
    def serve(req):
        if req.url.path.endswith("/repos"):
            return httpx.Response(200, json=[repository])
        return httpx.Response(status, json={})

    with api(serve) as test:
        result = test.get("/api/v1/users/alice/analytics")
        assert result.status_code == 200
        data = Analytics.model_validate(result.json())
        assert data.language_attempted == 1 and data.language_analyzed == analyzed
        assert data.languages == [] and bool(data.warnings) == (status != 200)
