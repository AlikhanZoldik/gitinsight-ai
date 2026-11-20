import api
import streamlit as st


def roadmap_task(key, problem, solution, benefit, difficulty, verify):
    with st.expander(problem):
        st.text(solution)
        st.text(f"Expected benefit · {benefit}")
        st.text(f"Difficulty · {difficulty}")
        st.text(f"Verify · {verify}")
        completed = st.session_state.setdefault("roadmap_progress", {})
        widget = "task_" + key
        if widget not in st.session_state:
            st.session_state[widget] = completed.get(key, False)
        completed[key] = st.checkbox("Marked complete in this session", key=widget)


def explorer(owner, items):
    if not items:
        st.info("No public repositories to inspect.")
        return []
    a, b = st.columns([2, 1])
    query = a.text_input("Search repositories", key=f"query_{owner}").strip().lower()
    language = b.selectbox(
        "Primary language",
        ["All languages", *sorted({r["language"] for r in items if r["language"]})],
        key=f"lang_{owner}",
    )
    rows = [
        r
        for r in items
        if query in r["name"].lower() and (language == "All languages" or r["language"] == language)
    ]
    if not rows:
        st.info("No repositories match these filters.")
        return []
    names = [r["name"] for r in rows]
    selected = st.selectbox("Inspect repository", names, key=f"repo_{owner}")
    row = next(r for r in rows if r["name"] == selected)
    st.text(row.get("description") or "No public description")
    st.caption(row.get("language") or "Language unavailable")
    root = f"repositories/{owner}/{selected}"
    if st.button("Prepare audit preview", type="primary"):
        st.session_state.pop("audit_preview", None)
        try:
            with st.spinner(
                "Reading the current commit, selecting files and checking portfolio signals…"
            ):
                st.session_state.audit_preview = (root, api.fetch(root + "/audit-preview"))
        except api.APIError as exc:
            st.error(str(exc))
    saved = st.session_state.get("audit_preview")
    if saved and saved[0] == root:
        display_preview(root, saved[1])
    return rows


def display_preview(root, p):
    identity = f"{root}/{p['commit']}"
    with st.container(border=True):
        st.subheader("Portfolio readiness")
        st.metric(
            "Evaluated criteria",
            f"{p['score']} / 100" if p["score"] is not None else "Not evaluated",
        )
        st.caption(
            "Weighted share of observed criteria among evaluable criteria. Each weight is shown below."
        )
        st.dataframe(
            [
                {
                    "Criterion": r["label"],
                    "Weight": r["weight"],
                    "Observation": {True: "Detected", False: "No match", None: "Not evaluated"}[
                        r["observed"]
                    ],
                }
                for r in p["rules"]
            ],
            hide_index=True,
            width="stretch",
        )
        for note in p["limitations"]:
            st.caption(note)
    st.subheader("AI review")
    st.caption(f"Commit {p['commit'][:12]} · {len(p['files'])} files · {p['bytes']:,} bytes")
    if p["files"]:
        st.code("\n".join(p["files"]), language=None)
    st.write("Run AI Audit sends the listed public files and portfolio checks to Google Gemini.")
    if st.button("Run AI Audit", type="primary", disabled=not p["files"]):
        st.session_state.pop("audit_report", None)
        try:
            with st.spinner("Checking the commit and requesting a validated Gemini review…"):
                st.session_state.audit_report = (
                    identity,
                    api.fetch(root + "/audit", body={"commit": p["commit"]})["review"],
                )
        except api.APIError as exc:
            st.error(str(exc))
    result = st.session_state.get("audit_report")
    findings = []
    if result and result[0] == identity:
        review = result[1]
        st.subheader("Gemini suggestions")
        st.text(review["summary"])
        findings = review["findings"]
        if not findings:
            st.info(
                "No grounded findings in the selected files. Coverage is limited to this sample."
            )
        for f in findings:
            with st.expander(f"{f['severity'].upper()} · {f['title']}"):
                st.text(
                    f"{f['file']} · Line {f['line'] or 'unverified'} · {f['confidence']} confidence"
                )
                st.code(f["evidence"])
                st.text(f["description"])
        for item in review["strengths"] + review["limitations"]:
            st.text(item)
    st.subheader("Improvement roadmap")
    for severity, label in [
        ("critical", "Critical fixes"),
        ("high", "High priority"),
        ("medium", "Medium priority"),
        ("low", "Optional enhancements"),
    ]:
        group = [f for f in findings if f["severity"] == severity]
        missing = [r for r in p["rules"] if r["observed"] is False] if severity == "low" else []
        if group or missing:
            st.markdown(f"**{label}**")
        for i, f in enumerate(group):
            roadmap_task(
                f"{identity}-{severity}-{f['file']}-{f['title']}-{i}",
                f["title"],
                f["recommendation"] + " · " + f["file"],
                f["benefit"],
                f["difficulty"],
                f["verification"],
            )
        for r in missing:
            roadmap_task(
                identity + r["label"],
                r["label"] + " · no match",
                r["action"],
                "Make this portfolio signal discoverable.",
                "Moderate"
                if r["label"] in {"Actions workflow", "Test file conventions"}
                else "Easy",
                "Inspect the repository and prepare a fresh preview after committing changes.",
            )
