# SXM Mobility Graph Lab - SXM Mobility Graph Lab

**SXM Mobility Graph Lab** is a practical decision-support initiative that transforms Sint Maarten’s road system into a **NetworkX-powered mobility model**. Using open road network data and locally available inputs (counts, observations, stakeholder feedback), the project simulates traffic flows, measures congestion and network fragility, and pinpoints the **intersections and corridors that most influence island-wide travel time and safety outcomes**.

The lab then runs “what-if” scenarios—such as new connector roads, direction changes, capacity upgrades, incident/closure tests, and safety-focused redesigns—to produce a ranked list of **short-term actions** and **longer-term infrastructure priorities**, supported by consultation-ready maps and visuals that the public and partners can understand and validate.

### What it produces (quick bullets)

- **Baseline congestion map** + top bottlenecks (edges) and critical intersections (nodes)
- **Scenario ranking**: which new links/route changes reduce delay the most
- **Resilience tests**: what happens if a key road is blocked (accident/works)
- **Safety overlay**: risk-priority corridors near schools, crossings, high-conflict junctions
- **Consultation visuals**: simple maps + “before/after” impact summaries for stakeholders


SXM Mobility Graph Lab is a Python project that turns Sint Maarten’s road network into a graph, simulates traffic demand (OD trips) moving through that graph, computes congestion/bottlenecks, and then tests what-if interventions (scenarios) to see which changes reduce congestion the most.

###  It’s designed to grow into:

- Streamlit for interactive dashboards + stakeholder demos
- Django later for a portal (users/roles, scenario library, audits, uploads)
- Shareable visuals via Plotly, plus optional exports for other tools.

## Dependency 

- **geo** → osmnx, geopandas, shapely, pyproj *(OSM network + spatial)*
- **viz** → plotly, folium *(maps/plots)*
- **dashboard** → streamlit *(UI)*
- **api** → fastapi, uvicorn *(scenario API)*
- **jobs** → celery, redis *(async runs later)*
- **db** → sqlalchemy, psycopg *(Postgres/PostGIS later)*
- **dev** → ruff, black, pytest, pre-commit, mypy *(tooling)*
- **core**: network + assignment primitives



---

## Repo structure (already created)

### `src/sxm_mobility/` modules
- **network/** *(build/simplify/edge attributes)*
- **demand/** *(OD generation)*
- **assignment/** *(BPR + MSA + metrics)*
- **scenarios/** *(catalog/runner/evaluator)*
- **viz/** *(mapping helpers)*
- **api/** *(FastAPI app scaffold)*

### `scripts/` runnable entry points
- **build_graph.py** *(OSMnx → GraphML)*
- **run_baseline.py** *(bottlenecks + fragility)*
- **run_scenarios.py** *(example scenario ranking)*
- **streamlit_app.py** *(starter dashboard)*

### Tests + docs
- **tests/** *(basic unit tests for assignment + metrics)*
- **docs/ARCHITECTURE.md** *(quick overview)*


## Quick start (uv)

```bash
# 1) Create venv + install core + dev tools
uv sync --extra dev --extra geo --extra viz --extra dashboard --extra api
uv sync --extra geo --extra io --extra viz --extra dashboard --extra api --extra jobs --extra db --extra dev

# 4) Run Graph Baselines for various experimentrs
uv run python scripts/build_graph.py
uv run python scripts/run_baseline.py
uv run python scripts/run_scenarios.py


# run vizualizer
uv run streamlit run scripts/streamlit_app.py

# 4) Run Experiments
uv run python src/sxm_mobility/experiments/run_baseline.py
uv run python src/sxm_mobility/experiments/run_scenarios.py

# 4) (Optional) Run API
uv run uvicorn sxm_mobility.api.app:app --reload
```


Install extras via:

```bash
uv sync --extra geo --extra viz --extra dev
```

## Repo layout

```text
sxm-mobility-graph-lab/
  data/                  # local datasets (ignored by git)
  docs/                  # notes, architecture, decisions
  notebooks/             # exploration
  scripts/               # runnable entrypoints
  src/sxm_mobility/      # library code
  tests/                 # tests
```
---

# SXM Mobility Graph Lab — Step-by-Step Project Overview


## Key concepts
- **Graph**
  - **Nodes** = intersections / points
  - **Edges** = road segments (directed if one-way)
- **OD (Origin–Destination)**
  - Trip intent list: `(origin_node, destination_node, demand)`
- **Demand**
  - “How many trips want to happen” in a time window (e.g., vehicles/hour).
  - Not traffic yet—traffic happens after assignment.
- **Assignment**
  - Routes OD demand onto the network → produces **edge flows** (traffic per road segment).
- **Congestion / Delay**
  - Additional travel time caused by flow relative to capacity.
- **Scenario**
  - A controlled change to the network (capacity changes, closures, new links) to evaluate impact.

---

## Pipeline steps (in order)

### Step 1 — Build the road network graph
**Run**
```bash
uv run python scripts/build_graph.py
```

**What happens**
1. **Download** OSM road data for Sint Maarten using OSMnx.
2. **Build** a directed **MultiDiGraph**:
   - nodes = OSM node IDs
   - edges = road segments (can have multiple edges between the same nodes, distinguished by `key`)
3. **Export artifacts** so downstream steps don’t re-download or recompute geometry.

**Outputs** (`data/processed/artifacts/`)
- `graph.gpickle`  
  Canonical engine artifact (fast, full fidelity for Python computations)
- `graph.graphml`  
  Shareable artifact (sanitized so GraphML can store it)
- `nodes.parquet`  
  Node table for dashboards/DB
- `edges.parquet`  
  Edge table for dashboards/DB (includes `geometry_wkt`)

---

### Step 2 — Run baseline traffic assignment + bottleneck detection
**Run**
```bash
uv run python scripts/run_baseline.py
```

**What happens**
1. **Load** `graph.gpickle` (the engine graph).
2. **Generate or load OD demand pairs**:
   - Origins/destinations must be **valid graph nodes**
   - Demand values represent “trip intensity” (e.g., vehicles/hour)
3. **Assign traffic (MSA-style loop)**:
   - Compute edge travel times from current flow (congestion function)
   - Find shortest paths for OD pairs using those times
   - Load demand onto edges → produces edge flows
   - Repeat for multiple iterations to stabilize
4. **Compute KPIs + bottlenecks**:
   - system KPIs (travel time, delay)
   - top congested edges (by delay or v/c)

**Outputs** (`data/processed/`)
- `results_baseline.parquet`  
  Baseline KPI summary (system-level metrics)
- `baseline_bottlenecks.parquet`  
  Ranked bottleneck edges (edge-level metrics)

---

### Step 3 — Run scenario testing (what-if interventions)
**Run**
```bash
uv run python scripts/run_scenarios.py
```

**What happens**
1. **Load** baseline graph + OD demand (or regenerate consistently).
2. **Compute baseline reference** (or load baseline KPIs).
3. For each scenario:
   - **Apply change** to the graph (examples):
     - increase capacity on selected edges
     - close an edge (roadworks / incident)
     - add a connector edge (simulate new road link)
   - **Re-run assignment**
   - **Evaluate deltas** vs baseline (improvement or worsening)
4. **Rank scenarios** by improvement (e.g., biggest delay reduction).

**Outputs** (`data/processed/`)
- `results_scenarios.parquet`  
  Scenario ranking table (baseline vs scenario KPIs + deltas)
- `scenario_details.parquet`  
  Scenario parameters and metadata (reproducibility)

---

### Step 4 — Visualize results in Streamlit (maps + charts)
**Run**
```bash
uv run streamlit run scripts/streamlit_app.py
```

**What happens**
1. Streamlit **reads artifacts** (it does not need to recompute heavy steps):
   - `edges.parquet` → network geometry for mapping
   - `baseline_bottlenecks.parquet` → overlay hotspots
   - `results_baseline.parquet` → baseline KPIs
   - `results_scenarios.parquet` → scenario comparison tables
2. Plotly renders:
   - the road network on **OpenStreetMap tiles**
   - bottleneck overlays (thicker lines / hover info)
   - KPI tables/charts and scenario comparisons

**Outcome**
A shareable stakeholder interface for:
- “Where are the worst congestion points?”
- “Which interventions reduce congestion most?”
- “How do scenarios compare in KPI impact?”

---

## Why artifacts matter (the architecture pattern)
The project is intentionally structured as:
- `scripts/` produce stable **artifacts** in `data/processed/`
- **apps (Streamlit/Django)** read those artifacts
- `src/sxm_mobility/` stays clean and reusable (engine code)

This separation makes it easy to:
- rerun heavy compute only when needed
- keep dashboards fast
- scale to multi-user + database later

---

## Growth path (how this becomes a real platform)

### Short term: Streamlit demo
- map of the road network
- bottleneck overlays
- scenario picker + KPI deltas
- exportable visuals (HTML)

### Mid/long term: Django portal
- user management + roles (VROMI/UNOPS/etc.)
- scenario library + run history
- upload local data (traffic counts, zones, closures)
- audit trail + report generation

### Database: PostGIS
- store edges/nodes/zones/results in a durable way
- support multi-user, multi-scenario history
- integrate with other systems and GIS tools



## Modeling

1. Ingest graph (OSMnx) → NetworkX MultiDiGraph
2. Add baseline edge attributes: `t0`, `capacity`
3. Generate OD demand (synthetic v1 → zones + calibrated v2)
4. Traffic assignment (BPR + MSA)
5. Compute metrics (delay, bottlenecks, fragility)
6. Scenario runner (apply change → re-assign → compare deltas)
7. Visualize + export

## Why MultiDiGraph?
Road networks can have parallel edges (e.g., divided roads, ramps). MultiDiGraph preserves this.

## MSA

**Method of Successive Approximations (MSA)** iteratively assigns traffic flows until user travel times stabilize, reaching equilibrium. Convergence means the system finds the best routes given congestion; researchers often plot the **relative gap** to show how quickly (or slowly) it converges.

### Key components and formula

**Formula (BPR volume–delay function):**

\[
T = T_{0}\times \left[1+\alpha \times \left(\frac{V}{C}\right)^{\beta}\right]
\]

**Where:**
- \(T\) — **Congested travel time**: actual time to traverse a road segment under current traffic.
- \(T_{0}\) — **Free-flow travel time**: time to traverse the segment with no traffic.
- \(V\) — **Volume**: observed traffic flow.
- \(C\) — **Capacity**: maximum flow the road can handle.
- \(\alpha\) — **Scaling parameter** (often \(0.15\)).
- \(\beta\) — **Shape parameter** (often \(4\)); higher values mean a sharper rise in congestion.

### How it works (congestion effect)

- **Low flow (\(V<C\))**: \(\left(\frac{V}{C}\right)^{\beta}\) is small, so \(T \approx T_{0}\).
- **Approaching capacity (\(V\rightarrow C\))**: \(\frac{V}{C}\rightarrow 1\), and \(T\) increases noticeably above \(T_{0}\).
- **Over capacity (\(V>C\))**: the function keeps increasing \(T\), representing severe congestion (even though real-world capacity has practical limits).

### Why it matters in traffic modeling

- **Route choice**: makes travel time (cost) sensitive to volume, influencing route decisions in assignment models.
- **Network performance**: helps evaluate infrastructure, signal timing, and demand management by showing how congestion affects travel times.
- **Calibration**: \(\alpha\) and \(\beta\) can be calibrated for specific road types/cities for better accuracy (even though standard defaults exist).

---

## BRP

The **BPR (Bureau of Public Roads) travel time function** is a widely used **volume–delay** function in traffic modeling. It calculates increased travel time as traffic volume approaches road capacity:

\[
T = T_{0}\times \left[1+\alpha \times \left(\frac{V}{C}\right)^{\beta}\right]
\]

**Where:**
- \(T\) is congested travel time,
- \(T_{0}\) is free-flow travel time,
- \(V\) is volume,
- \(C\) is capacity,
- \(\alpha\) (commonly \(0.15\)) and \(\beta\) (commonly \(4\)) control how quickly congestion “kicks in”.

It’s crucial for urban planning and traffic assignment because it links **traffic flow** to **travel cost**, enabling models to represent route choice and congestion impacts realistically.

Awesome — now that it runs, your next step is to **understand the mental model** and then grow the codebase without turning it into spaghetti.

Here’s the “how it works” in plain terms, then a growth roadmap.

---

## The mental model of this project

### 1) You have 3 layers

**A) Data layer (`data/`)**

- Stores **artifacts** so you don’t rebuild everything each run:
  - `graph.gpickle` = canonical engine graph
  - `graph.graphml` = shareable graph
  - `nodes/edges.parquet` = tables for dashboards/DB
  - `results_*.parquet` = outputs

**B) Engine layer (`src/sxm_mobility/`)**

- Reusable library code:
  - build graph, assign flows, evaluate scenarios
- Should never depend on Streamlit or Django.

**C) Delivery layer (`scripts/`, later `streamlit`, later `django`)**

- Entry points that run the engine and write artifacts.
- Streamlit/Django will mostly **read results** + **trigger scenario runs**.

This separation is what lets you scale.

---

## What you’re actually doing (traffic-wise)

### Step 1 — Represent roads as a graph

- Nodes = intersections  
- Edges = road segments  
- Each edge gets attributes like:
  - `t0` free-flow travel time
  - `capacity`
  - `time` congested travel time (changes with flow)
  - `flow` vehicles/hour assigned

### Step 2 — Create demand (OD)

OD = “how many trips from origin to destination”  
This is the *cause* of traffic.

Without OD demand, you only have a road map, not “traffic”.

### Step 3 — Assign demand to routes (flow assignment)

You’re doing an iterative loop (MSA style):

1. Compute edge travel times from current flow (BPR)
2. For each OD pair:
   - find shortest path using current travel times
   - push OD demand along that path
3. Blend new flows into current flows and repeat

Output:

- flow per edge
- congested travel time per edge
- system KPIs (total travel time, total delay)

### Step 4 — Find bottlenecks / criticality

From the baseline results you can identify:

- edges with high `flow/capacity`
- edges with high total delay: `flow * (time - t0)`
- nodes with high “through-flow” importance

### Step 5 — Scenario testing

A “scenario” is just a graph modification:

- add edge
- change capacity
- close edge
- change direction

Then rerun assignment and compare KPIs:

- baseline delay vs scenario delay
- rank scenarios by improvement

That’s your “which links reduce traffic most?” engine.

---

## How to grow the codebase safely (rules)

### Rule 1: Keep the engine pure

In `src/sxm_mobility/`:

- no printing
- no reading from hardcoded paths
- accept inputs (graphs, OD tables, settings)
- return outputs (DataFrames, dict metrics)

Scripts handle I/O.

### Rule 2: Make everything data-driven

Avoid “magic constants” buried in code:

- store scenario configs, OD configs, parameters in YAML/JSON or Pydantic settings:
  - BPR alpha/beta
  - MSA iterations
  - OD volumes
  - scenario list

### Rule 3: Treat artifacts as contracts

Once you choose:

- `edges.parquet` schema
- `results_baseline.parquet` schema

…don’t break them casually. Add new columns instead of renaming.

This makes Streamlit/Django stable.

---

## A practical growth roadmap (what to build next)

### Phase 1 — Make the baseline “credible”

**Add these outputs:**

- Edge KPIs table:
  - `u,v,key, flow, capacity, v_c_ratio, t0, time, delay`
- Node KPIs table:
  - intersection importance proxy (sum incident delays)
- Map export:
  - top 20 bottleneck edges as GeoJSON (for quick visualization)

**Add validation checks:**

- graph connectedness report
- missing capacity or speed assumptions report

---

### Phase 2 — Improve OD generation (biggest realism jump)

Right now OD may be synthetic. Upgrade it by adding “zones”:

- Create zones: Airport, Simpson Bay, Philipsburg, Cole Bay, etc.
- Map nodes to zones (spatial join / bounding polygons)
- Build OD using:
  - population density proxies
  - POI density
  - or stakeholder-supplied weights

Deliverable:

- `od.parquet` + `zones.geojson`

---

### Phase 3 — Make scenario selection smart (not manual)

Instead of “try random edges”, generate candidates:

**Candidate generation ideas:**

- Connect pairs of zones that currently have long travel times
- Connect nodes near bottleneck corridors to create bypasses
- Identify “bridge edges” (high betweenness, high delay) and propose alternative paths around them

Then run top N candidates and rank.

This becomes your “we recommend building X and Y” feature.

---

### Phase 4 — Move from demo to product (Django + Streamlit)

**Streamlit = fast stakeholder demo**

- load results tables
- scenario picker dropdown
- map + KPI deltas

**Django = institutional platform**

- users/roles (VROMI, TEATT, Justice, consultants)
- scenario library (store scenario configs)
- audit log of runs
- export “consultation packs” (PDF summary)

---

## What to read in your code to understand it quickly

1. `scripts/build_graph.py`  
   → shows how artifacts are produced

2. `src/sxm_mobility/assignment/msa.py`  
   → this is the heart of traffic flow simulation

3. `src/sxm_mobility/scenarios/runner.py`  
   → how interventions are applied + evaluated

4. `scripts/run_baseline.py` and `scripts/run_scenarios.py`  
   → show “how engine outputs become artifacts”

---

## Quick exercise to confirm you understand it

Change **one thing** and see the impact:

- double capacity on a known corridor
- rerun baseline and scenarios
- confirm system delay drops and that corridor’s `v/c` improves

That’s the best way to build intuition.

---

If you paste your current folder tree (`tree -L 3`) and the names of your key modules (`msa.py`, `bpr.py`, `runner.py`), I’ll walk you through your code path like a “trace”:

**build_graph → export → od → msa loop → metrics → parquet outputs**

…and point to exactly where you should add:

- better capacities
- time-of-day demand
- zone-based OD
- candidate link generation

## Data Set  element meanings
That JSON object is **one road segment (one edge)** from your road network graph, exported to a table-friendly format.

Think of it as: **an edge from node `u` to node `v`**, with metadata pulled from OpenStreetMap.

Here’s what each field means:

---

## Identity / graph structure

- **`u: 250656239`**  
  The **start node ID** (an OSM node id for an intersection/point).

- **`v: 1033360634`**  
  The **end node ID**.

- **`key: 0`**  
  Because your graph is a **MultiDiGraph**, there can be multiple parallel edges between the same `u` and `v` (e.g., ramps, service lanes). `key` distinguishes them. `0` means “the first one”.

---

## Road source IDs and classification

- **`osmid: "550465100"`**  
  The OpenStreetMap way ID for this road segment.  
  It’s a **string** here because we normalized it for Parquet/Arrow compatibility (sometimes it’s a list when edges get merged).

- **`highway: "primary"`**  
  OSM road type. `"primary"` usually means a main arterial road.

- **`name: "Airport Road"`**  
  The road name from OSM.

---

## Directionality

- **`oneway: true`**  
  This edge is one-way **from `u` → `v`**.

- **`reversed: "False"`**  
  This is typically an OSMnx bookkeeping flag indicating whether the geometry was reversed relative to original OSM direction during processing.  
  It being a **string** `"False"` (not boolean `False`) is due to the same “make everything safe for parquet” conversion.

---

## Geometry / distance

- **`length: 19.160143489700733`**  
  Length of this edge in **meters** (OSMnx calculates this).

- **`geometry_wkt: "LINESTRING (...)"`**  
  The actual line geometry of the road segment in **WKT** format.  
  These coordinates are **(longitude, latitude)**:

  - `(-63.119977, 18.040484)` → `(-63.120091, 18.04051)` → `(-63.12015, 18.040535)`

  This lets you render it easily in:

  - GeoPandas/Shapely (parse WKT)
  - PostGIS
  - Plotly/Mapbox
  - Leaflet/Folium
  - QGIS

---

## Capacity-ish proxies (not yet “traffic-ready”)

- **`lanes: "1"`**  
  Lane count from OSM (often missing or string-typed).

- **`maxspeed: "nan"`**  
  Missing value. Same for:

  - **`bridge`**, **`junction`**, **`access`**  
    These were blank in OSM for this segment; they became `"nan"` strings during export.

---

## What this edge *doesn’t* include yet (for traffic simulation)

To simulate congestion and flow properly, you’ll typically add derived attributes like:

- **`speed_kph`** (from `maxspeed` or OSMnx defaults)
- **`t0`** free-flow travel time (seconds) = `length / speed`
- **`capacity`** vehicles/hour (estimated from `highway`, `lanes`, urban assumptions)
- **`flow`** assigned vehicles/hour (result of your OD assignment)
- **`time`** congested time after BPR function

Right now this row is mainly **network geometry + metadata**, which is correct for ingestion/export.

---

## Small quality note

You’ve got some fields as strings that ideally should be typed:

- `lanes` should be numeric (int)
- `reversed` should be boolean
- `"nan"` should be actual nulls

It’s not “wrong” — it’s the tradeoff we made to get Parquet exports stable. If you want, we can keep the table cleaner by:

- preserving `u,v,key` as ints,
- converting `lanes` to int when possible,
- leaving missing values as `None` instead of `"nan"`.

---

## How to render this visually (quick idea)

In Streamlit you can parse `geometry_wkt` and plot it on a map:

- Folium: convert to coordinate pairs and add as a PolyLine
- Plotly: add as a line trace on OpenStreetMap tiles

If you tell me whether you’re using **Folium** or **Plotly**, I’ll give you a short snippet that takes rows like this and renders them (including coloring by `delay` once your flows are non-zero).

## License

MIT (adjust as needed).
