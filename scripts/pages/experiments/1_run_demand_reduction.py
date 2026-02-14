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
    st.subheader("⤵️ Demand reduction sweep (Ideal vehicles on the road)")
    st.dataframe(dr, use_container_width=True)


# ---------------------------
    # Conclusion (data-driven)
    # ---------------------------
    # Reconstruct baseline average delay if baseline row (0%) isn't included
    if "reduction_pct" in dr.columns and (dr["reduction_pct"] == 0).any():
        base_avg_delay = float(dr.loc[dr["reduction_pct"] == 0, "avg_delay_min"].iloc[0])
    elif "delta_avg_delay_min" in dr.columns:
        # base_avg_delay = avg_delay - (avg_delay - base_avg_delay)  => avg_delay - delta
        base_avg_delay = float((dr["avg_delay_min"] - dr["delta_avg_delay_min"]).median())
    else:
        base_avg_delay = float(dr["avg_delay_min"].iloc[0])

    best = dr.iloc[-1]
    best_red = int(best["reduction_pct"])
    best_avg_delay = float(best["avg_delay_min"])
    improvement_pct = (base_avg_delay - best_avg_delay) / base_avg_delay * 100.0 if base_avg_delay > 0 else 0.0

    # Pick a practical target for “acceptable peak-hour delay”
    target_avg_delay_min = 2.0
    hit = dr[dr["avg_delay_min"] <= target_avg_delay_min]
    hit_text = ""
    if not hit.empty:
        first_hit = hit.iloc[0]
        hit_red = int(first_hit["reduction_pct"])
        hit_delay = float(first_hit["avg_delay_min"])
        hit_text = (
            f" In this sweep, the first point where average delay falls below {target_avg_delay_min:.1f} minutes "
            f"per vehicle occurs at roughly {hit_red}% demand reduction (≈ {hit_delay:.2f} min/vehicle)."
        )

    st.subheader("❕ Conclusion ")
    st.success(
        f"The results show a strong and consistent improvement in congestion as peak-hour demand is reduced. "
        f"Compared with the estimated baseline average delay of about {base_avg_delay:.2f} minutes per vehicle, "
        f"reducing demand by {best_red}% lowers average delay to approximately {best_avg_delay:.2f} minutes per vehicle "
        f"(an improvement of about {improvement_pct:.0f}%)."
        f"{hit_text} "
        # f"These results are a useful first MVP indicator of the scale of change required; as local counts and observed "
        # f"travel patterns are added, the exact thresholds can be refined with real-world calibration."
    )