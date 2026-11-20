import api
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from components.charts import chart, languages


def show_insights(username: str):
    with st.spinner("Checking public repository metadata and documentation…"):
        data = api.fetch(f"users/{username}/insights")
    st.caption(
        f"{data['repository_count']} repositories listed. Each percentage uses successfully checked repositories for that rule."
    )
    for row in data["rules"]:
        with st.container(border=True):
            st.subheader(row["label"])
            pct = row["percentage"]
            if pct is None:
                st.caption("No repositories could be checked.")
            else:
                st.progress(
                    pct / 100, text=f"{row['matched']} of {row['checked']} checked · {pct:.0f}%"
                )
            st.caption(row["rule"])
            if row["recommendation"]:
                st.write(row["recommendation"])
    for warning in data["warnings"]:
        st.warning(warning)


def show_activity(username: str, items: list[dict]):
    if not items:
        st.info("No public repositories are available for activity analysis.")
        return
    selected = st.selectbox("Repository", [r["name"] for r in items])
    with st.spinner("Reading default-branch commits…"):
        data = api.fetch(f"users/{username}/activity", repo=selected)
    st.subheader(f"{data['retrieved']} commits retrieved")
    st.caption("Latest 30 default-branch commits by all authors, grouped by UTC committer date.")
    if data["has_more"]:
        st.caption("GitHub reports additional commits beyond this sample.")
    if not data["commits"]:
        st.info("This repository returned no commits.")
        return
    frame = pd.DataFrame(data["commits"])
    frame["committed_at"] = pd.to_datetime(frame["committed_at"], utc=True)
    counts = frame["committed_at"].dt.date.value_counts().sort_index()
    if not counts.empty:
        fig = go.Figure(
            go.Bar(
                x=counts.index,
                y=counts.values,
                marker_color="#96dfa9",
                hovertemplate="%{x}<br>%{y} commits<extra></extra>",
            )
        )
        fig.update_yaxes(title="Retrieved commits", dtick=1 if counts.max() < 6 else None)
        chart(fig)
    st.dataframe(
        frame.rename(
            columns={
                "sha": "SHA",
                "author": "Author",
                "message": "Subject",
                "committed_at": "Committed (UTC)",
            }
        ),
        hide_index=True,
        width="stretch",
    )


def show_comparison(username: str):
    st.caption(
        "Compare public repository data. These measures cover only visible projects and activity."
    )
    with st.form("comparison_search"):
        a, b, c = st.columns([2, 2, 1], vertical_alignment="bottom")
        first = a.text_input("First developer", username).strip()
        second = b.text_input("Second developer", placeholder="GitHub username").strip()
        submitted = c.form_submit_button("Compare", width="stretch", type="primary")
    if submitted:
        if not all(api.valid_username(name) for name in (first, second)):
            st.error("Enter two valid GitHub usernames.")
            return
        with st.spinner("Comparing public repositories…"):
            st.session_state.comparison = api.fetch("compare", user1=first, user2=second)
    if "comparison" not in st.session_state:
        return
    for index, (col, side) in enumerate(
        zip(st.columns(2), st.session_state.comparison["profiles"])
    ):
        with col.container(border=True):
            st.subheader(f"@{side['username']}")
            if side["error"]:
                st.warning(side["error"])
            if side["profile"]:
                st.metric("Public repositories", side["profile"]["public_repos"])
            data = side["analytics"]
            if data is None:
                continue
            st.caption(f"{data['repository_count']} public repositories listed")
            a, b = st.columns(2)
            a.metric("Stars", f"{data['total_stars']:,}")
            b.metric("Forks", f"{data['total_forks']:,}")
            st.write("Latest listed code push")
            st.text(data["latest_push"] or "Unavailable")
            st.write("Top languages")
            languages(data, key=f"comparison_languages_{index}")
            for warning in data["warnings"]:
                st.warning(warning)
