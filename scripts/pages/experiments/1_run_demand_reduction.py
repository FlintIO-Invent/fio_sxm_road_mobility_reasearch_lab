from __future__ import annotations
from pathlib import Path
import pandas as pd
import streamlit as st
from apps.executive import (
    apply_executive_style,
    baseline_delay_from_sweep,
    decision_callout,
    executive_header,
    format_analysis_date,
    make_demand_curve,
    option_card,
    screening_notice,
    select_reduction_case,
)

from sxm_mobility.experiments.run_manager import (
    list_runs,
    read_manifest,
    solution_experiment_path,
)

st.set_page_config(page_title="Peak-Hour Demand | SXM Mobility", page_icon="◈", layout="wide")
apply_executive_style()

@st.cache_data
def read_parquet_cached(path_str: str, mtime: float) -> pd.DataFrame:
    return pd.read_parquet(path_str)


def load_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return read_parquet_cached(str(path), path.stat().st_mtime)


runs = list_runs("demand_reduction")
if not runs:
    executive_header(
        eyebrow="Strategic option · Peak-hour demand",
        title="The peak-hour demand assessment is not yet available",
        deck="Complete the comparison to assess how different travel-demand levels affect journey delay.",
    )
    st.stop()

run = runs[0]
manifest = read_manifest(run)
results_path = solution_experiment_path(run)
results = load_parquet(results_path)

if results.empty:
    st.error("The latest peak-hour demand assessment is incomplete.")
    st.stop()

baseline_delay = baseline_delay_from_sweep(results)
case_10 = select_reduction_case(results, 10)
case_20 = select_reduction_case(results, 20)
case_40 = select_reduction_case(results, 40)


def improvement_for(case: pd.Series) -> float:
    return (baseline_delay - float(case["avg_delay_min"])) / baseline_delay * 100


improvement_10 = improvement_for(case_10)
improvement_20 = improvement_for(case_20)
improvement_40 = improvement_for(case_40)

executive_header(
    eyebrow=f"Strategic option · Peak-hour demand · {format_analysis_date(manifest.get('created_at'))}",
    title="Reducing peak-hour demand could significantly improve network performance",
    deck=(
        f"In the 20% comparison scenario, estimated average delay falls from {baseline_delay:.1f} to "
        f"{float(case_20['avg_delay_min']):.1f} minutes per vehicle a improvement of approximately {improvement_20:.0f}%. "
        "This illustrates the potential value of demand-management measures."
    ),
)
screening_notice(
    "Decision-use note — These analyses are designed to guide planning decisions by identifying the areas and strategies that warrant further investigation. They are not intended to represent a final investment ranking."
)

metric_columns = st.columns(4)
metric_columns[0].metric("Current planning case", f"{baseline_delay:.1f} min")
metric_columns[1].metric(
    "10% DEMAND REDUCTION",
    f"{float(case_10['avg_delay_min']):.1f} min",
    f"-{improvement_10:.0f}% delay",
    delta_color="inverse",
)
metric_columns[2].metric(
    "20% DEMAND REDUCTION",
    f"{float(case_20['avg_delay_min']):.1f} min",
    f"-{improvement_20:.0f}% delay",
    delta_color="inverse",
)
metric_columns[3].metric(
    "40% sensitivity CASE",
    f"{float(case_40['avg_delay_min']):.1f} min",
    f"-{improvement_40:.0f}% delay",
    delta_color="inverse",
)

decision_callout(
    title="Use the 10%–20% scenarios as practical planning bounds.",
    body=(
        "Determine what level of participation is realistically achievable before setting programme targets."
        "Develop a small set of measurable demand-management measures, "
        "then refine the assessment using observed participation and travel-time data."
    ),
)

st.subheader("How estimated delay changes as peak-hour demand falls")
st.caption("Lower values indicate better network performance. The curve shows the estimated change in average journey delay as peak-hour trip volumes are reduced.")
st.plotly_chart(make_demand_curve(results, baseline_delay), width="stretch")

st.subheader("Potential demand-management measures")
st.caption("These measures are illustrative options for further assessment. Their individual impacts have not been modelled in this analysis.")
policy_columns = st.columns(3, gap="medium")
with policy_columns[0]:
    option_card(
        label="FOR FURTHER ASSESSMENT",
        title="Targeted shared transport",
        body="Use observed origin, destination, and time-of-day patterns to identify where shared transport services could reduce peak-hour vehicle demand most effectively.",
    )
with policy_columns[1]:
    option_card(
        label="FOR FURTHER ASSESSMENT",
        title="Flexible and staggered schedules",
        body="Work with major employers and schools to test whether selected journeys can be shifted outside the busiest travel periods",
    )
with policy_columns[2]:
    option_card(
        label="FOR FURTHER ASSESSMENT",
        title="Higher-occupancy travel incentives",
        body="Explore corridor-specific measures that encourage more people per vehicle, supported by monitoring of participation, vehicle occupancy, and peak-hour traffic levels.",
        accent="violet",
    )

st.caption("")
with st.expander("Supporting analysis and data notes"):
    st.markdown(
        f"""
        - **Data version:** `{run.name}`
        - **Analysis date:** {format_analysis_date(manifest.get("created_at"))}
        - **Assessment basis:** Same road network and calculation assumptions at each demand level.

        The comparison isolates travel demand. It does not determine how a programme would achieve the change
        or whether a given target is socially, operationally, or financially feasible.
        """
    )

    evidence = results.copy()
    evidence["Estimated improvement"] = (
        (baseline_delay - evidence["avg_delay_min"]) / baseline_delay * 100
    )
    evidence = evidence.rename(
        columns={
            "reduction_pct": "Fewer peak trips",
            "avg_travel_time_min": "Average trip (min)",
            "avg_delay_min": "Average delay (min)",
            "total_demand_vph": "Estimated vehicles/hour",
        }
    )
    evidence["Fewer peak trips"] = evidence["Fewer peak trips"].map(lambda value: f"{value:.0f}%")
    evidence["Estimated improvement"] = evidence["Estimated improvement"].map(
        lambda value: f"{value:.1f}%"
    )
    st.dataframe(
        evidence[
            [
                "Fewer peak trips",
                "Estimated vehicles/hour",
                "Average trip (min)",
                "Average delay (min)",
                "Estimated improvement",
            ]
        ],
        width="stretch",
        hide_index=True,
    )
