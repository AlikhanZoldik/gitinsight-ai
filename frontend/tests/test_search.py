from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

FRONTEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def ui(monkeypatch):
    monkeypatch.syspath_prepend(str(FRONTEND))
    return AppTest.from_file(str(FRONTEND / "app.py"), default_timeout=30)


def test_error_and_invalid_search(ui):
    from api import APIError

    with patch(
        "api.fetch", side_effect=APIError("GitHub could not find this public resource.")
    ) as fetch:
        ui.run()
        assert "could not find" in ui.error[0].value
        ui.text_input[0].set_value(" ")
        ui.button[0].click().run()
        assert ui.error and fetch.call_count == 1 and not ui.exception


def test_empty_dashboard_and_navigation(ui):
    snapshot = {
        "profile": {
            "login": "alice",
            "name": None,
            "bio": None,
            "location": None,
            "avatar_url": "",
            "followers": 0,
            "following": 0,
            "public_repos": 0,
        },
        "analytics": {
            "warnings": [],
            "average_stars": None,
            "total_stars": 0,
            "total_forks": 0,
            "language_analyzed": 0,
            "repository_count": 0,
            "top_repositories": [],
            "languages": [],
        },
        "repositories": {"items": []},
    }
    with patch("api.fetch", return_value=snapshot) as fetch:
        ui.run()
        assert not ui.exception
        assert any("no listed public repositories" in item.value for item in ui.info)
        ui.radio[0].set_value("Activity").run()
        assert ui.info and not ui.exception and fetch.call_count == 1


def test_comparison_form_stores_results(ui):
    from api import APIError

    result = {
        "profiles": [
            {"username": name, "profile": None, "analytics": None, "error": "Unavailable"}
            for name in ("octocat", "alice")
        ]
    }
    with patch("api.fetch", side_effect=[APIError("Upstream unavailable"), result]):
        ui.run()
        ui.radio[0].set_value("Compare Developers").run()
        ui.text_input[1].set_value("alice")
        ui.button[0].click().run()
        assert not ui.exception
        assert len(ui.warning) == 2
        assert ui.session_state["comparison"] == result


def test_audit_submission_and_local_task(ui):
    def render():
        from components.audit import display_preview

        display_preview(
            "repositories/alice/project",
            {
                "commit": "abc",
                "files": ["app.py"],
                "bytes": 20,
                "score": 0,
                "rules": [
                    {
                        "label": "README",
                        "weight": 10,
                        "observed": False,
                        "action": "Document setup.",
                    }
                ],
                "limitations": [],
            },
        )

    app = AppTest.from_function(render)
    review = {"summary": "Checked the sample.", "findings": [], "strengths": [], "limitations": []}
    with patch("api.fetch", return_value={"review": review}) as fetch:
        app.run()
        app.button[0].click().run()
        fetch.assert_called_once_with("repositories/alice/project/audit", body={"commit": "abc"})
        app.checkbox[0].check().run()
        assert not app.exception
        assert any(app.session_state["roadmap_progress"].values())
        assert fetch.call_count == 1
