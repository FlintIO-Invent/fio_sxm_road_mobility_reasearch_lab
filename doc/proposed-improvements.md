# Proposed Improvements

This document lists practical improvements based on the current repository behavior. The highest-priority items focus on correctness, reproducibility, and making the model credible enough for stakeholder use.

## Priority 0: Fix Correctness And Runtime Failure Modes

### 1. Make demand-reduction runs fail clearly when no baseline exists

Files:

- `src/sxm_mobility/experiments/run_demand_reduction.py`
- `scripts/pages/experiments/1_run_demand_reduction.py`

Current behavior:

- The runner sets `baseline_run = None` when no baseline exists, but still calls `od_path(baseline_run)`.
- The Streamlit page can reference `dr` even when no demand-reduction result was loaded.

Proposed change:

- Raise a clear `FileNotFoundError("No baseline runs found. Run scripts/run_baseline.py first.")`.
- Stop the Streamlit page before conclusion code if no result dataframe exists.
- Save the baseline run name in the demand-reduction output and manifest.

### 2. Catch no-path failures in all-or-nothing assignment

File:

- `src/sxm_mobility/assignment/msa.py`

Current behavior:

- OD pairs with endpoints missing from the graph are skipped.
- OD pairs whose endpoints exist but have no route can still raise from `nx.shortest_path`.

Proposed change:

- Catch `networkx.NetworkXNoPath` and `networkx.NodeNotFound` inside `all_or_nothing_assignment`.
- Track and return assignment diagnostics: routed pairs, skipped missing endpoints, skipped no-path pairs, and total routed demand.
- Write diagnostics into run manifests or separate run summary artifacts.

### 3. Use settings consistently

Files:

- `src/sxm_mobility/config.py`
- `src/sxm_mobility/experiments/run_baseline.py`
- `src/sxm_mobility/experiments/run_bottleneck_bypass.py`
- `src/sxm_mobility/experiments/run_scenarios.py`

Current behavior:

- `baseline_top_n_bottlenecks` exists but baseline uses hard-coded `n=50`.
- `max_to_test` exists but the bypass runner iterates every bottleneck row.
- `scenarios_json`, `scenarios_enabled`, and `scenarios_preset` are defined but not used by `run_scenarios.py`.

Proposed change:

- Replace hard-coded values with settings.
- Either implement `scenarios_json` parsing or remove the unused settings until needed.
- Include every active setting in `manifest.json`.

### 4. Normalize KPI and table schemas

Files:

- `src/sxm_mobility/assignment/metrics.py`
- `src/sxm_mobility/experiments/run_baseline.py`
- `scripts/pages/baseline/1_island_traffic_stress_test.py`
- `src/sxm_mobility/config.py`

Current behavior:

- Baseline bottleneck output uses `v_c`.
- The baseline page display column list looks for `"volume capacity ratio"`, so `v_c` may not appear in the user-facing table.
- Historical artifacts include extra columns not produced by current baseline code.

Proposed change:

- Define versioned artifact schemas for base, baseline, scenarios, demand reduction, and bypass outputs.
- Keep machine columns stable (`v_c`) and apply display renames only in the UI.
- Add schema tests that read generated Parquet from a temp run and assert required columns.

### 5. Make empty bypass outputs explicit

File:

- `src/sxm_mobility/experiments/run_bottleneck_bypass.py`

Current behavior:

- If no connectors are proposed, empty dataframes may be saved with weak or missing schema guarantees.

Proposed change:

- Always write result and connector Parquet files with the expected columns, even when empty.
- Add a manifest field for `tested_bottlenecks`, `proposed_connectors`, and failure reasons.
- Use `settings.max_to_test` to cap runtime.

## Priority 1: Improve Reproducibility

### 1. Make run manifests complete

File:

- `src/sxm_mobility/experiments/run_manager.py`

Add manifest fields:

- Git commit SHA, if available.
- Code/package version.
- Base graph artifact checksum or modified timestamp.
- Baseline run dependency name for downstream experiments.
- Demand seed.
- Reduction sweep values.
- Connector search parameters such as `k_hops`, `max_straight_m`, speed, lanes, and two-way behavior.
- Assignment diagnostics.

### 2. Add `.env.example` and real `.env` loading

File:

- `src/sxm_mobility/config.py`

Current behavior:

- The settings docstring mentions local `.env`, but `env_file` is not configured.

Proposed change:

- Add `env_file=".env"` to `SettingsConfigDict`.
- Add `.env.example` with common `SXM_` variables.
- Document which settings affect graph building versus experiment runs.

### 3. Store assigned edge metrics for every run

Files:

- `src/sxm_mobility/experiments/run_baseline.py`
- `src/sxm_mobility/experiments/run_scenarios.py`
- `src/sxm_mobility/experiments/run_demand_reduction.py`
- `src/sxm_mobility/experiments/run_bottleneck_bypass.py`

Current behavior:

- Baseline stores bottlenecks but not a full assigned edge table.
- Scenario runs mostly store system-level deltas.

Proposed change:

- Save `edge_metrics.parquet` with `u`, `v`, `key`, `flow`, `capacity`, `v_c`, `t0`, `time`, `delay`, and geometry join keys.
- For scenarios, optionally save only changed/top edges to manage file size.

### 4. Decide whether processed data belongs in Git

Files:

- `.gitignore`
- `data/processed/`

Current behavior:

- `data/processed` artifacts are tracked.
- Raw and interim data are ignored.

Proposed change:

- If processed artifacts are fixtures/demo data, document that contract and keep them small.
- If they are generated outputs, ignore them and provide commands to recreate them.
- Keep a tiny test fixture graph separate from full demo artifacts.

## Priority 2: Improve Model Credibility

### 1. Replace purely synthetic OD with zone-based demand

Files:

- `src/sxm_mobility/demand/od_generation.py`
- new `src/sxm_mobility/demand/zones.py`

Proposed change:

- Define named zones such as airport, Simpson Bay, Cole Bay, Philipsburg, schools, ports, and border/crossing areas.
- Assign graph nodes to zones using polygons or nearest-node lookup.
- Generate OD from zone-to-zone demand tables rather than only node weights.
- Allow CSV/Parquet input for stakeholder-provided OD matrices.

### 2. Calibrate speeds, capacities, and BPR parameters

Files:

- `src/sxm_mobility/network/attributes.py`
- `src/sxm_mobility/assignment/bpr.py`

Proposed change:

- Split capacity rules by road type, lanes, directionality, and urban context.
- Add calibration inputs from counts, observed speeds, GPS/probe data, or manual surveys.
- Support per-edge or per-road-class `alpha` and `beta`.
- Write an assumptions report listing every edge that used defaults.

### 3. Model intersection and turning delay

Current behavior:

- Delay is edge-based only.
- Signals, turn penalties, roundabouts, stop/yield behavior, and intersection priority are not represented.

Proposed change:

- Add node-level delay proxies.
- Add turn penalties for movements through important junctions.
- Add configurable signal scenarios for proposed traffic lights.
- Report node bottlenecks in addition to edge bottlenecks.

### 4. Validate against observed reality

Proposed change:

- Add validation notebooks or scripts comparing model outputs to observed traffic counts and travel times.
- Track error metrics by corridor.
- Flag scenarios as screening-level until validation is available.

## Priority 3: Improve Scenario Generation

### 1. Make generic scenarios meaningful

File:

- `src/sxm_mobility/experiments/run_scenarios.py`

Current behavior:

- Capacity scenarios use the first graph edges, not necessarily important edges.
- The prototype connector connects the first and last graph nodes.

Proposed change:

- Build `IncreaseCapacity` scenarios from top bottlenecks.
- Build `Closure` scenarios from high-delay or high-betweenness edges.
- Build connector scenarios from actual candidate generators.

### 2. Choose and expose connector algorithms

Files:

- `src/sxm_mobility/scenarios/catalog.py`
- `src/sxm_mobility/experiments/run_bottleneck_bypass.py`

Current behavior:

- `run_bottleneck_bypass.py` uses `propose_connector_near_edge`.
- `shortest_path_relief_connectors` exists but is not used by the current runner.

Proposed change:

- Support an algorithm setting such as `near_edge` versus `shortest_path_relief`.
- Persist heuristic scores and candidate rejection reasons.
- Generate multiple candidates per bottleneck, then test the top candidates subject to runtime limits.
- Add constraints such as maximum grade, land-use exclusions, protected areas, and right-of-way feasibility when data is available.

### 3. Add scenario config files

Proposed change:

- Store scenarios in YAML or JSON.
- Validate configs with Pydantic.
- Let Streamlit and future API endpoints trigger named scenario configs instead of only running hard-coded sweeps.

## Priority 4: Improve Performance

### 1. Add convergence tracking and early stopping

File:

- `src/sxm_mobility/assignment/msa.py`

Current behavior:

- MSA always runs the configured number of iterations.

Proposed change:

- Compute relative gap or flow-change metrics per iteration.
- Stop early when convergence stabilizes.
- Save convergence history per run.

### 2. Reduce repeated shortest-path cost

File:

- `src/sxm_mobility/assignment/msa.py`

Current behavior:

- Each iteration computes shortest paths for every OD pair.

Proposed change:

- Profile assignment runtime.
- Cache repeated OD paths within an iteration where possible.
- Consider parallel OD routing for larger OD sets.
- Evaluate faster graph libraries only if NetworkX becomes a bottleneck.

### 3. Avoid unnecessary repeated baseline assignment

Files:

- `src/sxm_mobility/experiments/run_demand_reduction.py`
- `src/sxm_mobility/experiments/run_bottleneck_bypass.py`

Current behavior:

- Downstream experiments recompute baseline assignment instead of loading a saved assigned baseline graph or edge metrics.

Proposed change:

- Save baseline edge metrics and optionally an assigned graph artifact.
- Reuse baseline scores directly when the baseline dependency and settings match.

## Priority 5: Improve Dashboard UX And Reliability

### 1. Add run selectors to experiment pages

Files:

- `scripts/pages/experiments/1_run_demand_reduction.py`
- `scripts/pages/experiments/2_run_bottleneck_bypass.py`

Current behavior:

- Experiment pages automatically select the latest run.

Proposed change:

- Add sidebar selectors for demand-reduction and bypass runs.
- Show manifest details for the selected run.
- Warn when a selected experiment depends on a different baseline than the selected baseline page.

### 2. Improve map overlays and hover text

File:

- `scripts/apps/components.py`

Current behavior:

- Bottleneck hover information is assembled but skipped for the concatenated trace.
- Connector hover text can be difficult to align with individual segments when multiple lines are concatenated.

Proposed change:

- Render one trace per selected bottleneck/connector when hover precision matters.
- Add map coloring by `delay`, `v_c`, or `flow`.
- Add a table-to-map selection workflow.

### 3. Clean stakeholder copy and labels

Files:

- `scripts/pages/home/*.py`
- `scripts/pages/baseline/*.py`
- `scripts/pages/experiments/*.py`

Proposed change:

- Fix typos and informal placeholders.
- Align terminology: Sint Maarten, St. Maarten, SXM, demand reduction, vehicle reduction, bypass, connector.
- Avoid presenting unvalidated model results as forecasts.

## Priority 6: Grow API And Job Architecture Deliberately

Files:

- `src/sxm_mobility/api/app.py`
- `pyproject.toml`

Current behavior:

- FastAPI exposes only `/health`.
- `jobs` and `db` extras exist for future Celery/Redis and Postgres work.

Proposed change:

- Add read-only artifact endpoints first:
  - list runs
  - get manifest
  - get KPI table
  - get bottlenecks
  - get scenario results
- Add job-trigger endpoints only after run reproducibility and artifact schemas are stable.
- If background jobs are added, create a run registry with statuses: queued, running, succeeded, failed.

## Priority 7: Expand Tests

Add tests for:

- `all_or_nothing_assignment` with no route.
- Parallel edge selection by lowest `time`.
- Demand generation reproducibility by seed.
- Baseline runner output schemas using a temp `SXM_DATA_DIR`.
- Demand-reduction runner with and without baseline artifacts.
- Bypass runner empty-candidate behavior.
- Streamlit data helper functions where possible without launching the UI.
- Manifest fields and artifact path helpers.

Also add a tiny fixture graph and fixture OD table for integration tests so tests do not depend on checked-in full processed data.

## Suggested Implementation Order

1. Fix runner/UI crash cases and route exception handling.
2. Define artifact schemas and add schema tests.
3. Make settings and manifests complete.
4. Save full baseline edge metrics.
5. Replace generic scenario selection with bottleneck-driven candidates.
6. Add run selectors and better empty-state handling in Streamlit.
7. Start OD calibration and zone-based demand.
8. Add convergence diagnostics and performance profiling.
9. Expand API only after the artifact contract stabilizes.
