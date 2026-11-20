from html import escape
from urllib.parse import urlsplit

import pandas as pd
import streamlit as st


def profile_card(p: dict):
    login = escape(p["login"])
    avatar = p["avatar_url"]
    image = ""
    if urlsplit(avatar).hostname == "avatars.githubusercontent.com":
        image = f'<img alt="" src="{escape(avatar, quote=True)}">'
    location = f" &nbsp;·&nbsp; {escape(p['location'])}" if p["location"] else ""
    bio = f"<p>{escape(p['bio'])}</p>" if p["bio"] else ""
    st.html(f"""<section class="profile">{image}<div><a href="https://github.com/{login}" target="_blank" rel="noopener noreferrer">@{login} ↗</a>
        <h2>{escape(p["name"] or p["login"])}</h2>{bio}
        <small>{p["followers"]:,} followers &nbsp;·&nbsp; {p["following"]:,} following{location}</small></div></section>""")


def metrics(profile: dict, data: dict):
    avg = data["average_stars"]
    values = [
        ("Public repositories", f"{profile['public_repos']:,}", "GitHub profile count"),
        ("Total stars", f"{data['total_stars']:,}", "Across listed repositories"),
        ("Total forks", f"{data['total_forks']:,}", "Across listed repositories"),
        ("Average stars", f"{avg:,.1f}" if avg is not None else "—", "Per listed repository"),
    ]
    for col, (label, value, note) in zip(st.columns(4), values):
        col.html(
            f'<div class="metric"><span>{label}</span><strong>{value}</strong><small>{note}</small></div>'
        )


def repository_table(items: list[dict]):
    if not items:
        st.info("This profile has no listed public repositories.")
        return
    order = st.selectbox(
        "Sort repositories", ["Most stars", "Recently updated", "Most forks", "Alphabetical"]
    )
    keys = {
        "Most stars": "stargazers_count",
        "Recently updated": "updated_at",
        "Most forks": "forks_count",
    }
    rows = sorted(items, key=lambda r: r["name"].casefold())
    if order in keys:
        rows.sort(key=lambda r: r[keys[order]], reverse=True)
    frame = pd.DataFrame(rows).rename(
        columns={
            "html_url": "Repository",
            "language": "Language",
            "stargazers_count": "Stars",
            "forks_count": "Forks",
            "open_issues_count": "Issues + PRs",
            "updated_at": "Updated (UTC)",
            "pushed_at": "Pushed (UTC)",
            "created_at": "Created (UTC)",
            "description": "Description",
            "archived": "Archived",
        }
    )
    for key in ("Updated (UTC)", "Pushed (UTC)", "Created (UTC)"):
        frame[key] = pd.to_datetime(frame[key], utc=True).dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(
        frame[
            [
                "Repository",
                "Language",
                "Stars",
                "Forks",
                "Issues + PRs",
                "Updated (UTC)",
                "Pushed (UTC)",
                "Created (UTC)",
                "Archived",
                "Description",
            ]
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "Repository": st.column_config.LinkColumn(display_text=r"https://github.com/[^/]+/(.*)")
        },
    )
    st.caption(
        "Updated includes repository metadata changes. Pushed records the latest code push. GitHub counts open issues and pull requests together."
    )
