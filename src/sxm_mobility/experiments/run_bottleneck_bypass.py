from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd
from loguru import logger

from sxm_mobility.config import settings
from sxm_mobility.io.osm_ingest import load_gpickle
from sxm_mobility.demand.od_generation import load_od_parquet
from sxm_mobility.assignment.msa import msa_traffic_assignment
from sxm_mobility.assignment.metrics import total_delay, total_system_travel_time
from sxm_mobility.scenarios.catalog import propose_connector_near_edge, apply_connector
from sxm_mobility.experiments.run_manager import (
    base_dir,
    create_run_dir,
    write_manifest,
    RunManifest,
    list_runs,
    od_path,
    baseline_bottlenecks_path,
    bottleneck_bypass_experiment_path,
    bottleneck_bypass_edge_experiment_path,
)


def _node_xy(nodes: pd.DataFrame, node_id: int) -> tuple[float, float]:
    """
    Robustly fetch lon/lat for a node, regardless of whether osmid is int or str.
    Assumes nodes has columns: osmid, x (lon), y (lat).
    """
    df = nodes.copy()
    if "osmid" not in df.columns:
        raise KeyError("nodes.parquet must contain an 'osmid' column")
    if "x" not in df.columns or "y" not in df.columns:
        raise KeyError("nodes.parquet must contain 'x' (lon) and 'y' (lat) columns")

    row = df.loc[df["osmid"].astype(str) == str(node_id)]
    if row.empty:
        raise KeyError(f"Node {node_id} not found in nodes.parquet (osmid mismatch).")
    r = row.iloc[0]
    return float(r["x"]), float(r["y"])


def _connector_edges_row(
    nodes: pd.DataFrame,
    a: int,
    b: int,
    *,
    scenario_id: str,
    base_u: int,
    base_v: int,
    name: str,
    length_m: float,
    speed_kph: float,
    lanes: float,
    capacity: float,
    t0: float,
) -> dict:
    lon1, lat1 = _node_xy(nodes, a)
    lon2, lat2 = _node_xy(nodes, b)
    wkt = f"LINESTRING ({lon1} {lat1}, {lon2} {lat2})"

    return {
        "scenario_id": scenario_id,
        "baseline_bottleneck_u": base_u,
        "baseline_bottleneck_v": base_v,
        "u": a,
        "v": b,
        "key": 0,
        "name": name or "Proposed connector / bypass",
        "highway": "proposed_connector",
        "geometry_wkt": wkt,
        "length": float(length_m),
        "lanes": float(lanes),
        "maxspeed": float(speed_kph),
        "capacity": float(capacity),
        "t0": float(t0),
        "time": float(t0),
    }


def main() -> None:
    graph_path = base_dir() / "graph.gpickle"
    nodes_path = base_dir() / "nodes.parquet"

    if not graph_path.exists():
        raise FileNotFoundError(f"Missing base graph: {graph_path}. Run scripts/build_graph.py first.")
    if not nodes_path.exists():
        raise FileNotFoundError(f"Missing base nodes: {nodes_path}. Run scripts/build_graph.py first.")

    baseline_runs = list_runs("baseline")
    baseline_run = baseline_runs[0] if baseline_runs else None
    if baseline_run is None:
        raise FileNotFoundError("No baseline runs found. Run scripts/run_baseline.py first.")

    run_path = create_run_dir("bottleneck_bypass")
    logger.info("Solution experiment run folder: {}", run_path)

    G = load_gpickle(graph_path)
    nodes = pd.read_parquet(nodes_path)

    od = load_od_parquet(od_path(baseline_run))
    btn = pd.read_parquet(baseline_bottlenecks_path(baseline_run))

    logger.info("Loaded baseline OD pairs: {}", len(od))
    logger.info("Loaded baseline bottlenecks rows: {}", len(btn))

    # Normalize bottleneck ids
    for c in ["u", "v", "key"]:
        if c in btn.columns:
            btn[c] = pd.to_numeric(btn[c], errors="coerce").astype("Int64")

    # Take top N bottlenecks to generate multiple connector candidates
    TOP_N_BOTTLENECKS = 10
    btn = btn.sort_values(["delay", "v_c"], ascending=False).head(TOP_N_BOTTLENECKS)

    # Baseline assignment ONCE
    G0 = G.copy()
    G0 = msa_traffic_assignment(
        G0, od=od, iters=settings.msa_iters, alpha=settings.bpr_alpha, beta=settings.bpr_beta
    )
    base_tstt = total_system_travel_time(G0)
    base_delay = total_delay(G0)

    results_rows: list[dict] = []
    connector_rows: list[dict] = []
    seen_connectors: set[tuple[int, int]] = set()

    for i, r in enumerate(btn.itertuples(index=False), start=1):
        u = int(r.u)
        v = int(r.v)

        # Propose one connector for this bottleneck
        try:
            spec = propose_connector_near_edge(
                G,
                nodes_df=nodes,
                u=u,
                v=v,
                k_hops=3,
                max_straight_m=300.0,
            )
        except Exception as e:
            logger.warning("Could not propose connector for bottleneck {}->{}: {}", u, v, e)
            continue

        a, b = int(spec.a), int(spec.b)
        key = (a, b) if a <= b else (b, a)
        if key in seen_connectors:
            logger.info("Skipping duplicate connector {}->{} (already tested)", a, b)
            continue
        seen_connectors.add(key)

        speed_mps = float(spec.speed_kph) * 1000.0 / 3600.0
        t0 = float(spec.length_m) / max(1.0, speed_mps)
        capacity = 900.0 * float(spec.lanes)

        scenario_id = f"connector_{i:02d}_u{u}_v{v}_a{a}_b{b}"

        logger.info(
            "Bottleneck {}: u={} v={} | Proposed connector: {}->{} (~{:.1f}m)",
            i, u, v, a, b, float(spec.length_m)
        )

        # Apply + assign
        G1 = G.copy()
        apply_connector(G1, spec)
        G1 = msa_traffic_assignment(
            G1, od=od, iters=settings.msa_iters, alpha=settings.bpr_alpha, beta=settings.bpr_beta
        )

        scen_tstt = total_system_travel_time(G1)
        scen_delay = total_delay(G1)

        results_rows.append({
            "scenario_id": scenario_id,
            "scenario": "connector_bypass",
            "baseline_bottleneck_u": u,
            "baseline_bottleneck_v": v,
            "connector_a": a,
            "connector_b": b,
            "connector_length_m": float(spec.length_m),
            "connector_speed_kph": float(spec.speed_kph),
            "connector_lanes": float(spec.lanes),
            "baseline_tstt_veh_hours": float(base_tstt),
            "baseline_delay_veh_hours": float(base_delay),
            "scenario_tstt_veh_hours": float(scen_tstt),
            "scenario_delay_veh_hours": float(scen_delay),
            "delta_tstt_veh_hours": float(scen_tstt - base_tstt),
            "delta_delay_veh_hours": float(scen_delay - base_delay),
        })

        connector_rows.append(
            _connector_edges_row(
                nodes,
                a, b,
                scenario_id=scenario_id,
                base_u=u,
                base_v=v,
                name=getattr(spec, "name", "Proposed connector / bypass"),
                length_m=float(spec.length_m),
                speed_kph=float(spec.speed_kph),
                lanes=float(spec.lanes),
                capacity=float(capacity),
                t0=float(t0),
            )
        )

    results = pd.DataFrame(results_rows)
    connector_edges = pd.DataFrame(connector_rows)

    # Save (even if empty, so you can debug in Streamlit)
    connector_edges.to_parquet(bottleneck_bypass_edge_experiment_path(run_path), index=False)
    results.to_parquet(bottleneck_bypass_experiment_path(run_path), index=False)

    manifest = RunManifest(
        run_name=run_path.name,
        experiment="bottleneck_bypass",
        created_at=datetime.now().isoformat(timespec="seconds"),
        place_query=settings.place_query,
        network_type=settings.network_type,
        od_mode="from_baseline_run",
        total_demand_vph=float(sum(d for _, _, d in od)),
        n_pairs=len(od),
        msa_iters=settings.msa_iters,
        bpr_alpha=settings.bpr_alpha,
        bpr_beta=settings.bpr_beta,
        notes=f"Connector sweep over top {TOP_N_BOTTLENECKS} baseline bottlenecks; baseline run: {baseline_run.name}",
    )
    write_manifest(run_path, manifest)

    logger.info("Saved results rows: {}", len(results))
    logger.info("Saved connector edges rows: {}", len(connector_edges))


if __name__ == "__main__":
    main()
