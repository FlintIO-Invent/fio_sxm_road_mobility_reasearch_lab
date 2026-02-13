from __future__ import annotations
from pathlib import Path
import pandas as pd
import streamlit as st
from sxm_mobility.config import settings
from sxm_mobility.helpers import clean_osm_value, build_node_labels
from apps.components import make_network_figure
from sxm_mobility.experiments.run_manager import (
    base_dir,
    runs_dir,
    list_runs,
    read_manifest,
    solution_experiment_path
    
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
# Resolve latest demand-reduction experiment artifact
# ============================================================
RUNS_DIR: Path = runs_dir() if callable(runs_dir) else runs_dir

dr_runs = list_runs("demand_reduction")
latest_dr_run: Path | None = dr_runs[0] if dr_runs else None

dr_path: Path | None = solution_experiment_path(latest_dr_run) if latest_dr_run else None


# ============================================================
# Page content
# ============================================================
st.title("Island Demand Reduction Dashboard")

st.markdown(
    """
This dashboard summarizes a demand-reduction experiment designed to answer a practical policy question:
**how many vehicles can be on Sint Maarten’s roads during a busy hour before delays rise sharply, and what reduction would bring congestion back down to a more acceptable level**.

The road network remains the same as the baseline model. The only change is the number of trips entering the network during the peak hour.
Each row in the results table represents a different reduction level (for example 5%, 10%, 15%), which can reflect measures such as improved public transport,
carpooling, staggered work and school times, parking policies, or other reforms that shift travel away from peak hours.

For each reduction level, the model re-runs the traffic simulation and recalculates congestion across the entire island. The table reports system performance
and, importantly, the **average delay per vehicle**, which is the most intuitive way to interpret what these changes mean for everyday travel.
The goal is to identify the smallest reduction that delivers a meaningful improvement in mobility outcomes.
"""
)

if dr_path is None:
    st.info("No demand-reduction runs found yet. Run the demand reduction script to generate results.")
elif not dr_path.exists():
    st.warning(f"Demand-reduction results file not found: {dr_path}")
else:
    dr = pd.read_parquet(dr_path)
    st.subheader("Demand reduction sweep (Ideal vehicles on the road)")
    st.dataframe(dr, use_container_width=True)

