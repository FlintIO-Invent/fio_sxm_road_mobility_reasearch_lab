from pathlib import Path
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent 
PAGES_DIR = BASE_DIR / "pages"

home = st.Page(
    str(PAGES_DIR / "home" / "1_overview.py"), title="Overview", icon=":material/home:", default=True
)

roads_most_traveled = st.Page(
    str(PAGES_DIR / "experiments" / "1_roads_most_traveled.py"), title="Roads Most Traveled", icon=":material/experiment:",
)

pg = st.navigation({"Home": [home],
                    "Experiments": [roads_most_traveled], 
                    })
pg.run()
