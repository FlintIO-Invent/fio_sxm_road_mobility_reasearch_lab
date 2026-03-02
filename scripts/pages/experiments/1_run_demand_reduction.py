from __future__ import annotations
from pathlib import Path
import pandas as pd
import streamlit as st
from sxm_mobility.config import settings
from sxm_mobility.helpers import clean_osm_value, build_node_labels
from apps.components import make_network_figure, show_column_help
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

with st.container(border=True):
    st.subheader("Reduction Findings")
    st.markdown(
        """
    This dashboard summarizes a demand-reduction experiment designed to answer a practical policy question:
    **how many vehicles can be on Sint Maarten’s roads during a busy hour before delays rise sharply, and what reduction would bring congestion back down to a more acceptable level**.

    The road network remains the same as the baseline model. The only change is the number of trips entering the network during the peak hour.
    Each row in the results table represents a different reduction level (for example 5%, 10%, 15%), which can reflect measures such as: 

    - **Improved public transport**
    - Carpooling 
    - Staggered work and school times 
    - Vehicle reform laws
        - Importation Laws
        - Car Emission Reduction Laws

    or other reforms that shift travel away from peak hours. For each reduction level, the model re-runs the traffic simulation and recalculates congestion across the entire island. The table reports system performance
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
        if not dr.empty:
            dr_view = dr.rename(columns=getattr(settings, "dr_columns_mapping", {}))
            dr_help = getattr(settings, "DR_HELP", {})

            st.subheader("Demand reduction sweep ")
            st.dataframe(dr_view, use_container_width=True)
            show_column_help(dr_view, dr_help, title="ℹ️ What do these columns mean?")

with st.container(border=True):
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


    st.subheader("Conclusion")

    # --- Primary takeaways (balanced framing) ---
    st.info(
        "Demand reduction consistently improves congestion. "
        "The **50% reduction** case should be treated as an **optimistic** goal, "
        "so we also highlight **more obtainable, more plausible options in the first phase of implementation**."
    )

    # --- Top row KPIs: baseline + optimistic ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Baseline avg delay", f"{base_avg_delay:.2f} min/veh")
    c2.metric("Optimistic scenario", f"-{best_red}% demand")
    c3.metric("Delay (optimistic)", f"{best_avg_delay:.2f} min/veh", delta=f"-{improvement_pct:.0f}%")

    st.caption(hit_text)

    st.divider()

    # --- Secondary options table ---
    st.markdown("#### Secondary options (quickly achievable reductions with meaningful improvements)")

    df_opts = pd.DataFrame({
        "Demand reduction (%)": dr["reduction_pct"],
        "Avg delay (min/veh)": dr["avg_delay_min"],
    })

    df_opts["Improvement vs baseline (%)"] = (
        (base_avg_delay - df_opts["Avg delay (min/veh)"]) / base_avg_delay * 100
    ).round(0).astype(int)

    # mark optimistic scenario
    df_opts["Scenario"] = df_opts["Demand reduction (%)"].apply(
        lambda x: "Optimistic (stretch)" if x == best_red else "Secondary"
    )

    # Keep only meaningful secondary options (exclude baseline + optimistic)
    secondary_df = df_opts[
        (df_opts["Demand reduction (%)"] != 0) &
        (df_opts["Demand reduction (%)"] != best_red)
    ].sort_values("Demand reduction (%)")

    # Show top 3 secondary (you can change this selection logic)
    top_secondary = secondary_df.head(3)

    st.dataframe(
        top_secondary[["Demand reduction (%)", "Avg delay (min/veh)", "Improvement vs baseline (%)"]],
        use_container_width=True,
        hide_index=True,
    )

    # --- Narrative summary: optimistic + secondary ---
    if not top_secondary.empty:
        sec_lines = []
        for _, r in top_secondary.iterrows():
            sec_lines.append(
                f"- **-{int(r['Demand reduction (%)'])}%** → **{r['Avg delay (min/veh)']:.2f} min/veh** "
                f"(≈ **{int(r['Improvement vs baseline (%)'])}%** improvement)"
            )
        secondary_text = "\n".join(sec_lines)
    else:
        secondary_text = "_No secondary options available from the current sweep._"

    st.success(
        f"**Optimistic (stretch):** -{best_red}% demand reduces average delay from "
        f"**{base_avg_delay:.2f}** to **{best_avg_delay:.2f} min/vehicle** "
        f"(≈ **{improvement_pct:.0f}%** improvement).\n\n"
        f"**Secondary options:**\n{secondary_text}"
    )




