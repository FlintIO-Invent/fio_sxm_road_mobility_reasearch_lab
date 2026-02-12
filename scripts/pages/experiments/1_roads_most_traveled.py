from __future__ import annotations

from pathlib import Path
import pandas as pd
import streamlit as st

from sxm_mobility.config import settings
from apps.components import make_network_figure

from sxm_mobility.experiments.run_manager import (
    base_dir,
    list_runs,
    read_manifest,
    baseline_bottlenecks_path,
    baseline_kpi_path,
    scenarios_path,
)


st.set_page_config(page_title="St. Maarten Road Mobility Research Lab", layout="wide")


# ---------------------------
# Cached parquet reader
# ---------------------------
@st.cache_data
def read_parquet_cached(path_str: str, mtime: float) -> pd.DataFrame:
    # mtime is included so cache invalidates when the file changes
    return pd.read_parquet(path_str)


def load_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(str(path))
    return read_parquet_cached(str(path), path.stat().st_mtime)


def ids_to_string_for_display(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].astype("string")
    return out


# ---------------------------
# Resolve base network artifacts (shared)
# ---------------------------
EDGES_PATH = base_dir() / "edges.parquet"
if not EDGES_PATH.exists():
    st.error(f"Missing base edges file: {EDGES_PATH}")
    st.info("Run scripts/build_graph.py to create base artifacts.")
    st.stop()

edges = load_parquet(EDGES_PATH)

# Ensure join keys are numeric for merges/overlays
for c in ["u", "v", "key"]:
    if c in edges.columns:
        edges[c] = pd.to_numeric(edges[c], errors="coerce").astype("Int64")


# ---------------------------
# Select baseline run (required)
# ---------------------------
baseline_runs = list_runs("baseline")
if not baseline_runs:
    st.info("No baseline runs found. Run scripts/run_baseline.py")
    st.stop()

st.sidebar.header("Run selection")

baseline_options = [p.name for p in baseline_runs]
selected_baseline = st.sidebar.selectbox("Baseline run", baseline_options, index=0)
baseline_run_path = next(p for p in baseline_runs if p.name == selected_baseline)
baseline_manifest = read_manifest(baseline_run_path)
st.sidebar.caption(f"Baseline created_at: {baseline_manifest.get('created_at', 'n/a')}")

kpi_path = baseline_kpi_path(baseline_run_path)
btn_path = baseline_bottlenecks_path(baseline_run_path)

try:
    kpi = load_parquet(kpi_path)
except FileNotFoundError:
    kpi = pd.DataFrame()
    st.warning(f"Baseline KPI missing for run: {baseline_run_path.name}")

try:
    btn = load_parquet(btn_path)
except FileNotFoundError:
    btn = pd.DataFrame()
    st.warning(f"Baseline bottlenecks missing for run: {baseline_run_path.name}")

# Standardize bottleneck join key types
for c in ["u", "v", "key"]:
    if c in btn.columns:
        btn[c] = pd.to_numeric(btn[c], errors="coerce").astype("Int64")


# ---------------------------
# Optional: select scenario run
# ---------------------------
# (Depending on what you named it when creating runs, it might be "scenarios" or "scenario")
scen_runs = list_runs("scenarios")
if not scen_runs:
    scen_runs = list_runs("scenario")

selected_scen_run_path: Path | None = None
scen_df = pd.DataFrame()

if scen_runs:
    scen_options = ["(latest)"] + [p.name for p in scen_runs]
    selected_scen = st.sidebar.selectbox("Scenario run", scen_options, index=0)

    if selected_scen == "(latest)":
        selected_scen_run_path = scen_runs[0]
    else:
        selected_scen_run_path = next(p for p in scen_runs if p.name == selected_scen)

    scen_manifest = read_manifest(selected_scen_run_path)
    st.sidebar.caption(f"Scenarios created_at: {scen_manifest.get('created_at', 'n/a')}")

    try:
        scen_df = load_parquet(scenarios_path(selected_scen_run_path))
    except FileNotFoundError:
        scen_df = pd.DataFrame()
        st.sidebar.warning("Scenario results missing in selected run.")


# ---------------------------
# Sidebar controls (render)
# ---------------------------
st.sidebar.header("Render options")
max_edges = st.sidebar.slider("Max edges to draw (performance)", 500, 20000, 8000, step=500)
show_bottlenecks = st.sidebar.checkbox("Overlay bottlenecks", value=True)
top_n = st.sidebar.slider("Top N bottlenecks", 10, 300, 50, step=10)

st.sidebar.markdown(
    "Adjust how much of the network is drawn and whether congestion hotspots are highlighted. "
    "Higher values show more detail but may reduce performance."
)


# ---------------------------
# Page content
# ---------------------------
st.title("Dashboards")

# --- Baseline outputs
with st.container(border=True):
    st.subheader("📘 Baseline outputs")
    st.caption(
        "This section shows how the road network performs under normal conditions — "
        "before any improvements or changes are tested."
    )

    c1, c2 = st.columns([1, 1], gap="large")

    with c1:
        st.markdown("**KPI summary**")
        if not kpi.empty:
            kpi_view = kpi.rename(columns=getattr(settings, "kpi_columns", {}))
            st.dataframe(kpi_view, use_container_width=True)
        else:
            st.info("No KPI table found for this run.")

    with c2:
        st.markdown("**Top bottlenecks**")
        if not btn.empty:
            # Sort if delay exists (keeps output consistent)
            if "delay" in btn.columns:
                btn = btn.sort_values("delay", ascending=False)

            btn_view = ids_to_string_for_display(btn, ["u", "v", "key"]).rename(
                columns=getattr(settings, "btn_columns", {})
            )
            st.dataframe(btn_view, use_container_width=True)
        else:
            st.info("No bottleneck table found for this run.")


# --- Map
with st.container(border=True):
    st.subheader("🗺️ Road Network Map")
    st.caption(
        "This interactive map shows the modeled road network of Sint Maarten. "
        "Optionally overlay the top bottleneck segments from the selected baseline run."
    )

    bottlenecks_for_overlay = None
    if show_bottlenecks and not btn.empty:
        bottlenecks_for_overlay = btn.head(top_n)

    fig = make_network_figure(
        edges=edges,
        max_edges=max_edges,
        bottlenecks=bottlenecks_for_overlay,
        top_n=top_n,
    )
    st.plotly_chart(fig, use_container_width=True)


# --- Scenarios
with st.container(border=True):
    st.subheader("🔄 Scenario outputs")
    st.caption(
        "Scenario results show how proposed changes would affect island-wide mobility. "
        "If you select a scenario run in the sidebar, it will be shown here."
    )

    if scen_df is not None and not scen_df.empty:
        scen_view = scen_df.rename(columns=getattr(settings, "scen_columns", {}))
        st.dataframe(scen_view, use_container_width=True)
    else:
        st.info("No scenario run selected or scenario results not found.")


# --- Solution Prioritization
with st.container(border=True):
    st.subheader("💡 Solution Prioritization")
    st.caption(
        "This section summarizes how to interpret the baseline and scenario analyses for decision-making."
    )
    st.markdown(
        """
Possible solutions are prioritized based on whether they reduce total travel time, reduce congestion hotspots, and improve resilience.  
This helps identify interventions that deliver the strongest overall benefit for mobility and safety.
"""
    )
