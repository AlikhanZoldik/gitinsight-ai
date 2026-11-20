from pathlib import Path

import pandas as pd
import streamlit as st
from api import APIError, fetch, valid_username
from components.audit import explorer
from components.charts import languages, popularity
from components.details import show_activity, show_comparison, show_insights
from components.metrics import metrics, profile_card, repository_table

st.set_page_config(page_title="GitInsight AI · Portfolio analytics", page_icon="◩", layout="wide")
style = (Path(__file__).parent / "styles/custom.css").read_text(encoding="utf-8")
st.html(f"<style>{style}</style>")

PAGES = {
    "Overview": "dashboard",
    "Repositories": "folder_open",
    "Repository Audit": "policy",
    "Languages": "data_usage",
    "Activity": "timeline",
    "Compare Developers": "compare_arrows",
    "Portfolio Insights": "fact_check",
}
with st.sidebar:
    st.html('<div class="brand"><span class="mark"><i></i><i></i><i></i></span>GitInsight AI</div>')
    page = st.radio(
        "Workspace",
        list(PAGES),
        format_func=lambda p: f":material/{PAGES[p]}: {p}",
        key="workspace_navigation",
    )
    st.divider()
    st.caption("Understand Your Code. Visualize Your Growth.")

st.title(page)
if page == "Compare Developers":
    try:
        show_comparison(st.session_state.get("username", "octocat"))
    except APIError as exc:
        st.error(str(exc))
    st.stop()
with st.form("profile_search"):
    left, right = st.columns([4, 1], vertical_alignment="bottom")
    name = left.text_input(
        "GitHub username",
        value=st.session_state.get("username", "octocat"),
        placeholder="Enter a GitHub username",
    ).strip()
    submitted = right.form_submit_button(
        "Analyze", icon=":material/search:", type="primary", width="stretch"
    )

if submitted or "username" not in st.session_state:
    if not valid_username(name):
        st.error("Enter 1–39 letters, numbers, or single hyphens between letters or numbers.")
        st.stop()
    st.session_state.username = name
    st.session_state.pop("dashboard", None)
    try:
        with st.spinner(f"Reading @{name} from GitHub…"):
            st.session_state.dashboard = fetch(f"users/{name}/dashboard")
    except APIError as exc:
        st.error(str(exc))
        st.stop()

if "dashboard" not in st.session_state:
    st.info("Use Analyze to load a public profile.")
    st.stop()

snapshot = st.session_state.dashboard
profile, data = snapshot["profile"], snapshot["analytics"]
items = snapshot["repositories"]["items"]
profile_card(profile)
for warning in data["warnings"]:
    st.warning(warning)

if page == "Overview":
    metrics(profile, data)
    a, b = st.columns(2)
    with a.container(border=True):
        st.subheader("Language distribution")
        languages(data)
    with b.container(border=True):
        st.subheader("Repository popularity")
        popularity(data)
    st.subheader("Repositories")
    repository_table(items)
    with st.container(border=True):
        st.subheader("Portfolio insights")
        described = sum(bool((r["description"] or "").strip()) for r in items)
        st.write(f"{described} of {len(items)} listed repositories have a description.")
        st.caption("Open Portfolio Insights for README, license, topic, and root test-file checks.")
elif page in {"Repositories", "Repository Audit"}:
    rows = explorer(profile["login"], items)
    if page == "Repositories" and rows:
        repository_table(rows)
elif page == "Languages":
    with st.container(border=True):
        st.subheader("Language distribution")
        languages(data)
    if data["languages"]:
        table = pd.DataFrame(data["languages"]).rename(
            columns={"name": "Language", "bytes": "Reported bytes", "percentage": "Share (%)"}
        )
        st.dataframe(
            table,
            hide_index=True,
            width="stretch",
            column_config={"Share (%)": st.column_config.NumberColumn(format="%.2f")},
        )
    st.caption(
        "Percentages weight GitHub-reported bytes across the most recently updated repositories in the sample. They describe repository contents."
    )
else:
    try:
        if page == "Activity":
            show_activity(profile["login"], items)
        else:
            show_insights(profile["login"])
    except APIError as exc:
        st.error(str(exc))
