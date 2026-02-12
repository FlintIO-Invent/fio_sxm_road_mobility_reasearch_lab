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

### What it Produces

- **Baseline congestion map** – Top bottlenecks (edges) and critical intersections (Problem)
- **Scenario ranking** – Which new links or route changes reduce delay the most (Solution)
""")

st.markdown("---")


st.subheader("Experimental Design")
st.write(
    """
In this model, intersections are represented as nodes and road segments as edges, and each edge is enriched with 
operational properties such as free-flow travel time and capacity. Traffic demand is introduced as origin-destination 
trips that represent vehicles moving through the network, and these trips are generated in a way that intentionally concentrates movement on the most relevant 
corridors:origins and destinations are sampled with weights that favor high-importance parts of the network, so the simulations “zone in” on the roads people actually 
rely on rather than spreading demand evenly across side streets. Once demand is applied, the model assigns trips through the network and updates each road segment’s travel 
cost as flows increase, meaning heavily used or capacity-constrained segments become “heavier” and naturally emerge as the system’s critical bottlenecks. A baseline run establishes 
current network performance and identifies the road segments that contribute the most to overall delay, after which scenario tests modify the network—such as increasing capacity on a corridor, 
simulating a closure, or adding a connector—and rerun the same demand to measure how total delay and travel time change. This produces a ranked, evidence-based view of which interventions deliver the 
strongest island-wide benefit and where targeted improvements are likely to have the greatest impact.
    
    """
)

st.subheader("Data sources")
st.write("- OpenStreetMap (roads)\n- customizable origin destination demand / scenarios\n- (Optional) counts / speeds if available")

st.subheader("How to use")
st.write("Go to **Dashboards** → set filters in the sidebar → explore the map and KPIs.")

st.markdown("---")
st.subheader("Notes & limitations")
st.info("This is a prototype. Capacities/speeds may be proxies until calibrated with local counts.")
