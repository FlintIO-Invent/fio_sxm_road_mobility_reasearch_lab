import streamlit as st

st.set_page_config(
    page_title="St. Maarten Road Mobility Research Lab",
    layout="wide"
)

st.title("St. Maarten Road Mobility Research Lab")
st.subheader("SXM Mobility Graph Lab — What This Experiment Is Doing")

st.markdown("""
### 1️⃣ Turning Roads Into a Digital Network

In the **SXM Mobility Graph Lab**, we ran a traffic “stress test” on Sint Maarten’s road network to identify where congestion is most likely to build and which roads are most critical to keeping the island moving.

First, we converted the island’s road system into a computer-readable network:

- Every **intersection** becomes a node  
- Every **road segment** becomes a link  

Each road segment includes real-world attributes such as:
- Length  
- Direction (one-way or two-way)  
- Estimated travel speed  
- Approximate vehicle capacity  

This allows the model to treat major corridors differently from neighborhood streets — just like real drivers do.

---

### 2️⃣ Simulating a Busy Hour

Next, we simulated a peak traffic hour by generating thousands of trips moving across the island.

The model then “drives” those trips through the network:

- When too many trips use the same road, congestion increases.
- As congestion increases, travel time slows down.
- Drivers (in the simulation) begin shifting to alternate routes.
- This process repeats until traffic stabilizes into a realistic pattern.

The result is a balanced traffic distribution that reflects how congestion spreads through the system.

---

### 3️⃣ Identifying Bottlenecks

The most important output is the **bottleneck ranking**.

These are not simply slow roads — they are road segments that:

- Carry heavy traffic
- Experience significant congestion
- Create system-wide ripple effects when delayed

Improving a lightly used side street has minimal impact.  
Improving a high-impact corridor can reduce delays for thousands of trips.

---

### 4️⃣ What the Baseline Shows

In this baseline scenario:

- Average travel time per trip is only a few minutes.
- Congestion adds a modest delay per vehicle on average.
- Total system delay appears large only because it accumulates across thousands of drivers.

This means the system is sensitive — small improvements in the right place can create measurable island-wide benefits.

---

### 5️⃣ Moving Into “What-If” Testing

The next phase introduces scenario testing:

- Increasing capacity on bottleneck roads  
- Adjusting directional flow  
- Adding connector roads  
- Simulating closures or disruptions  

Each scenario is scored based on how much total congestion is reduced across the entire network.

The objective is to generate a clear, evidence-based shortlist of road improvements — supported by maps, metrics, and visuals that policymakers and the public can easily understand.
""")
