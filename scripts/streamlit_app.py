from pathlib import Path
import streamlit as st
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
PAGES_DIR = BASE_DIR / "pages"

# Home Pages
overview = st.Page(
    str(PAGES_DIR / "home" / "1_overview.py"),
    title="Overview",
    icon=":material/overview_key:",
    default=True,
)

design = st.Page(
    str(PAGES_DIR / "home" / "2_design.py"),
    title="Design",
    icon=":material/architecture:",
)

# Experiment Pages
island_traffic_stress_test = st.Page(
    str(PAGES_DIR / "baseline" / "1_island_traffic_stress_test.py"),
    title="Island Traffic Stress Test",
    icon=":material/hematology:",
)

# Solutioning Experiments 
demand_reduction = st.Page(
    str(PAGES_DIR / "experiments" / "1_run_demand_reduction.py"),
    title="Demand Reduction",
    icon=":material/arrow_range:",
)

# Navigation
pg = st.navigation({
    "Home": [overview, design],
    "Baselines": [island_traffic_stress_test],
    "Solution Experiments": [demand_reduction],
})

pg.run()
