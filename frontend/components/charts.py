import plotly.graph_objects as go
import streamlit as st

COLORS = ["#8bb7ff", "#ab9ce8", "#e7b878", "#78b9d2", "#d999ac", "#8fafa1", "#8690cb"]


def chart(fig: go.Figure, height: int = 240, key: str | None = None):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cbd5cd", family="Inter, sans-serif", size=12),
        margin=dict(l=4, r=12, t=12, b=25),
        height=height,
        hoverlabel=dict(bgcolor="#27352c", font_color="white"),
    )
    st.plotly_chart(
        fig,
        width="stretch",
        theme=None,
        key=key,
        config={"displayModeBar": False, "responsive": True},
    )


def languages(data: dict, key: str | None = None):
    values = data["languages"]
    st.caption(
        f"Reported bytes · {data['language_analyzed']} of {data['repository_count']} listed repositories analyzed"
    )
    if not values:
        st.info("No language bytes were available for this sample.")
        return
    shown = values[:5]
    labels = [row["name"] for row in shown]
    sizes = [row["bytes"] for row in shown]
    if len(values) > 5:
        labels.append("Other languages")
        sizes.append(sum(row["bytes"] for row in values[5:]))
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=sizes,
            hole=0.73,
            sort=False,
            direction="clockwise",
            textinfo="none",
            marker=dict(colors=COLORS, line=dict(color="#181e1a", width=3)),
            hovertemplate="%{label}<br>%{value:,} bytes · %{percent}<extra></extra>",
        )
    )
    fig.update_layout(
        legend=dict(orientation="v", y=0.5, x=0.66),
        annotations=[
            dict(
                text=f"<b>{len(values)}</b>",
                font_size=29,
                x=0.30,
                y=0.5,
                xanchor="center",
                showarrow=False,
                xref="paper",
                yref="paper",
            )
        ],
    )
    fig.update_traces(domain=dict(x=[0, 0.6]))
    chart(fig, key=key)


def popularity(data: dict):
    rows = data["top_repositories"][::-1]
    st.caption("Top five listed repositories by stars")
    if not rows:
        st.info("No repositories to rank.")
        return
    fig = go.Figure(
        go.Bar(
            x=[r["stargazers_count"] for r in rows],
            y=[r["name"] for r in rows],
            orientation="h",
            marker_color="#a99bd8",
            width=0.48,
            text=[f"{r['stargazers_count']:,}" for r in rows],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}<br>%{x:,} stars<extra></extra>",
        )
    )
    maximum = max(r["stargazers_count"] for r in rows)
    fig.update_xaxes(
        range=[0, max(1, maximum * 1.35)], showgrid=True, gridcolor="#2b342e", zeroline=False
    )
    fig.update_yaxes(type="category", automargin=True, ticksuffix="  ")
    chart(fig)
