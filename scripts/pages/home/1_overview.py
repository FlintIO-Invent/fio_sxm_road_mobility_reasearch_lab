import streamlit as st

st.set_page_config(page_title="St. Maarten Road Mobility Research Lab", layout="wide")

st.title("St. Maarten Road Mobility Research Lab")
st.markdown("""
Sint. Maarten Road Mobility Research Lab is a experimental practical decision-support initiative that transforms Sint Maarten’s 
road system into a graph-powered mobility model. Using open road network data and locally available 
inputs (traffic counts, observations, stakeholder feedback), the lab simulates traffic flows, measures congestion and network fragility, 
and identifies the intersections and corridors that most influence island-wide travel time and safety outcomes.

The lab then runs “what-if” scenarios such as new connector roads, 
direction changes, capacity upgrades, incident/closure tests, and safety-focused redesigns to produce 
a ranked list of short-term actions and longer-term infrastructure priorities. All outputs are delivered as 
consultation-ready maps and visuals that the public and institutional partners can easily understand and validate.

""")

st.markdown("---")
st.header("How to use this dashboard")
st.write(
    "There are alot of cool things being done in the background, but the dashboard may not feel as intuitive and user-friendly since its approach is for a more scientific approach." 
    "Here’s a quick guide to what you’re seeing and how to interact with it:\n\n"
)
st.subheader("Data sources")
st.write(
    "- OpenStreetMap road network (links, nodes, geometry, free-flow time, capacity)\n"
    "- Real world Synthetic data (e.g., traffic counts, probe/GPS speeds, surveys)\n"
    "- Customizable parameters that control origin & destination demand generation (e.g., trip volumes, friction/decay, zoning)\n"
)


st.subheader("Tabs & dashboards")

c1, c2 = st.columns(2)

with c1:
    st.markdown("### 🧱 Baselines")
    st.write(
        "Your **reference runs**. Use these to understand the default network + demand assumptions, "
        "and to anchor comparisons for any interventions."
    )

with c2:
    st.markdown("### 🛠️ Solution experiments")
    st.write(
        "Your **intervention runs**. Use these to evaluate proposed changes and compare results "
        "against a baseline (including delta views)."
    )

with st.expander("Baseline dashboard: what the sidebar controls do?", expanded=False):
    st.write(
        "The **Baseline** dashboard shows the default network, demand assumptions, and traffic assignment results.\n\n"
        "**Sidebar controls are typically associated with:**"
    )

    b1, b2 = st.columns(2)
    with b1:
        st.markdown(
            "- **Experiment Run History**: There can be many baselines runs for many reasons this sidebar feature shows which saved baseline run you’re viewing\n"
            "- **Map Render options**: used with the road network map toggle visibility of various map layers (e.g., road names, labels, traffic flow)\n"
        )
    # with b2:
    #     st.markdown(
    #         "- **Assignment settings**: method/iterations (e.g., MSA steps) + outputs\n"
    #         "- **Map metric**: what the links are colored by (volume, speed, delay, V/C…)\n"
    #         "- **Bottleneck settings**: top-N + thresholds for ranking/highlighting\n"
    #         "- **KPI settings**: which KPIs to show + aggregation level"
    #     )

    st.caption(
        "Tip: If results look different than expected, check **Experiment Run History**"
        "irst those usually drive the biggest changes."
    )

with st.expander("Solution experiment dashboard: what the sidebar controls do?", expanded=False):
    st.write(
        "The **Solution Experiment** dashboard shows an intervention (network/demand/operations change) "
        "and helps you compare it against a baseline.\n\n"
        "**Sidebar controls are typically associated with:** Currently in development.."
    )

    s1, s2 = st.columns(2)
    # with s1:
    #     st.markdown(
    #         "- **Experiment selection**: choose the solution/intervention run\n"
    #         "- **Comparison mode**: Solution, Baseline, or **Delta (Solution − Baseline)**\n"
    #         "- **Geography filters**: zoom into a district/zone/corridor\n"
    #         "- **Demand scenario** (if varied): same as baseline or adjusted demand"
    #     )
    # with s2:
    #     st.markdown(
    #         "- **Network change toggles**: enable/disable specific modifications (if supported)\n"
    #         "- **Map metric**: show absolute metrics or **change in** metrics (delta)\n"
    #         "- **Impact thresholds**: filter to “meaningful” changes (e.g., delay ↓ > X)\n"
    #         "- **KPI comparison**: absolute vs % change + aggregation level"
    #     )

    # st.caption(
    #     "Tip: Start with **Delta** to spot where things improve/worsen, then switch to **Solution** "
    #     "to confirm the new absolute levels are acceptable."
    # )



st.markdown("---")
st.subheader("Notes & limitations")

st.warning(
    "This is a prototype model. While the road geometry and network structure are based on OpenStreetMap, "
    "several inputs are currently proxies until we calibrate with local measurements.\n\n"
    "In particular:\n"
    "- Travel demand (Origin-Destination trips and total vehicles per hour) is synthetic.\n"
    "- Free-flow travel time (t0) is derived from road length and assumed/OSM speed limits.\n"
    "- Road capacity is approximated (e.g., a per-lane vehicles/hour rule).\n"
    "- Congestion response uses default BPR parameters (alpha/beta), not Sint Maarten–calibrated values.\n"
    "- Intersection effects (signals, turning delay, priority rules) are not yet fully represented.\n\n"
    "Although we follow industry statndard principles, the dashboard is best interpreted as a screening tool (where congestion concentrates"
    " and which corridors matter most), not a final engineering forecast, until local counts and observed travel times are added, but provides a starting point for discussion and improvements."
)



