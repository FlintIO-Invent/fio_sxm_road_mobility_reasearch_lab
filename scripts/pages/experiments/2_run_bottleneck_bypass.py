from __future__ import annotations
from pathlib import Path
import pandas as pd
import streamlit as st
from apps.components import make_network_figure
from sxm_mobility.experiments.run_manager import (
    base_dir,
    list_runs,
    read_manifest,
    bottleneck_bypass_experiment_path,
    bottleneck_bypass_edge_experiment_path
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
    return pd.read_parquet(path_str)


def load_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(str(path))
    return read_parquet_cached(str(path), path.stat().st_mtime)


def find_connector_file(run_dir: Path) -> Path | None:
    """Robust connector artifact discovery."""
    candidates = [
        run_dir / "connector_edges.parquet",
        run_dir / "connector.parquet",
        run_dir / "bypass_connector_edges.parquet",
        run_dir / "bottleneck_bypass_edges.parquet",
    ]
    for p in candidates:
        if p.exists():
            return p

    parquet_files = sorted(run_dir.glob("*.parquet"))
    for p in parquet_files:
        if "connector" in p.name.lower():
            return p

    for p in parquet_files:
        name = p.name.lower()
        if "edge" in name and "edges.parquet" not in name and "results" not in name:
            return p

    return None


def add_improvement_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure stakeholder-friendly improvement columns exist:
      - improve_delay_veh_hours (positive = better)
      - improve_delay_pct
      - status (Improves/Worsens/No change)
    """
    out = df.copy()

    # Must have baseline/scenario delay or delta_delay
    if "delta_delay_veh_hours" not in out.columns:
        if "scenario_delay_veh_hours" in out.columns and "baseline_delay_veh_hours" in out.columns:
            out["delta_delay_veh_hours"] = out["scenario_delay_veh_hours"] - out["baseline_delay_veh_hours"]
        else:
            return out

    if "improve_delay_veh_hours" not in out.columns:
        out["improve_delay_veh_hours"] = -out["delta_delay_veh_hours"]

    if "improve_delay_pct" not in out.columns:
        if "baseline_delay_veh_hours" in out.columns:
            base = out["baseline_delay_veh_hours"].replace(0, pd.NA)
            out["improve_delay_pct"] = (out["improve_delay_veh_hours"] / base) * 100.0
        else:
            out["improve_delay_pct"] = pd.NA

    if "status" not in out.columns:
        out["status"] = out["delta_delay_veh_hours"].apply(
            lambda x: "Improves" if x < 0 else ("Worsens" if x > 0 else "No change")
        )

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
# Sidebar controls (render)
# ============================================================
st.sidebar.header("Map Render options")
st.sidebar.markdown("Higher values show more detail but may reduce performance.")
max_edges = st.sidebar.slider("Increase roadways network", 500, 20000, 8000, step=500)

# Note: this page is about connectors; we overlay connectors, not baseline bottlenecks.
show_connectors = st.sidebar.checkbox("Overlay proposed connectors", value=True)


# ============================================================
# Page content
# ============================================================
st.title("Bottleneck Bypass Dashboard")

st.markdown(
    """
This dashboard shows a “what-if” test where we propose a small new road connection (a connector or bypass) near a known congestion point and then re-run the traffic simulation to see whether overall delays improve.
The model starts from the same baseline road network and the same baseline travel demand used in the congestion results. In other words, we are not changing “how many trips happen” — we are only changing the **road layout** by adding a proposed connector link. The simulation then assigns trips across the network using weighted travel times: roads that become busy slow down, and the model shifts some trips toward alternative routes, similar to how drivers re-route in real life.
The results table compares the baseline performance against the connector scenario. The most important indicator is **total delay**, which represents the extra travel time added by congestion across all vehicles during the simulated busy period. A connector is considered successful if it reduces total delay (an improvement), meaning the network can move the same volume of trips with less congestion.
The map helps visualize the connectors which are highlighted as a distinct line so stakeholders can immediately see where the intervention is located. This experiment is meant to show and support early screening: ***it does not claim the connector should be built as-is.*** Instead, it provides evidence on whether a bypass concept is worth further engineering review, field validation, and discussion with the community.
"""
)


bb_runs = list_runs("bottleneck_bypass")
bb_run: Path | None = bb_runs[0] if bb_runs else None

if bb_run is None:
    st.info("No connector/bypass runs found yet. Run your bottleneck bypass script to generate results.")
    st.stop()

manifest = read_manifest(bb_run)

# --- Load Results
results_path = bottleneck_bypass_experiment_path(bb_run)
if not results_path.exists():
    st.warning(f"Missing results file: {results_path}")
    results = pd.DataFrame()
else:
    results = load_parquet(results_path)

if not results.empty:
    results = add_improvement_columns(results)

    # Sort best first (largest improvement = highest improve_delay)
    results = results.sort_values("improve_delay_veh_hours", ascending=False)

    st.subheader("🪢 Impact summary (Does it improve congestion?)")

    best = results.iloc[0]
    base_delay = float(best.get("baseline_delay_veh_hours", 0.0))
    best_delay = float(best.get("scenario_delay_veh_hours", 0.0))
    improve = float(best.get("improve_delay_veh_hours", 0.0))
    pct = best.get("improve_delay_pct", None)

    c4, c1, c2, c3 = st.columns(4)
    c4.metric("Total vehicles (Demand)", f"25,000")
    c1.metric("Baseline total delay (veh-hours)", f"{base_delay:,.2f}")
    c2.metric("Best scenario delay (veh-hours)", f"{best_delay:,.2f}")
    c3.metric(
        "Delay reduction (veh-hours)",
        f"{improve:,.2f}",
        delta=(f"{float(pct):.1f}%" if pct is not None and pd.notna(pct) else None),
    )

    st.caption("Positive delay reduction means improvement; negative means the connector made delays worse.")

    # Show a clean table for stakeholders
    display_cols = []
    for c in [
        "scenario_id",
        "status",
        "improve_delay_veh_hours",
        "improve_delay_pct",
        "connector_length_m",
        "connector_speed_kph",
        "connector_lanes",
        "baseline_bottleneck_u",
        "baseline_bottleneck_v",
        "connector_a",
        "connector_b",
    ]:
        if c in results.columns:
            display_cols.append(c)

    st.dataframe(results[display_cols], use_container_width=True)

else:
    st.info("No results rows found in the experiment output yet.")


# --- Connector artifact (robust)
connector_path = None
try:
    connector_path = bottleneck_bypass_edge_experiment_path(bb_run)
except Exception:
    connector_path = find_connector_file(bb_run)

if connector_path is None or not connector_path.exists():
    st.warning(
        "Could not find a connector edge artifact in this run folder. "
        "Make sure your runner writes something like connector_edges.parquet."
    )
    connector_edges = pd.DataFrame()
else:
    connector_edges = load_parquet(connector_path)

if not connector_edges.empty:
    if "geometry_wkt" not in connector_edges.columns:
        st.error(
            "Connector file exists but has no geometry_wkt column. "
            "Your runner must save connector geometry as WKT."
        )
        connector_edges = pd.DataFrame()
    else:
        connector_edges = connector_edges.dropna(subset=["geometry_wkt"])
        st.caption(f"Connector overlay source: {connector_path.name} | rows: {len(connector_edges)}")


# --- Choose which connector to show on map (recommended for clarity)
selected_id = None
if not connector_edges.empty and "scenario_id" in connector_edges.columns and show_connectors:
    options = connector_edges["scenario_id"].astype(str).unique().tolist()
    options = ["(best)"] + options

    selected = st.selectbox("Choose a connector to display on the map", options, index=0)

    if selected == "(best)" and (results is not None) and (not results.empty) and ("scenario_id" in results.columns):
        selected_id = str(results.iloc[0]["scenario_id"])
    else:
        selected_id = selected

extra = None
if show_connectors and not connector_edges.empty:
    if selected_id and "scenario_id" in connector_edges.columns:
        extra = connector_edges.loc[connector_edges["scenario_id"].astype(str) == str(selected_id)]
    else:
        # fallback: draw all connectors
        extra = connector_edges

# --- Map render
st.subheader("🗺️ Map view")
st.caption("The highlighted line is the selected proposed connector/bypass.")

fig = make_network_figure(
    edges=edges,
    max_edges=max_edges,
    bottlenecks=None,
    top_n=0,
    extra_edges=extra if (extra is not None and not extra.empty) else None,
)
st.plotly_chart(fig, use_container_width=True)
