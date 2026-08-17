# How SXM Mobility Graph Lab Works

All paths in this document are relative to `mobility_graph_lab/`.

## Purpose

SXM Mobility Graph Lab models Sint Maarten's road network as a directed NetworkX multigraph, generates synthetic origin-destination demand, assigns that demand to shortest paths under congestion, ranks bottlenecks, and evaluates intervention experiments such as demand reduction and proposed bypass connectors.

The repository is split into three practical layers:

- `src/sxm_mobility/`: reusable engine code.
- `scripts/`: runnable command-line and Streamlit entry points.
- `data/processed/`: saved graph and run artifacts consumed by later steps and dashboards.

## Runtime And Dependencies

The project is a Python `>=3.12` `uv` project declared in `pyproject.toml`.

Core dependencies include:

- `networkx`, `numpy`, `pandas`, `pydantic`, `pydantic-settings`, `loguru`, `duckdb`, `pyarrow`, `streamlit`, `plotly`, and `shapely`.
- Optional `geo` extras for OSMnx/geospatial graph building.
- Optional `dashboard`, `api`, `jobs`, `db`, and `dev` extras for Streamlit, FastAPI, future background jobs, future database work, and development tooling.

Typical setup:

```bash
uv sync --extra geo --extra io --extra viz --extra dashboard --extra api --extra dev
```

Useful commands:

```bash
uv run python scripts/build_graph.py
uv run python scripts/run_baseline.py
uv run python scripts/run_scenarios.py
uv run python scripts/run_demand_reduction.py
uv run python scripts/run_bottleneck_bypass.py
uv run streamlit run scripts/streamlit_app.py
uv run uvicorn sxm_mobility.api.app:app --reload
uv run --extra dev pytest
```

## Configuration

Configuration lives in `src/sxm_mobility/config.py`.

The global `settings` object is a Pydantic `BaseSettings` model with the prefix `SXM_`. Examples:

- `SXM_PLACE_QUERY`
- `SXM_NETWORK_TYPE`
- `SXM_OD_N_PAIRS`
- `SXM_OD_TOTAL_DEMAND_VPH`
- `SXM_MSA_ITERS`
- `SXM_BPR_ALPHA`
- `SXM_BPR_BETA`

Default values currently include:

- `place_query = "Sint Maarten"`
- `network_type = "drive"`
- `od_n_pairs = 250`
- `od_total_demand_vph = 25000.0`
- `od_seed = 42`
- `msa_iters = 30`
- `bpr_alpha = 0.15`
- `bpr_beta = 4.0`

The settings docstring mentions local `.env` support, but `SettingsConfigDict` does not currently declare an `env_file`, so the current code is configured through real environment variables unless the app is changed.

`config.py` also stores display-name mappings and help text used by the Streamlit pages.

## Data Layout

Processed data is written below:

```text
data/processed/
  base/
    graph.gpickle
    graph.graphml
    nodes.parquet
    edges.parquet
  runs/
    baseline__YYYYMMDD_HHMM/
    scenarios__YYYYMMDD_HHMM/
    demand_reduction__YYYYMMDD_HHMM/
    bottleneck_bypass__YYYYMMDD_HHMM/
```

The current checked-in base artifacts contain:

- `nodes.parquet`: 1,965 nodes.
- `edges.parquet`: 4,423 directed road edges.
- `graph.gpickle`: canonical Python engine artifact.
- `graph.graphml`: shareable graph artifact.

Run folders are created by `src/sxm_mobility/experiments/run_manager.py`. Each run folder gets a `manifest.json` with the run name, experiment type, creation time, place, network type, OD mode, demand, pair count, MSA iterations, and BPR parameters.

## Package Map

`src/sxm_mobility/network/`

- `build_graph.py`: builds the OSMnx road network and enriches edges.
- `attributes.py`: adds assignment attributes such as `t0`, `capacity`, `flow`, and `time`.
- `simplify.py`: contains a largest weakly connected component helper.

`src/sxm_mobility/io/`

- `osm_ingest.py`: saves/loads graphs and exports nodes/edges to Parquet.

`src/sxm_mobility/demand/`

- `od_generation.py`: creates synthetic OD demand, scales demand, and saves/loads OD Parquet.

`src/sxm_mobility/assignment/`

- `bpr.py`: implements the Bureau of Public Roads travel-time function.
- `msa.py`: implements traffic assignment with Method of Successive Averages.
- `metrics.py`: computes system travel time, delay, and bottleneck rankings.

`src/sxm_mobility/scenarios/`

- `catalog.py`: scenario dataclasses and connector candidate helpers.
- `runner.py`: applies a scenario, reruns assignment, and scores the result.
- `evaluator.py`: wraps system KPI scoring.

`src/sxm_mobility/experiments/`

- `run_baseline.py`: baseline assignment and bottleneck run.
- `run_scenarios.py`: generic toy scenario comparisons.
- `run_demand_reduction.py`: demand reduction sweep.
- `run_bottleneck_bypass.py`: bypass connector proposal and evaluation sweep.
- `run_manager.py`: run directory and artifact path helpers.

`scripts/`

- `build_graph.py`: graph build entry point.
- `run_*.py`: thin wrappers around experiment modules.
- `streamlit_app.py`: multipage Streamlit router.
- `pages/`: Streamlit page implementations.

`src/sxm_mobility/api/app.py`

- Minimal FastAPI app exposing only `GET /health`.

## Step 1: Build The Base Graph

Command:

```bash
uv run python scripts/build_graph.py
```

Call path:

```text
scripts/build_graph.py
  -> sxm_mobility.network.build_graph.build_graph(...)
  -> sxm_mobility.network.attributes.add_freeflow_time_and_capacity(...)
  -> sxm_mobility.io.osm_ingest.save_gpickle(...)
  -> sxm_mobility.io.osm_ingest.save_graphml(...)
  -> sxm_mobility.io.osm_ingest.export_nodes_edges_parquet(...)
```

What happens:

1. `settings.place_query` and `settings.network_type` select the OSMnx place and network mode.
2. OSMnx downloads a simplified graph with `ox.graph_from_place(..., simplify=True)`.
3. OSMnx adds edge speeds and travel times.
4. `add_freeflow_time_and_capacity` initializes assignment fields on every edge:
   - `t0`: free-flow edge travel time in seconds.
   - `capacity`: estimated vehicles per hour.
   - `flow`: initialized to `0.0`.
   - `time`: initialized to `t0`.
5. The code tries to keep OSMnx's largest strongly connected component.
6. The graph and table artifacts are written to `data/processed/base/`.

Capacity is estimated from OSM road class and lanes. Per-lane defaults are hard-coded in `attributes.py`, for example:

- `primary`: 1,400 vehicles/hour/lane.
- `secondary`: 1,100 vehicles/hour/lane.
- `tertiary`: 900 vehicles/hour/lane.
- `residential`: 600 vehicles/hour/lane.
- `service`: 400 vehicles/hour/lane.

If lanes are missing, the code assumes at least one lane. If speed or travel time is missing, it falls back to a default speed of 40 kph.

Base artifact notes:

- `graph.gpickle` is the full-fidelity engine graph used by experiments.
- `graph.graphml` is sanitized for tools that understand GraphML.
- `nodes.parquet` and `edges.parquet` are dashboard/database-friendly exports.
- Geometry is stored as WKT text in `geometry_wkt`.

## Step 2: Generate Baseline Traffic

Command:

```bash
uv run python scripts/run_baseline.py
```

Call path:

```text
scripts/run_baseline.py
  -> sxm_mobility.experiments.run_baseline.main()
  -> load base graph.gpickle
  -> generate_od_weighted_total(...)
  -> msa_traffic_assignment(...)
  -> top_bottlenecks(...)
  -> total_system_travel_time(...), total_delay(...)
  -> write Parquet outputs and manifest
```

What happens:

1. The runner loads `data/processed/base/graph.gpickle`.
2. It creates a new folder such as `data/processed/runs/baseline__20260215_0153/`.
3. It generates synthetic OD demand using `generate_od_weighted_total`.
4. It saves OD demand to `od.parquet`.
5. It runs MSA traffic assignment on the graph.
6. It ranks the top 50 bottleneck edges.
7. It writes KPI, bottleneck, OD, and manifest artifacts.

Baseline outputs:

```text
data/processed/runs/baseline__.../
  od.parquet
  results_baseline.parquet
  baseline_bottlenecks.parquet
  manifest.json
```

`od.parquet` columns:

- `origin`
- `destination`
- `demand`

`results_baseline.parquet` current code columns:

- `place_query`
- `network_type`
- `total_demand_vph`
- `msa_iters`
- `bpr_alpha`
- `bpr_beta`
- `od_pairs`
- `nodes`
- `edges`
- `tstt`
- `delay`
- `avg_travel_time_min`
- `avg_delay_min`

Some checked-in historical artifacts also contain legacy duplicate columns such as `tstt_vh_per_h` and `delay_vh_per_h`.

`baseline_bottlenecks.parquet` columns:

- `u`
- `v`
- `key`
- `flow`
- `capacity`
- `v_c`
- `delay`

## Step 3: OD Demand Generation

Demand generation lives in `src/sxm_mobility/demand/od_generation.py`.

The main generator is `generate_od_weighted_total`.

It works as follows:

1. Build a node list from the graph.
2. Compute a node weight for each node with `node_weights_from_graph`.
3. Node weights are based on the road classes of incoming and outgoing edges.
4. Randomly sample origin and destination nodes, with higher probability near more important roads.
5. Ensure origin and destination are different.
6. Generate random positive raw demand for each pair.
7. Rescale all raw demands so their total equals `settings.od_total_demand_vph`.

This means the model currently uses synthetic demand. It is reproducible for a fixed graph, seed, pair count, and total demand.

`scale_od` is used by the demand-reduction experiment to multiply each OD demand by a factor.

## Step 4: Traffic Assignment

Traffic assignment lives in `src/sxm_mobility/assignment/msa.py`.

The model uses:

- BPR edge travel time.
- All-or-nothing shortest-path routing.
- Method of Successive Averages flow updates.

The BPR function is in `assignment/bpr.py`:

```text
time = t0 * (1 + alpha * (flow / capacity) ** beta)
```

If capacity is less than or equal to zero, the function returns `t0`.

The MSA loop in `msa_traffic_assignment` works as follows:

1. Count OD pairs whose endpoints are present in the graph and log assigned versus failed endpoints.
2. Initialize every edge:
   - `flow = existing flow or 0.0`
   - `time = t0` if available.
3. For each iteration `k`:
   - Recompute every edge's `time` using BPR and current `flow`.
   - Run all-or-nothing assignment for every OD pair:
     - Find the shortest path by edge `time`.
     - For each consecutive node pair on the path, choose the parallel edge key with the minimum `time`.
     - Add the OD demand to that edge's auxiliary flow.
   - Blend auxiliary flow into current flow using:
     - `step = 1 / (k + 1)`
     - `flow = flow + step * (aux_flow - flow)`
4. Recompute edge times once more and return the mutated graph.

Important units:

- `t0` and `time` are seconds.
- `flow` is vehicles/hour.
- `flow * time / 3600` is vehicle-hours per hour.
- `delay = flow * (time - t0) / 3600`.
- Average minutes per vehicle is `(vehicle_hours / total_demand_vph) * 60`.

## Step 5: Metrics

Metrics live in `src/sxm_mobility/assignment/metrics.py`.

`total_system_travel_time(G)` sums `flow * time / 3600` across edges.

`total_delay(G)` sums `flow * (time - t0) / 3600` across edges.

`top_bottlenecks(G, n)` returns edge rows sorted descending by:

1. delay
2. volume/capacity ratio (`v_c`)

Each bottleneck row contains `u`, `v`, `key`, `flow`, `capacity`, `v_c`, and `delay`.

## Step 6: Generic Scenario Runs

Command:

```bash
uv run python scripts/run_scenarios.py
```

Call path:

```text
scripts/run_scenarios.py
  -> sxm_mobility.experiments.run_scenarios.main()
  -> load graph
  -> load latest baseline OD and KPI when available
  -> build scenario objects
  -> run_scenario(...) for each scenario
  -> write results_scenarios.parquet, scenario_details.parquet, manifest.json
```

Current scenario types are defined in `src/sxm_mobility/scenarios/catalog.py`:

- `IncreaseCapacity`: copies the graph and multiplies one edge's capacity by `1 + pct`.
- `Closure`: copies the graph and removes one edge.
- `AddConnector`: copies the graph and adds one directed edge with length, free-flow time, capacity, and `scenario_edge=True`.

Current generic scenario selection is simple:

- Increase capacity on the first `settings.scenarios_cap_top_k` edges in the base graph.
- Optionally close the first edge in the base graph.
- Optionally add a connector from the first node to the last node.

This runner does not currently use `settings.scenarios_json`, `settings.scenarios_enabled`, or `settings.scenarios_preset`.

Scenario outputs:

```text
data/processed/runs/scenarios__.../
  od.parquet
  results_scenarios.parquet
  scenario_details.parquet
  manifest.json
```

`results_scenarios.parquet` columns include:

- `scenario_name`
- `scenario_type`
- `tstt`
- `delay`
- `baseline_tstt`
- `baseline_delay`
- `delta_tstt`
- `delta_delay`
- `delay_improvement`
- `delay_improvement_pct`
- `od_pairs`
- `msa_iters`
- `bpr_alpha`
- `bpr_beta`

`scenario_details.parquet` stores each scenario name, type, description, and JSON-encoded parameters.

## Step 7: Demand Reduction Experiment

Command:

```bash
uv run python scripts/run_demand_reduction.py
```

Call path:

```text
scripts/run_demand_reduction.py
  -> sxm_mobility.experiments.run_demand_reduction.main()
  -> load graph
  -> load latest baseline OD
  -> compute baseline assignment
  -> scale OD demand for each reduction level
  -> rerun assignment for each reduced-demand case
  -> write results_solution_experiment_path.parquet and manifest.json
```

Current reduction levels:

```text
5%, 10%, 15%, 20%, 25%, 30%, 40%, 50%
```

For each reduction `r`, the code calculates:

```text
factor = settings.od_factor - r
```

With the default `od_factor = 1.0`, that means demand factors from `0.95` down to `0.50`.

Output:

```text
data/processed/runs/demand_reduction__.../
  results_solution_experiment_path.parquet
  manifest.json
```

Result columns:

- `reduction_pct`
- `factor`
- `total_demand_vph`
- `tstt_veh_hours`
- `delay_veh_hours`
- `avg_travel_time_min`
- `avg_delay_min`
- `delta_delay_veh_hours`
- `delta_avg_delay_min`

This runner assumes a baseline run exists. If no baseline run exists, current code will fail when trying to load `od_path(baseline_run)`.

## Step 8: Bottleneck Bypass Experiment

Command:

```bash
uv run python scripts/run_bottleneck_bypass.py
```

Call path:

```text
scripts/run_bottleneck_bypass.py
  -> sxm_mobility.experiments.run_bottleneck_bypass.main()
  -> load base graph, nodes, edges
  -> load latest baseline OD and bottlenecks
  -> recompute baseline assignment once
  -> propose one connector per bottleneck row
  -> apply connector and rerun assignment
  -> compare against baseline
  -> write result and connector geometry tables
```

Inputs:

- `data/processed/base/graph.gpickle`
- `data/processed/base/nodes.parquet`
- `data/processed/base/edges.parquet`
- latest `baseline__.../od.parquet`
- latest `baseline__.../baseline_bottlenecks.parquet`

For each baseline bottleneck row:

1. Resolve the bottleneck edge and road label.
2. Use `propose_connector_near_edge` to find a nearby candidate connector.
3. Create a `ConnectorSpec`.
4. Add the connector to a graph copy with `apply_connector`.
5. `apply_connector` adds the edge in both directions by default unless the connector is one-way.
6. Run MSA assignment on the modified graph.
7. Compare scenario delay and travel time against the baseline assignment.
8. Save a result row and a connector geometry row.

The current bypass runner calls `propose_connector_near_edge`, not the newer `shortest_path_relief_connectors` helper also present in `catalog.py`.

Output:

```text
data/processed/runs/bottleneck_bypass__.../
  bottleneck_bypass_experiment_path.parquet
  bottleneck_bypass_edge_experiment_path.parquet
  manifest.json
```

`bottleneck_bypass_experiment_path.parquet` columns include:

- `scenario_id`
- `status`
- `baseline_edge_name`
- `baseline_bottleneck_u`
- `baseline_bottleneck_v`
- `connector_a`
- `connector_b`
- `connector_name`
- `connector_length_m`
- `connector_speed_kph`
- `connector_lanes`
- `baseline_tstt_veh_hours`
- `baseline_delay_veh_hours`
- `scenario_tstt_veh_hours`
- `scenario_delay_veh_hours`
- `delta_tstt_veh_hours`
- `delta_delay_veh_hours`
- `improve_delay_veh_hours`
- `improve_delay_pct`

`bottleneck_bypass_edge_experiment_path.parquet` columns include:

- `scenario_id`
- `baseline_bottleneck_u`
- `baseline_bottleneck_v`
- `u`
- `v`
- `key`
- `name`
- `connector_name`
- `baseline_edge_name`
- `highway`
- `geometry_wkt`
- `length`
- `lanes`
- `maxspeed`
- `capacity`
- `t0`
- `time`
- `status`
- `improve_delay_veh_hours`
- `improve_delay_pct`

## Step 9: Streamlit Dashboard

Command:

```bash
uv run streamlit run scripts/streamlit_app.py
```

The Streamlit app is a multipage app defined in `scripts/streamlit_app.py`.

Pages:

- `scripts/pages/home/1_overview.py`
- `scripts/pages/home/2_design.py`
- `scripts/pages/baseline/1_island_traffic_stress_test.py`
- `scripts/pages/experiments/1_run_demand_reduction.py`
- `scripts/pages/experiments/2_run_bottleneck_bypass.py`

Shared map/table helpers live in `scripts/apps/components.py`.

The dashboard reads saved Parquet artifacts. It does not rerun graph building or MSA assignment inside the UI.

Baseline page:

- Requires `data/processed/base/edges.parquet` and `nodes.parquet`.
- Requires at least one `baseline__...` run.
- Lets the user pick a baseline run.
- Loads KPI and bottleneck tables.
- Builds readable road/junction labels.
- Renders a Plotly OpenStreetMap road network and optional bottleneck overlay.

Demand reduction page:

- Selects the latest `demand_reduction__...` run.
- Displays the demand reduction sweep table.
- Computes narrative summary metrics from that latest run.

Bottleneck bypass page:

- Selects the latest `bottleneck_bypass__...` run.
- Loads result rows and connector geometry rows.
- Displays best-case impact metrics and the full result table.
- Lets the user choose a connector to overlay on the map.

Map rendering:

- `geometry_wkt` is parsed with Shapely.
- Base network and overlays are rendered with Plotly `Scattermapbox`.
- The map uses OpenStreetMap tiles.

## Step 10: API

Command:

```bash
uv run uvicorn sxm_mobility.api.app:app --reload
```

The API is currently only a scaffold:

- `GET /health` returns `{"status": "ok"}`.

There are no scenario, run, artifact, or dashboard API endpoints yet.

## Tests

Tests live in `tests/`.

Current coverage includes:

- `test_bpr.py`: BPR travel time increases monotonically with flow.
- `test_metrics.py`: delay is non-negative for simple inputs.
- `test_demand_reduction.py`: OD scaling preserves pairs and total demand math.
- `test_pipeline_sanity.py`: toy graph attribute initialization, OD total demand, and MSA assignment smoke test.

Run:

```bash
uv run --extra dev pytest
```

## Current Important Caveats

- Demand is synthetic, not calibrated to observed counts or surveys.
- Capacity and free-flow time are proxies based on OSM attributes and defaults.
- Intersection delay, signals, turns, and priority rules are not modeled.
- `run_scenarios.py` uses the first graph edges/nodes for generic scenarios, not the highest-impact bottlenecks.
- `run_demand_reduction.py` requires a baseline run but does not explicitly guard against no baseline existing.
- `all_or_nothing_assignment` skips missing OD endpoints but does not catch all no-path routing failures.
- Some configured settings are declared but not currently used by runners.
- The API and future jobs/database dependencies are scaffolds, not implemented platform features.
