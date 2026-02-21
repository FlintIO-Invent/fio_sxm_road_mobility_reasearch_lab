from __future__ import annotations
from pathlib import Path
import pandas as pd
from sxm_mobility.config import settings
import streamlit as st
from apps.components import make_network_figure, show_column_help
from sxm_mobility.experiments.run_manager import (
    base_dir,
    list_runs,
    read_manifest,
    bottleneck_bypass_experiment_path,
    bottleneck_bypass_edge_experiment_path,
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


def add_improvement_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure stakeholder-friendly improvement columns exist:
      - improve_delay_veh_hours (positive = better)
      - improve_delay_pct
      - status (Improves/Worsens/No change)
    """
    out = df.copy()

    if "delta_delay_veh_hours" not in out.columns:
        if {"scenario_delay_veh_hours", "baseline_delay_veh_hours"} <= set(out.columns):
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


def _safe_str(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if not s or s.lower() in {"nan", "none"}:
        return ""
    return s


def ensure_connector_name(results: pd.DataFrame, connector_edges: pd.DataFrame) -> pd.DataFrame:
    """
    Guarantee a stakeholder-friendly 'connector_name' column exists on results.
    Preference order:
      1) results.connector_name (already present)
      2) connector_edges.name joined by scenario_id
      3) constructed: "Relief connector near <road> (a ↔ b)"
    """
    out = results.copy()

    if "connector_name" in out.columns and out["connector_name"].notna().any():
        out["connector_name"] = out["connector_name"].astype(str)
        return out

    # Try join from connector_edges.name
    if (
        "scenario_id" in out.columns
        and not connector_edges.empty
        and "scenario_id" in connector_edges.columns
        and "name" in connector_edges.columns
    ):
        name_map = (
            connector_edges.dropna(subset=["scenario_id"])
            .assign(scenario_id=lambda d: d["scenario_id"].astype(str))
            .drop_duplicates("scenario_id")[["scenario_id", "name"]]
        )
        out = out.assign(scenario_id=lambda d: d["scenario_id"].astype(str)).merge(
            name_map, on="scenario_id", how="left"
        )
        out["connector_name"] = out["name"].map(_safe_str)
        out = out.drop(columns=["name"], errors="ignore")

    # If still missing, construct a readable name
    if "connector_name" not in out.columns:
        out["connector_name"] = ""

    if not out["connector_name"].notna().any() or (out["connector_name"].astype(str).str.len().max() == 0):
        # Build from whatever is present
        def _make_name(r: pd.Series) -> str:
            base = _safe_str(r.get("road_label")) or _safe_str(r.get("baseline_road")) or ""
            a = r.get("connector_a", "")
            b = r.get("connector_b", "")
            if base:
                return f"Relief connector near {base} ({a} ↔ {b})"
            return f"Proposed connector ({a} ↔ {b})"

        out["connector_name"] = out.apply(_make_name, axis=1)

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

for c in ["u", "v", "key"]:
    if c in edges.columns:
        edges[c] = pd.to_numeric(edges[c], errors="coerce").astype("Int64")

# ============================================================
# Sidebar controls
# ============================================================
st.sidebar.header("Map Render options")
st.sidebar.markdown("Higher values show more detail but may reduce performance.")
max_edges = st.sidebar.slider("Increase roadways network", 500, 20000, 8000, step=500)
show_connectors = st.sidebar.checkbox("Overlay proposed connectors", value=True)

# ============================================================
# Page content
# ============================================================
st.title("Bottleneck Bypass Dashboard")
with st.container(border=True):
    st.subheader("📘 Bypass Findings")
    st.markdown(
        """
    This dashboard shows a “what-if” test where we propose small new road connections (connectors/bypasses) near congestion points and re-run the traffic simulation to measure whether island-wide delays improve.

    We hold travel demand constant and only change the road layout. Roads are weighted by travel time: when segments carry more flow they slow down, and the model shifts some trips to alternative routes (similar to real drivers). A connector is considered successful if it reduces **total delay** across all vehicles during the simulated busy period. The map highlights each proposed connector so stakeholders can validate whether it is physically plausible and targeted at the right corridor.
    """
    )

    # pick latest run
    bb_runs = list_runs("bottleneck_bypass")
    bb_run: Path | None = bb_runs[0] if bb_runs else None

    if bb_run is None:
        st.info("No connector/bypass runs found yet. Run your bottleneck bypass script to generate results.")
        st.stop()

    manifest = read_manifest(bb_run)

    # --- load results
    results_path = bottleneck_bypass_experiment_path(bb_run)
    if not results_path.exists():
        st.warning(f"Missing results file: {results_path}")
        results = pd.DataFrame()
    else:
        results = load_parquet(results_path)

    # --- load connector edges (geometry + optional name/status)
    connector_path = bottleneck_bypass_edge_experiment_path(bb_run)
    if connector_path is None or not connector_path.exists():
        st.warning(
            "Could not find connector edge artifact for this run. "
            "Make sure your runner writes bottleneck_bypass_edge_experiment_path(...)."
        )
        connector_edges = pd.DataFrame()
    else:
        connector_edges = load_parquet(connector_path)

    if not connector_edges.empty and "geometry_wkt" in connector_edges.columns:
        connector_edges = connector_edges.dropna(subset=["geometry_wkt"])

    # --- enrich results
    if not results.empty:
        results = add_improvement_columns(results)
        results["scenario_id"] = results["scenario_id"].astype(str)

        # 🔥 ensure connector_name exists and is meaningful
        results = ensure_connector_name(results, connector_edges)

        # Sort best first
        results = results.sort_values("improve_delay_veh_hours", ascending=False)

        st.subheader("🪢 Impact summary (Does it improve congestion?)")
        best = results.iloc[0]
        base_delay = float(best.get("baseline_delay_veh_hours", 0.0))
        best_delay = float(best.get("scenario_delay_veh_hours", 0.0))
        improve = float(best.get("improve_delay_veh_hours", 0.0))
        pct = best.get("improve_delay_pct", None)

        c0, c1, c2, c3 = st.columns(4)
        c0.metric("Baseline delay (veh-hours)", f"{base_delay:,.2f}")
        c1.metric("Best scenario delay (veh-hours)", f"{best_delay:,.2f}")
        c2.metric("Delay reduction (veh-hours)", f"{improve:,.2f}")
        c3.metric(
            "Delay reduction (%)",
            f"{float(pct):.1f}%" if pct is not None and pd.notna(pct) else "n/a",
        )

        st.caption("Positive delay reduction means improvement; negative means the connector increased delays.")

        if  results_path is None or not results_path.exists():
            st.info("No results file found yet. Run the bottleneck bypass script to generate results.")
        else:
            bn = pd.read_parquet(results_path)
            if  not bn.empty:
                bn_view = bn.rename(columns=getattr(settings, "BYPASS_COLUMNS_MAPPING", {}))
                bn_help = getattr(settings, "BYPASS_RESULTS_HELP", {})

                # st.subheader("⤵️ Demand reduction sweep ")
                st.dataframe(bn_view, use_container_width=True)
                show_column_help(bn_view, bn_help, title="ℹ️ What do these columns mean?")

    else:
        st.info("No results rows found in the experiment output yet.")

    

            
with st.container(border=True):
    
    # --- Map render
    st.subheader("🗺️ Map view")
    st.caption("The highlighted line is the selected proposed connector/bypass.")
    
    # ============================================================
    # Choose which connector to show on map (BY NAME)
    # ============================================================
    selected_scenario_id: str | None = None

    if show_connectors and (not results.empty) and ("connector_name" in results.columns):
        options = ["(best)"] + results["connector_name"].astype(str).tolist()
        chosen_name = st.selectbox("Choose a connector to display on the map", options, index=0)

        if chosen_name == "(best)":
            selected_scenario_id = str(results.iloc[0]["scenario_id"])
        else:
            match = results.loc[results["connector_name"].astype(str) == str(chosen_name)]
            if not match.empty:
                selected_scenario_id = str(match.iloc[0]["scenario_id"])

    extra = None
    if show_connectors and not connector_edges.empty:
        if selected_scenario_id and "scenario_id" in connector_edges.columns:
            extra = connector_edges.loc[connector_edges["scenario_id"].astype(str) == selected_scenario_id]
        else:
            extra = connector_edges
    fig = make_network_figure(
        edges=edges,
        max_edges=max_edges,
        bottlenecks=None,
        top_n=0,
        extra_edges=extra if (extra is not None and not extra.empty) else None,
    )
    st.plotly_chart(fig, use_container_width=True)
