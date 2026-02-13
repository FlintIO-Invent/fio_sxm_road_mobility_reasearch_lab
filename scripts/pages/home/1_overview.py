import streamlit as st

st.set_page_config(page_title="St. Maarten Road Mobility Research Lab", layout="wide")

st.title("St. Maarten Road Mobility Research Lab")
st.markdown("""
Sint. Maarten Road Mobility Research Lab is a experimental practical decision-support initiative that transforms Sint Maarten’s 
road system into a graph-powered mobility model. Using open road network data and locally available 
inputs (traffic counts, observations, stakeholder feedback), the lab simulates traffic flows, measures congestion and network fragility, 
and identifies the intersections and corridors that most influence island-wide travel time and safety outcomes.

The lab then runs “what-if” scenarios — such as new connector roads, 
direction changes, capacity upgrades, incident/closure tests, and safety-focused redesigns — to produce 
a ranked list of short-term actions and longer-term infrastructure priorities. All outputs are delivered as 
consultation-ready maps and visuals that the public and institutional partners can easily understand and validate.

""")

st.markdown("---")


st.subheader("Data sources")
st.write("- OpenStreetMap \n- customizable origin destination demand & scenarios\n- counts & speeds if available")

st.subheader("How to use")
st.write("Go to **Dashboards** → set filters in the sidebar → explore the map and KPIs.")

st.markdown("---")
st.subheader("Notes & limitations")
st.info("This is a prototype. Capacities & speeds may be proxies until calibrated with more local data.")
