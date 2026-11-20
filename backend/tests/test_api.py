import httpx
import pytest

from backend.app.models.schemas import Profile


def test_valid_profile(api, profile):
    with api(lambda req: httpx.Response(200, json=profile)) as test:
        response = test.get("/api/v1/users/alice")
        assert response.status_code == 200
        assert Profile.model_validate(response.json()).login == "alice"
        assert test.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("name", ["a--b", "-leading", "bad_name", "a" * 40])
def test_invalid_username(api, name):
    with api(lambda req: pytest.fail("Unexpected upstream call")) as test:
        assert test.get(f"/api/v1/users/{name}").status_code == 422


def test_missing_profile(api):
    with api(lambda req: httpx.Response(404)) as test:
        assert test.get("/api/v1/users/missing").status_code == 404
