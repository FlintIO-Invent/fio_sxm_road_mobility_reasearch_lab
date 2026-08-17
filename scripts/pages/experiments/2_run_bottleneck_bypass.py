from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from apps.components import make_network_figure
from apps.executive import (
    apply_executive_style,
    decision_callout,
    deduplicate_connectors,
    executive_header,
    format_analysis_date,
    screening_notice,
)

from sxm_mobility.experiments.run_manager import (
    base_dir,
    bottleneck_bypass_edge_experiment_path,
    bottleneck_bypass_experiment_path,
    list_runs,
    read_manifest,
)

st.set_page_config(page_title="Network Improvements | SXM Mobility", page_icon="◈", layout="wide")
apply_executive_style()


@st.cache_data
def read_parquet_cached(path_str: str, mtime: float) -> pd.DataFrame:
    return pd.read_parquet(path_str)


def load_parquet(path: Path | None) -> pd.DataFrame:
    if path is None or not path.exists():
        return pd.DataFrame()
    return read_parquet_cached(str(path), path.stat().st_mtime)


runs = list_runs("bottleneck_bypass")
if not runs:
    executive_header(
        eyebrow="Strategic option · Network improvements",
        title="The network improvement assessment is not yet available",
        deck="Complete the comparison to assess distinct concepts for relieving network pressure.",
    )
    st.stop()

run = runs[0]
manifest = read_manifest(run)
results = load_parquet(bottleneck_bypass_experiment_path(run))
connector_edges = load_parquet(bottleneck_bypass_edge_experiment_path(run))
edges = load_parquet(base_dir() / "edges.parquet")

if results.empty or connector_edges.empty or edges.empty:
    st.error("The latest network improvement assessment is incomplete.")
    st.stop()

unique_results = deduplicate_connectors(results).reset_index(drop=True)
unique_results["Candidate"] = [f"Concept {index + 1}" for index in range(len(unique_results))]
unique_results["Nearby source labels"] = unique_results.get(
    "source_labels",
    unique_results["connector_name"].astype(str).str.replace("Bypass near ", "", regex=False),
).replace({"": "Unnamed corridor"})

best = unique_results.iloc[0]
best_improvement = float(best["improve_delay_pct"])
best_length = float(best.get("connector_length_m", 0))
best_corridor = str(best["Nearby source labels"])

executive_header(
    eyebrow=f"Strategic option · Network improvements · {format_analysis_date(manifest.get('created_at'))}",
    title="One connectivity concept shows a meaningful potential network benefit",
    deck=(
        f"A schematic connection of approximately {best_length:.0f} metres between assessment points near {best_corridor} is associated with an estimated {best_improvement:.0f}% reduction in network delay. "
        f"This type of result identifies a concept for feasibility assessment."
        
    ),
)
screening_notice(
    "Decision-use note — These analyses are designed to guide planning decisions by identifying the areas and strategies that warrant further investigation. They are not intended to represent a final investment ranking"
)

metric_columns = st.columns(4)
metric_columns[0].metric("CONNECTION CONCEPTS ASSESSED", f"{len(unique_results)}")
metric_columns[1].metric("LEADING ESTIMATED IMPROVEMENT", f"{best_improvement:.1f}%")
metric_columns[2].metric("CONNECTION DISTANCE", f"{best_length:.0f} m")
metric_columns[3].metric("Next review stage", "Feasibility")

decision_callout(
    title="Advance the strongest concepts to structured feasibility review.",
    body=(
        "Assess potential alignments, land ownership, junction safety, environmental constraints, constructability, "
        "and indicative cost. Only concepts that remain credible after this review should progress to detailed traffic "
        "and engineering assessment."
    ),
)

st.subheader("Leading connectivity concepts")
st.caption("The concepts below show where additional network connections produced the strongest estimated improvements in the planning model.")
shortlist = unique_results.head(5).copy()
shortlist["Planning concept"] = shortlist["Candidate"]
shortlist["Nearby corridors"] = shortlist["Nearby source labels"]
shortlist["Estimated delay reduction"] = shortlist["improve_delay_pct"].map(
    lambda value: f"{value:.1f}%"
)
shortlist["Straight-line distance"] = shortlist["connector_length_m"].map(
    lambda value: f"{value:.0f} m"
)
st.dataframe(
    shortlist[
        [
            "Planning concept",
            "Nearby corridors",
            "Estimated delay reduction",
            "Straight-line distance",
        ]
    ],
    width="stretch",
    hide_index=True,
)

st.subheader("Explore the concepts on the network")
st.caption("The highlighted thick line on a the map can easily be interpreted as “this is where you are proposing a road.")
selector_options = {
    f"{row['Candidate']} · {row['Nearby source labels']} · {row['improve_delay_pct']:.1f}%": str(
        row["scenario_id"]
    )
    for _, row in unique_results.iterrows()
}
selected_label = st.selectbox(
    "Connection to display",
    options=list(selector_options),
    label_visibility="collapsed",
)
selected_scenario = selector_options[selected_label]
selected_edge = connector_edges.loc[
    connector_edges["scenario_id"].astype(str) == selected_scenario
]

figure = make_network_figure(
    edges=edges,
    max_edges=len(edges),
    extra_edges=selected_edge,
    height=560,
)
st.plotly_chart(figure, width="stretch")
st.caption("")

with st.expander("Supporting analysis and data notes"):
    st.markdown(
        f"""
        - **Data version:** `{run.name}`
        - **Analysis date:** {format_analysis_date(manifest.get("created_at"))}
        - **Original comparison records:** {len(results)}
        - **Distinct connection concepts shown:** {len(unique_results)}

        Multiple original rows can describe the same physical endpoint pair under different nearby-road labels.
        When records share the same endpoint pair, this view retains the highest reported performance result and
        combines related nearby-road labels. The assumed speed and lane count are calculation inputs, not proposed
        design standards.
        """
    )

    technical = unique_results.copy()
    technical = technical.rename(
        columns={
            "Candidate": "Planning concept",
            "Nearby source labels": "Nearby corridors",
            "improve_delay_pct": "Estimated delay reduction (%)",
            "improve_delay_veh_hours": "Estimated delay reduction (veh-hours)",
            "connector_length_m": "Straight-line distance (m)",
            "connector_speed_kph": "Calculation speed (km/h)",
            "connector_lanes": "Calculation lane count",
        }
    )
    st.dataframe(
        technical[
            [
                "Planning concept",
                "Nearby corridors",
                "Estimated delay reduction (%)",
                "Estimated delay reduction (veh-hours)",
                "Straight-line distance (m)",
                "Calculation speed (km/h)",
                "Calculation lane count",
            ]
        ],
        width="stretch",
        hide_index=True,
    )
