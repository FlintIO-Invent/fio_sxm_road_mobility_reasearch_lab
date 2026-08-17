from __future__ import annotations

import pandas as pd
import streamlit as st
from apps.executive import (
    apply_executive_style,
    executive_header,
    format_analysis_date,
    option_card,
    screening_notice,
)

from sxm_mobility.experiments.run_manager import list_runs, read_manifest

st.set_page_config(page_title="Evidence & Limitations | SXM Mobility", page_icon="◈", layout="wide")
apply_executive_style()

executive_header(
    eyebrow="Evidence framework",
    title="A structured basis for prioritisation and strategic planning",
    deck=(
        "This assessment combines a digital representation of Sint Maarten’s "
        "road network with estimated peak-hour travel demand to show where network "
        "pressure is likely to concentrate, how performance changes under different "
        "conditions, and which strategic options warrant further investigation."
    ),
)
screening_notice(
    "Transparency note — Travel demand, speeds, and road capacity are currently " \
    "based on planning estimates. Local measurements and technical validation are " \
    "required " \
    "before detailed design, funding decisions, or firm delivery commitments."
)

st.subheader("What this brief is designed to support")
useful_columns = st.columns(3, gap="medium")
with useful_columns[0]:
    option_card(
        label="Prioritise",
        title="Focus fieldwork where it matters most",
        body="Identify the corridors and junctions where traffic counts, measured travel times, queue observations, and operational reviews can provide the greatest decision value.",
    )
with useful_columns[1]:
    option_card(
        label="Compare",
        title="Evaluate strategic directions",
        body="Compare demand-management and network-improvement options on a consistent basis to identify which approaches warrant further development and feasibility assessment.",
    )
with useful_columns[2]:
    option_card(
        label="Structure",
        title="Define the next decision stage",
        body="Turn the findings into a focused programme of validation, option development, and decision points for subsequent planning and technical review.",
        accent="violet",
    )

st.subheader("How the assessment is structured")
steps = st.columns(3, gap="large")
with steps[0]:
    st.markdown("#### 01 · Network foundation")
    st.write("Roads and junctions are represented as a connected digital network with estimated travel speeds, capacity, and routing characteristics.")
with steps[1]:
    st.markdown("#### 02 · Peak-hour performance")
    st.write("Estimated peak-hour trips are assigned across the network to identify where congestion forms and how it affects journey times, delay, and route choice.")
with steps[2]:
    st.markdown("#### 03 · Strategic comparison")
    st.write("Demand and connectivity scenarios are tested against the same baseline to show how network performance could respond under different planning conditions.")

st.subheader("What remains to be confirmed")
limits = pd.DataFrame(
    [
        {
            "Area requiring confirmation": "Estimated travel demand",
            "Why it matters": "Trip volumes and origins are planning assumptions, not measured behaviour.",
            "Next evidence step": "Traffic counts, travel surveys, and observed route patterns",
        },
        {
            "Area requiring confirmation": "Indicative speed and road capacity",
            "Why it matters": "Corridor priorities may change once local conditions are incorporated.",
            "Next evidence step": "Observed speeds, lane use, queues, and road operations",
        },
        {
            "Area requiring confirmation": "Junction and turning delay",
            "Why it matters": "Signals, priority rules, and turning conflicts are not yet fully represented.",
            "Next evidence step": "Turning counts, signal timings, and junction observations",
        },
        {
            "Area requiring confirmation": "Delivery and wider impacts",
            "Why it matters": "A strong mobility result is not yet an investment recommendation.",
            "Next evidence step": "Land, safety, cost, environment, equity, and constructability checks",
        },
    ]
)
st.dataframe(limits, width="stretch", hide_index=True)

st.subheader("Appropriate use")
st.info(
    "Use this brief to set priorities, commission the next evidence, and develop comparable options. It should "
    "not be used by itself to approve a road project, set a statutory target, forecast economic benefits, or "
    "promise a travel-time outcome."
)

with st.expander("Analysis provenance"):
    provenance_rows: list[dict[str, object]] = []
    for experiment, label in [
        ("baseline", "Network performance"),
        ("demand_reduction", "Peak-hour demand"),
        ("bottleneck_bypass", "Network improvements"),
    ]:
        runs = list_runs(experiment)
        if not runs:
            continue
        run = runs[0]
        manifest = read_manifest(run)
        provenance_rows.append(
            {
                "Analysis": label,
                "Data version": run.name,
                "Date": format_analysis_date(manifest.get("created_at")),
                "Calculation iterations": manifest.get("msa_iters"),
            }
        )

    if provenance_rows:
        st.dataframe(pd.DataFrame(provenance_rows), width="stretch", hide_index=True)
    st.caption(
        "The performance and strategy comparisons were prepared as separate planning analyses. The executive "
        "summary does not present them as one fully integrated investment ranking."
    )
