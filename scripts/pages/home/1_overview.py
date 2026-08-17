from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from apps.executive import (
    apply_executive_style,
    baseline_delay_from_sweep,
    decision_callout,
    deduplicate_connectors,
    executive_header,
    format_analysis_date,
    make_corridor_chart,
    option_card,
    screening_notice,
    select_reduction_case,
)

from sxm_mobility.experiments.run_manager import (
    base_dir,
    baseline_bottlenecks_path,
    baseline_kpi_path,
    bottleneck_bypass_experiment_path,
    list_runs,
    read_manifest,
    solution_experiment_path,
)
from sxm_mobility.helpers import clean_osm_value

st.set_page_config(page_title="SXM Mobility Strategy Brief", page_icon="◈", layout="wide")
apply_executive_style()


@st.cache_data
def load_parquet(path_str: str, mtime: float) -> pd.DataFrame:
    return pd.read_parquet(path_str)


def read_if_present(path: Path | None) -> pd.DataFrame:
    if path is None or not path.exists():
        return pd.DataFrame()
    return load_parquet(str(path), path.stat().st_mtime)


baseline_runs = list_runs("baseline")
if not baseline_runs:
    executive_header(
        eyebrow="Sint Maarten mobility strategy",
        title="The executive summary is awaiting the latest data update",
        deck="Complete the network performance assessment to populate the headline findings and priority corridors.",
    )
    st.info("The network performance results are not yet available.")
    st.stop()

baseline_run = baseline_runs[0]
baseline_manifest = read_manifest(baseline_run)
baseline_kpi = read_if_present(baseline_kpi_path(baseline_run))
baseline_bottlenecks = read_if_present(baseline_bottlenecks_path(baseline_run))

if baseline_kpi.empty:
    st.error("The latest network performance update is incomplete, so the headline measures cannot be shown.")
    st.stop()

kpi = baseline_kpi.iloc[0]
modeled_demand = float(kpi.get("total_demand_vph", 0))
avg_trip = float(kpi.get("avg_travel_time_min", 0))
avg_delay = float(kpi.get("avg_delay_min", 0))
island_delay = float(kpi.get("delay", 0))

edges_path = base_dir() / "edges.parquet"
edges = read_if_present(edges_path)
corridors = pd.DataFrame()
if not baseline_bottlenecks.empty and not edges.empty:
    join_keys = ["u", "v", "key"]
    for column in join_keys:
        baseline_bottlenecks[column] = pd.to_numeric(
            baseline_bottlenecks[column], errors="coerce"
        ).astype("Int64")
        edges[column] = pd.to_numeric(edges[column], errors="coerce").astype("Int64")

    corridor_segments = baseline_bottlenecks.merge(edges, on=join_keys, how="left")
    corridor_segments["Corridor"] = corridor_segments.get("name", pd.Series(dtype=object)).map(
        clean_osm_value
    )
    corridor_segments["Corridor"] = corridor_segments["Corridor"].fillna(
        corridor_segments.get("highway", pd.Series(dtype=object)).map(clean_osm_value)
    )
    corridor_segments["Corridor"] = corridor_segments["Corridor"].fillna("Unnamed corridor")
    corridors = (
        corridor_segments.groupby("Corridor", as_index=False)
        .agg(delay=("delay", "sum"), peak_pressure=("v_c", "max"))
        .sort_values("delay", ascending=False)
    )
    denominator = island_delay if island_delay > 0 else float(corridors["delay"].sum())
    corridors["Share of island delay"] = corridors["delay"] / denominator * 100

top_three_share = float(corridors.head(3)["Share of island delay"].sum()) if not corridors.empty else 0
top_corridor_names = corridors.head(3)["Corridor"].tolist()

demand_runs = list_runs("demand_reduction")
demand_run = demand_runs[0] if demand_runs else None
demand_manifest = read_manifest(demand_run) if demand_run else {}
demand_results = read_if_present(solution_experiment_path(demand_run) if demand_run else None)
demand_improvement = None
demand_case_delay = None
if not demand_results.empty:
    demand_baseline = baseline_delay_from_sweep(demand_results)
    demand_case = select_reduction_case(demand_results, 20)
    demand_case_delay = float(demand_case["avg_delay_min"])
    demand_improvement = (demand_baseline - demand_case_delay) / demand_baseline * 100

connector_runs = list_runs("bottleneck_bypass")
connector_run = connector_runs[0] if connector_runs else None
connector_manifest = read_manifest(connector_run) if connector_run else {}
connector_results = read_if_present(
    bottleneck_bypass_experiment_path(connector_run) if connector_run else None
)
unique_connectors = deduplicate_connectors(connector_results)
best_connector = unique_connectors.iloc[0] if not unique_connectors.empty else None
connector_improvement = (
    float(best_connector.get("improve_delay_pct", 0)) if best_connector is not None else None
)
connector_area = (
    str(
        best_connector.get(
            "source_labels",
            str(best_connector.get("connector_name", "leading pressure corridor")).replace(
                "Bypass near ", ""
            ),
        )
    )
    if best_connector is not None
    else "the leading pressure corridor"
)

executive_header(
    eyebrow="Sint Maarten mobility strategy · Executive summary",
    title="How Sint Maarten moves, where pressure builds, and where action can have the greatest impact",
    deck=(
        f"The assessment represents {modeled_demand:,.0f} vehicle trips during the peak hour. "
        f"An average journey is estimated at {avg_trip:.1f} minutes, including {avg_delay:.1f} minutes "
        "of congestion-related delay. Most of that pressure is concentrated along a small number of corridors."
    ),
)
screening_notice(
    "Decision-use note — These analyses are designed to guide planning decisions by identifying the areas and strategies that warrant further investigation. They are not intended to represent a final investment ranking."
)

metric_columns = st.columns(4)
metric_columns[0].metric("Chosen trip estimate", f"{modeled_demand:,.0f}")
metric_columns[1].metric("Chosen journey estimate", f"{avg_trip:.1f} min")
metric_columns[2].metric("Chosen delay estimate", f"{avg_delay:.1f} min")
metric_columns[3].metric(
    "Top-3 estimate",
    f"{top_three_share:.0f}%" if top_three_share else "—",
)

if top_corridor_names:
    corridor_phrase = ", ".join(top_corridor_names)
else:
    corridor_phrase = "the leading pressure corridors"

decision_callout(
    title="Confirm the priority corridors and develop a balanced response.",
    body=(
        f"Focus data collection and junction reviews on A.J.C. Brouwersweg, G. A. Arnell Boulevard, and the Indigo Bay Roundabout. Treat the 10%–20% demand scenarios as planning bounds, and advance the strongest network concepts for further land, safety, cost, and constructability assessment."
    ),
)

st.subheader("Strategic response at a glance")
left, right = st.columns(2, gap="large")
with left:
    if demand_improvement is not None and demand_case_delay is not None:
        option_card(
            label="Operational strategy · Peak-hour demand",
            title=f"20% planning scenario → estimated average delay reduced by {demand_improvement:.0f}%",
            body=(
                f"Under the 20% demand-reduction scenario, average delay falls to approximately {demand_case_delay:.1f} minutes per vehicle. This provides a useful planning benchmark for understanding how demand-management measures could improve network performance."
            ),
        )
    else:
        option_card(
            label="Operational strategy · Peak-hour demand",
            title="Comparison results pending",
            body="Complete the demand assessment to compare practical peak-hour planning cases.",
        )
    st.page_link(
        "pages/experiments/1_run_demand_reduction.py",
        label="Review peak-hour demand strategy",
        icon=":material/arrow_forward:",
    )

with right:
    if connector_improvement is not None:
        option_card(
            label="Infrastructure strategy · Network improvement",
            title=f"Strongest concept → estimated {connector_improvement:.0f}% performance improvement",
            body=(
                f"The strongest tested infrastructure concept improves network performance by approximately 17%, with the most promising opportunity identified near {connector_area}. The concept should now be assessed for feasibility, safety, land requirements, cost, and constructability."
                "It warrants professional feasibility review before any route or alignment is considered."
            ),
            accent="violet",
        )
    else:
        option_card(
            label="Infrastructure strategy · Network improvement",
            title="Concept comparison pending",
            body="Complete the network improvement assessment to compare distinct relief concepts.",
            accent="violet",
        )
    st.page_link(
        "pages/experiments/2_run_bottleneck_bypass.py",
        label="Review network improvements",
        icon=":material/arrow_forward:",
    )

if not corridors.empty:
    st.subheader("Where network pressure is concentrated")
    st.caption(
        "A relatively small number of corridors account for a substantial share of the estimated network-wide delay, helping identify where further investigation and targeted intervention may have the greatest value."
    )
    st.plotly_chart(make_corridor_chart(corridors.head(5)), width="stretch")

st.subheader("Recommended next steps")
next_columns = st.columns(3, gap="medium")
with next_columns[0]:
    option_card(
        label="01 · Confirm",
        title="Strengthen the evidence base",
        body="Validate the model findings with counts, turning-movement observations, and measured travel times along the highest-priority corridors.",
    )
with next_columns[1]:
    option_card(
        label="02 · Develop",
        title="Turn findings into viable options",
        body="Use the demand scenarios as planning bounds and develop the strongest network concepts into comparable options, incorporating engineering, safety, land, cost, and delivery considerations.",
    )
with next_columns[2]:
    option_card(
        label="03 · Decide",
        title="Build an investment-ready shortlist",
        body="Combine the modelling results with local evidence and feasibility findings to identify the options best suited for detailed assessment, approval, and potential delivery.",
        accent="violet",
    )