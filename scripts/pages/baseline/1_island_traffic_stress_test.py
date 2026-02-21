from __future__ import annotations
from pathlib import Path
import pandas as pd
import streamlit as st
from sxm_mobility.config import settings
from sxm_mobility.helpers import clean_osm_value, build_node_labels
from apps.components import make_network_figure, show_column_help
from sxm_mobility.experiments.run_manager import (
    base_dir,
    list_runs,
    read_manifest,
    baseline_bottlenecks_path,
    baseline_kpi_path,
    scenarios_path,
)

# ============================================================
# Page config
# ============================================================
st.set_page_config(page_title="St. Maarten Road Mobility Research Lab", layout="wide")

# ============================================================
# Cached parquet reader
# ============================================================
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


# ============================================================
# Resolve base network artifacts (shared)
# ============================================================
BASE_DIR: Path = base_dir() if callable(base_dir) else base_dir

EDGES_PATH = BASE_DIR / "edges.parquet"
NODES_PATH = BASE_DIR / "nodes.parquet"

if not EDGES_PATH.exists():
    st.error(f"Missing base edges file: {EDGES_PATH}")
    st.info("Run scripts/build_graph.py to create base artifacts.")
    st.stop()

if not NODES_PATH.exists():
    st.error(f"Missing base nodes file: {NODES_PATH}")
    st.info("Run scripts/build_graph.py to create base artifacts.")
    st.stop()

edges = load_parquet(EDGES_PATH)
nodes = load_parquet(NODES_PATH)

# Ensure join keys are numeric for merges/overlays
for c in ["u", "v", "key"]:
    if c in edges.columns:
        edges[c] = pd.to_numeric(edges[c], errors="coerce").astype("Int64")


# ============================================================
# Select baseline run (required)
# ============================================================
baseline_runs = list_runs("baseline")
if not baseline_runs:
    st.info("No baseline runs found. Run scripts/run_baseline.py")
    st.stop()

st.sidebar.header("Experiment Run History")
st.sidebar.markdown(
    "The history tracks minnor parameter chnages like vehicle deman, experiment names, iterations ect."
)

baseline_options = [p.name for p in baseline_runs]
selected_baseline = st.sidebar.selectbox("Baseline run", baseline_options, index=0)
baseline_run_path = next(p for p in baseline_runs if p.name == selected_baseline)

baseline_manifest = read_manifest(baseline_run_path)
st.sidebar.caption(f"Baseline created_at: {baseline_manifest.get('created_at', 'n/a')}")

kpi_path = baseline_kpi_path(baseline_run_path)
btn_path = baseline_bottlenecks_path(baseline_run_path)

# Load KPI + bottlenecks
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

# Build readable junction labels (uses nodes + edges)
node_labels = build_node_labels(nodes, edges)

def node_label(x) -> str:
    if pd.isna(x):
        return "Junction"
    try:
        return node_labels.get(int(x), "Junction")
    except Exception:
        return "Junction"

# Enrich bottlenecks with road names and From/To labels
merged_btn = pd.DataFrame()
cols: list[str] = []

if not btn.empty:
    merged_btn = btn.merge(
        edges,
        on=["u", "v", "key"],
        how="left",
        suffixes=("", "_edge"),
    )

    merged_btn["Road"] = merged_btn.get("name", pd.Series([None] * len(merged_btn))).map(clean_osm_value)
    merged_btn["Road"] = merged_btn["Road"].fillna(
        merged_btn.get("highway", pd.Series([None] * len(merged_btn))).map(clean_osm_value)
    )

    merged_btn["From"] = merged_btn["u"].map(node_label)
    merged_btn["To"] = merged_btn["v"].map(node_label)

    # Optional per-vehicle edge delay (sec/veh)
    if "flow" in merged_btn.columns and "delay" in merged_btn.columns:
        merged_btn["avg delay (sec/veh)"] = (merged_btn["delay"] * 3600.0) / merged_btn["flow"].replace(0, pd.NA)
        merged_btn["avg delay (sec/veh)"] = merged_btn["avg delay (sec/veh)"].round(2)

    cols = [
        c for c in
        ["Road", "From", "To", "delay", "volume capacity ratio", "flow", "capacity", "length", "avg delay (sec/veh)"]
        if c in merged_btn.columns
    ]


st.sidebar.divider()

# ============================================================
# Sidebar controls (render)
# ============================================================
st.sidebar.header("Map Render options")
st.sidebar.markdown(
    "Adjust how much of the road network is drawn. Higher values show more detail but may reduce performance."
)
max_edges = st.sidebar.slider("Increase roadways network", 500, 20000, 8000, step=500)
show_bottlenecks = st.sidebar.checkbox("Overlay bottlenecks", value=True)
top_n = st.sidebar.slider("Increase bottlenecks", 10, 300, 50, step=10)


# ============================================================
# Page content
# ============================================================
st.title("Island Traffic Stress Test Dashboard")

# ---------------------------
# Baseline outputs
# ---------------------------
with st.container(border=True):
    st.subheader("📘 Baseline outputs")
    st.caption(
        "This section shows how the road network performs under normal conditions "
        "before any improvements or changes are tested."
    )

    c1, c2 = st.columns([1, 1], gap="large")

    st.markdown("**KPI Summary**")
    if not kpi.empty:
        kpi_view = kpi.rename(columns=getattr(settings, "kpi_columns_mapping", {}))
        kpi_help = getattr(settings, "KPI_HELP", {})
        st.dataframe(kpi_view, use_container_width=True)
        show_column_help(kpi_view, kpi_help, title="ℹ️ What do these columns mean?")

    else:
        st.info("No KPI table found for this run.")


    st.markdown("**Top bottlenecks**")
    if not btn.empty and not merged_btn.empty:
        # Keep output consistent
        if "delay" in merged_btn.columns:
            merged_btn = merged_btn.sort_values("delay", ascending=False)
        st.dataframe(merged_btn[cols], use_container_width=True)
        show_column_help(merged_btn[cols], settings.BOTTLENECK_HELP, title="ℹ️  What do these columns mean?")

    else:
        st.info("No bottleneck table found for this run.")


# ---------------------------
# Map
# ---------------------------
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

# ---------------------------
# Solution Prioritization
# ---------------------------
with st.container(border=True):
    st.subheader("💡 Solution Experiments & Prioritization")
    st.caption(
        "In the ***solution experiments*** tab contains all modeled intervention scenarios and their comparative results."
    )
    st.markdown(
        """
        There we evaluate each proposed mobility intervention against the baseline model.

        Scenarios are compared based on:
        - Total system travel time  
        - Congestion hotspot reduction  
        - Network resilience and robustness  

        This structured comparison helps identify which strategies deliver the strongest overall improvement
        in mobility performance, safety, and long-term system stability.
        """
    )
