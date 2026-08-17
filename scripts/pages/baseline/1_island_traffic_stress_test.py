from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from apps.components import make_network_figure
from apps.executive import (
    apply_executive_style,
    decision_callout,
    executive_header,
    format_analysis_date,
    screening_notice,
)

from sxm_mobility.experiments.run_manager import (
    base_dir,
    baseline_bottlenecks_path,
    baseline_kpi_path,
    list_runs,
    read_manifest,
)
from sxm_mobility.helpers import clean_osm_value

st.set_page_config(page_title="Network Performance | SXM Mobility", page_icon="◈", layout="wide")
apply_executive_style()


@st.cache_data
def read_parquet_cached(path_str: str, mtime: float) -> pd.DataFrame:
    return pd.read_parquet(path_str)


def load_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return read_parquet_cached(str(path), path.stat().st_mtime)


def pressure_label(value: float) -> str:
    if value >= 2:
        return "Very high"
    if value >= 1.2:
        return "High"
    if value >= 1:
        return "Elevated"
    return "Moderate"


baseline_runs = list_runs("baseline")
if not baseline_runs:
    executive_header(
        eyebrow="Current performance",
        title="The network performance update is not yet available",
        deck="Complete the latest assessment to populate the corridor and journey findings.",
    )
    st.stop()

baseline_run = baseline_runs[0]
manifest = read_manifest(baseline_run)
kpi = load_parquet(baseline_kpi_path(baseline_run))
bottlenecks = load_parquet(baseline_bottlenecks_path(baseline_run))
edges = load_parquet(base_dir() / "edges.parquet")

if kpi.empty or bottlenecks.empty or edges.empty:
    st.error("The latest network performance update is incomplete.")
    st.stop()

for column in ["u", "v", "key"]:
    bottlenecks[column] = pd.to_numeric(bottlenecks[column], errors="coerce").astype("Int64")
    edges[column] = pd.to_numeric(edges[column], errors="coerce").astype("Int64")

snapshot = kpi.iloc[0]
island_delay = float(snapshot.get("delay", 0))
avg_trip = float(snapshot.get("avg_travel_time_min", 0))
avg_delay = float(snapshot.get("avg_delay_min", 0))
modeled_demand = float(snapshot.get("total_demand_vph", 0))

segments = bottlenecks.merge(edges, on=["u", "v", "key"], how="left", suffixes=("", "_road"))
segments["Corridor"] = segments.get("name", pd.Series(index=segments.index, dtype=object)).map(
    clean_osm_value
)
segments["Corridor"] = segments["Corridor"].fillna(
    segments.get("highway", pd.Series(index=segments.index, dtype=object)).map(clean_osm_value)
)
segments["Corridor"] = segments["Corridor"].fillna("Unnamed corridor")

corridors = (
    segments.groupby("Corridor", as_index=False)
    .agg(
        modeled_delay=("delay", "sum"),
        peak_pressure=("v_c", "max"),
        priority_segments=("delay", "size"),
    )
    .sort_values("modeled_delay", ascending=False)
)
denominator = island_delay if island_delay > 0 else float(corridors["modeled_delay"].sum())
corridors["share"] = corridors["modeled_delay"] / denominator * 100
corridors["pressure"] = corridors["peak_pressure"].map(pressure_label)

top_corridor = str(corridors.iloc[0]["Corridor"])
top_corridor_share = float(corridors.iloc[0]["share"])
top_three_share = float(corridors.head(3)["share"].sum())

executive_header(
    eyebrow=f"Current performance · {format_analysis_date(manifest.get('created_at'))}",
    title="A small number of corridors account for most of the estimated network delay",
    deck=(
        f"Priority segments along {top_corridor} account for an estimated {top_corridor_share:.0f}% of the island-wide congestion delay. "
        f"Together, the three leading corridors represent approximately {top_three_share:.0f}%, highlighting where targeted investigation could have the greatest value."
    ),
)
screening_notice()

metric_columns = st.columns(4)
metric_columns[0].metric("Chosen trip estimate", f"{modeled_demand:,.0f}")
metric_columns[1].metric("Chosen journey estimate", f"{avg_trip:.1f} min")
metric_columns[2].metric("Chosen delay estimate", f"{avg_delay:.1f} min")
metric_columns[3].metric("Top-3 estimate", f"{top_three_share:.0f}%")

decision_callout(
    title="Focus the next round of fieldwork on the highest-priority corridors.",
    body=(
        "Targeted peak-hour counts, turning-movement surveys, queue observations, and measured travel times can validate "
        "the current findings and provide the evidence needed to develop practical interventions."
    ),
)

st.subheader("Where network pressure is concentrated")
priority_view = corridors.head(5).copy()
priority_view["Share of island delay"] = priority_view["share"].map(lambda value: f"{value:.1f}%")
priority_view["Relative pressure"] = priority_view["pressure"]
st.dataframe(
    priority_view[["Corridor", "Share of island delay", "Relative pressure"]],
    width="stretch",
    hide_index=True,
)

st.subheader("Network view")
st.caption("Highlighted road segments make the largest estimated contribution to peak-hour delay.")
figure = make_network_figure(
    edges=edges,
    max_edges=len(edges),
    bottlenecks=bottlenecks.sort_values("delay", ascending=False).head(15),
    top_n=15,
    height=560,
)
st.plotly_chart(figure, width="stretch")

with st.expander("Supporting analysis and data notes"):
    st.markdown(
        f"""
        - **Data version:** `{baseline_run.name}`
        - **Analysis date:** {format_analysis_date(manifest.get("created_at"))}
        - **Study area:** {manifest.get("place_query", "Sint Maarten")}
        - **Peak-hour trips represented:** {modeled_demand:,.0f}

        “Relative pressure” translates the estimated road flow compared with indicative road capacity into
        plain language. Capacity, speed, and travel demand still require local confirmation.
        """
    )

    technical_view = segments.sort_values("delay", ascending=False).head(25).copy()
    technical_view = technical_view.rename(
        columns={
            "flow": "Estimated flow (veh/h)",
            "capacity": "Indicative capacity (veh/h)",
            "v_c": "Flow / capacity indicator",
            "delay": "Estimated segment delay (veh-hours)",
        }
    )
    st.dataframe(
        technical_view[
            [
                "Corridor",
                "Estimated flow (veh/h)",
                "Indicative capacity (veh/h)",
                "Flow / capacity indicator",
                "Estimated segment delay (veh-hours)",
            ]
        ],
        width="stretch",
        hide_index=True,
    )
