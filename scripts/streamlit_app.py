from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
PAGES_DIR = BASE_DIR / "pages"

# Home Pages
overview = st.Page(
    str(PAGES_DIR / "home" / "1_overview.py"),
    title="Executive Summary",
    icon=":material/space_dashboard:",
    default=True,
)

design = st.Page(
    str(PAGES_DIR / "home" / "2_design.py"),
    title="Evidence & Limitations",
    icon=":material/info:",
)

# Experiment Pages
island_traffic_stress_test = st.Page(
    str(PAGES_DIR / "baseline" / "1_island_traffic_stress_test.py"),
    title="Network Performance",
    icon=":material/traffic:",
)

# Solutioning Experiments 
demand_reduction = st.Page(
    str(PAGES_DIR / "experiments" / "1_run_demand_reduction.py"),
    title="Peak-Hour Demand",
    icon=":material/trending_down:",
)

# Solutioning Experiments 
bottleneck_bypass = st.Page(
    str(PAGES_DIR / "experiments" / "2_run_bottleneck_bypass.py"),
    title="Network Improvements",
    icon=":material/alt_route:",
)

# Navigation
pg = st.navigation({
    "Strategic brief": [overview],
    "Current performance": [island_traffic_stress_test],
    "Strategy options": [demand_reduction, bottleneck_bypass],
    "Reference": [design],
})

pg.run()
