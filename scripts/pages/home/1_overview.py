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


st.subheader("Data sources")
st.write("- OpenStreetMap \n- Customizable parameters that control origin & destination demands ect.\n- Counts & speeds from local or ingestable sources")

st.subheader("How to use")
st.write("Explore sidebar  → Go to various experiment **Dashboards** → Set filters in the sidebar → Interact with the map and KPIs.")

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
    "and which corridors matter most), not a final engineering forecast, until local counts and observed travel times are added, but provides a starting point for discussion and improvements."
)



