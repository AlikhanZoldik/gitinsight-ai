# GitInsight 1.0 baseline review

The existing FastAPI, Streamlit, GitHub integration, analytics, comparison, CI and two-container deployment are retained. The running dashboard and its desktop/mobile verification were inspected before the upgrade.

| Severity | Evidence | Upgrade decision |
|---|---|---|
| Critical | No confirmed critical defect in the existing flows. | Preserve the existing regression suite. |
| High | Existing GitHub request paths can use a configured token. Adding arbitrary repository paths without a fresh visibility check could disclose private content. | Check visibility and canonical name before reading audit files. |
| High | Existing API has no paid-provider request budget. | Serialize and cap Gemini calls, keep keys on the backend. |
| Medium | Repository updates and metadata can be cached for five minutes. Root-only test detection misses nested projects. | Resolve current commit for each audit and inspect its recursive tree. |
| Medium | Explorer only sorts. Existing error rendering expects a JSON object. | Add search, language filtering, audit selection and robust API errors. |
| Low | Username validation exists in both services. The previous visual palette uses green surfaces throughout. | Keep independent client/server validation and refine the dashboard theme. |

New coverage is needed for snapshot selection, secret exclusions, provider errors, evidence grounding, scoring and the audit journey. No dependency vulnerability scan was part of this baseline.

## Upgrade verification

The baseline suite passed 24 tests. The upgraded suite passed 44, including a mocked structured Gemini review, transient and permanent provider failures, commit changes, private-repository rejection, cache reuse and local roadmap interaction. Ruff lint and formatting passed.

The browser verification used the live public octocat account. It exercised overview charts, repository sorting, repository name filtering, audit preview, the missing-key response, language distribution, commit activity, portfolio insights, comparison and a 390-pixel mobile overview. The screenshots in the README were captured during this run. A live Gemini generation still requires operator credentials and an available model.

A PyPI advisory lookup covered 57 installed Python package versions across both images. It identified advisories for the base image's pip 25.0.1. Both Dockerfiles upgrade pip to 26.3, whose PyPI release metadata returned no advisories during verification. This check covers Python package advisories only.
