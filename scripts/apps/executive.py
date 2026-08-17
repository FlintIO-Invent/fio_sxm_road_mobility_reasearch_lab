from __future__ import annotations

from datetime import datetime
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

EXECUTIVE_CSS = """
<style>
    :root {
        --ink: #0b0f19;
        --ink-soft: #33354d;
        --muted: #565973;
        --paper: #f3f6ff;
        --card: #ffffff;
        --line: #e2e5f1;
        --primary: #6366f1;
        --primary-dark: #3e41ee;
        --primary-soft: #eff0fe;
        --violet: #8b5cf6;
        --navy: #080d1a;
    }

    .stApp {
        background:
            radial-gradient(circle at 86% 4%, rgba(99, 102, 241, 0.09), transparent 26rem),
            var(--paper);
        color: var(--ink);
    }

    .stApp,
    .stApp button,
    .stApp input,
    .stApp textarea {
        font-family: "Manrope", "Inter", "Aptos", sans-serif;
    }

    [data-testid="stAppViewContainer"] > .main {
        background: transparent;
    }

    .block-container {
        max-width: 1240px;
        padding-top: 2.6rem;
        padding-bottom: 4rem;
    }

    [data-testid="stSidebar"] {
        background: var(--navy);
        border-right: 0;
    }

    [data-testid="stSidebar"] * {
        color: #f3f6ff;
    }

    [data-testid="stSidebarNav"] span,
    [data-testid="stSidebarNav"] a {
        font-size: 0.94rem;
    }

    [data-testid="stHeader"] {
        background: rgba(243, 246, 255, 0.88);
        backdrop-filter: blur(12px);
    }

    h1, h2, h3 {
        color: var(--ink);
        letter-spacing: -0.025em;
    }

    h2 {
        margin-top: 2.2rem;
    }

    p, li, label {
        color: var(--ink);
    }

    .exec-hero {
        background:
            radial-gradient(circle at 84% 15%, rgba(99, 102, 241, 0.38), transparent 25rem),
            radial-gradient(circle at 18% 88%, rgba(139, 92, 246, 0.16), transparent 22rem),
            var(--navy);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 20px;
        box-shadow: 0 18px 44px rgba(8, 13, 26, 0.14);
        margin: 0 0 1.05rem 0;
        overflow: hidden;
        padding: 2.5rem 2.6rem 2.35rem;
    }

    .exec-eyebrow {
        color: var(--primary-dark);
        font-size: 0.76rem;
        font-weight: 750;
        letter-spacing: 0.13em;
        text-transform: uppercase;
        margin-bottom: 0.75rem;
    }

    .exec-title {
        color: var(--ink);
        font-size: clamp(2.1rem, 4.5vw, 4.15rem);
        font-weight: 680;
        line-height: 1.02;
        letter-spacing: -0.055em;
        max-width: 980px;
        margin: 0;
        text-wrap: balance;
    }

    .exec-deck {
        color: var(--muted);
        font-size: 1.08rem;
        line-height: 1.65;
        max-width: 850px;
        margin: 1rem 0 1.55rem 0;
    }

    .exec-hero .exec-eyebrow {
        color: #a5b4fc;
    }

    .exec-hero .exec-title {
        color: #ffffff;
    }

    .exec-hero .exec-deck {
        color: #b4b7c9;
        margin-bottom: 0;
    }

    .screening-note {
        align-items: center;
        background: var(--primary-soft);
        border: 1px solid #c7d2fe;
        border-radius: 10px;
        color: var(--ink-soft);
        display: flex;
        font-size: 0.86rem;
        gap: 0.65rem;
        line-height: 1.45;
        margin: 0 0 1.55rem 0;
        padding: 0.75rem 0.9rem;
    }

    .screening-dot {
        background: var(--primary);
        border-radius: 999px;
        display: inline-block;
        flex: 0 0 auto;
        height: 0.55rem;
        width: 0.55rem;
    }

    [data-testid="stMetric"] {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 14px;
        min-height: 142px;
        padding: 1.05rem 1.1rem;
        box-shadow: 0 7px 22px rgba(11, 15, 25, 0.055);
    }

    [data-testid="stMetricLabel"] {
        color: var(--muted);
        font-size: 0.76rem;
        font-weight: 720;
        letter-spacing: 0.035em;
        overflow: visible;
        text-transform: uppercase;
    }

    [data-testid="stMetricLabel"] > div,
    [data-testid="stMetricLabel"] p {
        line-height: 1.25;
        overflow: visible;
        text-overflow: clip;
        white-space: normal;
    }

    [data-testid="stMetricValue"] {
        color: var(--ink);
        font-size: 2rem;
        letter-spacing: -0.045em;
    }

    [data-testid="stMetricDelta"] {
        font-size: 0.8rem;
    }

    .decision-callout {
        background:
            radial-gradient(circle at 96% 0%, rgba(139, 92, 246, 0.34), transparent 18rem),
            linear-gradient(135deg, #1b2040, var(--primary-dark));
        border-radius: 16px;
        box-shadow: 0 12px 28px rgba(62, 65, 238, 0.2);
        color: #ffffff;
        margin: 1rem 0;
        padding: 1.25rem 1.35rem;
    }

    .decision-callout .callout-kicker {
        color: #e0e7ff;
        font-size: 0.72rem;
        font-weight: 760;
        letter-spacing: 0.12em;
        margin-bottom: 0.45rem;
        text-transform: uppercase;
    }

    .decision-callout .callout-title {
        color: #ffffff;
        font-size: 1.15rem;
        font-weight: 680;
        margin-bottom: 0.3rem;
    }

    .decision-callout .callout-body {
        color: #f1f2ff;
        font-size: 0.93rem;
        line-height: 1.55;
    }

    .option-card {
        background: var(--card);
        border: 1px solid var(--line);
        border-top: 4px solid var(--primary);
        border-radius: 13px;
        min-height: 188px;
        padding: 1.05rem 1.1rem;
    }

    .option-card.violet {
        border-top-color: var(--violet);
    }

    .option-card .option-label {
        color: var(--muted);
        font-size: 0.71rem;
        font-weight: 730;
        letter-spacing: 0.1em;
        text-transform: uppercase;
    }

    .option-card .option-title {
        color: var(--ink);
        font-size: 1.08rem;
        font-weight: 690;
        margin: 0.5rem 0;
    }

    .option-card .option-body {
        color: var(--muted);
        font-size: 0.9rem;
        line-height: 1.52;
    }

    [data-testid="stDataFrame"] {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 12px;
        overflow: hidden;
    }

    [data-testid="stExpander"] {
        background: rgba(255, 255, 255, 0.82);
        border: 1px solid var(--line);
        border-radius: 12px;
    }

    [data-testid="stPlotlyChart"] {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 14px;
        overflow: hidden;
    }

    .small-provenance {
        color: var(--muted);
        font-size: 0.78rem;
        line-height: 1.5;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(255, 255, 255, 0.68);
        border-color: var(--line);
        border-radius: 14px;
    }

    @media (max-width: 760px) {
        .block-container {
            padding-top: 1.5rem;
        }

        .exec-title {
            font-size: 2.35rem;
        }

        .exec-hero {
            border-radius: 16px;
            padding: 1.7rem 1.35rem 1.6rem;
        }

        [data-testid="stMetric"] {
            min-height: 116px;
        }
    }
</style>
"""


def apply_executive_style() -> None:
    st.markdown(EXECUTIVE_CSS, unsafe_allow_html=True)


def executive_header(*, eyebrow: str, title: str, deck: str) -> None:
    st.markdown(
        (
            '<div class="exec-hero">'
            f'<div class="exec-eyebrow">{escape(eyebrow)}</div>'
            f'<h1 class="exec-title">{escape(title)}</h1>'
            f'<p class="exec-deck">{escape(deck)}</p>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def screening_notice(
    message: str = (
        "Decision-use note — These analyses are designed to guide planning decisions by identifying the areas and strategies that warrant further investigation. They are not intended to represent a final investment ranking."
    ),
) -> None:
    st.markdown(
        (
            '<div class="screening-note">'
            '<span class="screening-dot"></span>'
            f"<span>{escape(message)}</span>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def decision_callout(*, title: str, body: str, kicker: str = "takeaway") -> None:
    st.markdown(
        (
            '<div class="decision-callout">'
            f'<div class="callout-kicker">{escape(kicker)}</div>'
            f'<div class="callout-title">{escape(title)}</div>'
            f'<div class="callout-body">{escape(body)}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def option_card(*, label: str, title: str, body: str, accent: str = "primary") -> None:
    accent_class = " violet" if accent == "violet" else ""
    st.markdown(
        (
            f'<div class="option-card{accent_class}">'
            f'<div class="option-label">{escape(label)}</div>'
            f'<div class="option-title">{escape(title)}</div>'
            f'<div class="option-body">{escape(body)}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def format_analysis_date(value: object) -> str:
    if value is None:
        return "Date unavailable"
    raw = str(value).strip()
    if not raw:
        return "Date unavailable"
    try:
        return datetime.fromisoformat(raw).strftime("%d %b %Y")
    except ValueError:
        return raw


def baseline_delay_from_sweep(df: pd.DataFrame) -> float:
    if df.empty or "avg_delay_min" not in df.columns:
        raise ValueError("Demand-reduction results do not include average delay.")
    if "reduction_pct" in df.columns and (df["reduction_pct"] == 0).any():
        return float(df.loc[df["reduction_pct"] == 0, "avg_delay_min"].iloc[0])
    if "delta_avg_delay_min" in df.columns:
        return float((df["avg_delay_min"] - df["delta_avg_delay_min"]).median())
    return float(df["avg_delay_min"].iloc[0])


def select_reduction_case(df: pd.DataFrame, target_pct: int) -> pd.Series:
    if df.empty or "reduction_pct" not in df.columns:
        raise ValueError("Demand-reduction results do not include reduction levels.")
    levels = pd.to_numeric(df["reduction_pct"], errors="coerce")
    matches = df.loc[levels == target_pct]
    if matches.empty:
        raise ValueError(f"Demand-reduction results do not include the {target_pct}% case.")
    return matches.iloc[0]


def deduplicate_connectors(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the strongest presentation row for each physical connector endpoint pair."""
    if df.empty:
        return df.copy()

    out = df.copy()
    required = {"connector_a", "connector_b"}
    if required.issubset(out.columns):
        endpoint_a = pd.to_numeric(out["connector_a"], errors="coerce")
        endpoint_b = pd.to_numeric(out["connector_b"], errors="coerce")
        out["_endpoint_low"] = pd.concat([endpoint_a, endpoint_b], axis=1).min(axis=1)
        out["_endpoint_high"] = pd.concat([endpoint_a, endpoint_b], axis=1).max(axis=1)
        keys = ["_endpoint_low", "_endpoint_high"]

        if "connector_name" in out.columns:
            out["_source_label"] = (
                out["connector_name"].astype(str).str.replace("Bypass near ", "", regex=False)
            )
            source_labels = (
                out.groupby(keys, dropna=False)["_source_label"]
                .agg(lambda values: " / ".join(sorted(set(values))))
                .rename("source_labels")
                .reset_index()
            )
            out = out.merge(source_labels, on=keys, how="left")
    elif "scenario_id" in out.columns:
        keys = ["scenario_id"]
    else:
        return out

    if "improve_delay_pct" in out.columns:
        out = out.sort_values("improve_delay_pct", ascending=False)
    return out.drop_duplicates(keys).drop(
        columns=["_endpoint_low", "_endpoint_high", "_source_label"], errors="ignore"
    )


def make_demand_curve(df: pd.DataFrame, baseline_delay: float) -> go.Figure:
    chart = df[["reduction_pct", "avg_delay_min"]].copy()
    if not (chart["reduction_pct"] == 0).any():
        chart = pd.concat(
            [pd.DataFrame({"reduction_pct": [0], "avg_delay_min": [baseline_delay]}), chart],
            ignore_index=True,
        )
    chart = chart.sort_values("reduction_pct")

    fig = go.Figure(
        go.Scatter(
            x=chart["reduction_pct"],
            y=chart["avg_delay_min"],
            mode="lines+markers",
            line={"color": "#6366f1", "width": 4},
            marker={"color": "#ffffff", "line": {"color": "#6366f1", "width": 3}, "size": 10},
            hovertemplate="%{x:.0f}% fewer peak trips<br>%{y:.1f} min estimated average delay<extra></extra>",
        )
    )
    fig.update_layout(
        height=420,
        margin={"l": 20, "r": 20, "t": 28, "b": 20},
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        showlegend=False,
        font={"color": "#0b0f19", "family": "Manrope, Inter, Aptos, sans-serif"},
        xaxis={
            "title": "Peak-hour trip reduction",
            "ticksuffix": "%",
            "gridcolor": "#e9ebf4",
            "zeroline": False,
        },
        yaxis={
            "title": "Estimated average delay (minutes per vehicle)",
            "gridcolor": "#e9ebf4",
            "rangemode": "tozero",
            "zeroline": False,
        },
        hoverlabel={"bgcolor": "#0b0f19", "font_color": "white"},
    )
    return fig


def make_corridor_chart(corridors: pd.DataFrame) -> go.Figure:
    chart = corridors.sort_values("Share of island delay", ascending=True)
    fig = go.Figure(
        go.Bar(
            x=chart["Share of island delay"],
            y=chart["Corridor"],
            orientation="h",
            marker_color="#8b5cf6",
            text=chart["Share of island delay"].map(lambda value: f"{value:.0f}%"),
            textposition="outside",
            hovertemplate="%{y}<br>%{x:.1f}% of island-wide estimated delay<extra></extra>",
        )
    )
    fig.update_layout(
        height=330,
        margin={"l": 12, "r": 45, "t": 20, "b": 20},
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        showlegend=False,
        font={"color": "#0b0f19", "family": "Manrope, Inter, Aptos, sans-serif"},
        xaxis={"visible": False, "range": [0, max(50, chart["Share of island delay"].max() * 1.2)]},
        yaxis={"title": None},
        hoverlabel={"bgcolor": "#0b0f19", "font_color": "white"},
    )
    return fig
