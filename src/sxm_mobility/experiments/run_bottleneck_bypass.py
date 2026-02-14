from __future__ import annotations

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


def _clean_osm_text(x) -> str | None:
    """Turn OSMnx mixed values into readable text."""
    if x is None:
        return None
    if isinstance(x, list) and x:
        x = x[0]
    s = str(x).strip()
    if s.lower() in {"nan", "none", ""}:
        return None
    return s


def _build_node_lookup(nodes: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """Map osmid(str) -> (lon, lat)."""
    if "osmid" not in nodes.columns:
        raise KeyError("nodes.parquet must contain an 'osmid' column")
    if "x" not in nodes.columns or "y" not in nodes.columns:
        raise KeyError("nodes.parquet must contain 'x' (lon) and 'y' (lat) columns")

    out: dict[str, tuple[float, float]] = {}
    for r in nodes.itertuples(index=False):
        k = str(getattr(r, "osmid"))
        out[k] = (float(getattr(r, "x")), float(getattr(r, "y")))
    return out


def _connector_edges_row(
    node_lookup: dict[str, tuple[float, float]],
    a: int,
    b: int,
    *,
    scenario_id: str,
    base_u: int,
    base_v: int,
    bottleneck_road: str,
    length_m: float,
    speed_kph: float,
    lanes: float,
    capacity: float,
    t0: float,
    status: str,
    improve_delay_veh_hours: float,
    improve_delay_pct: float | None,
) -> dict:
    lon1, lat1 = node_lookup[str(a)]
    lon2, lat2 = node_lookup[str(b)]
    wkt = f"LINESTRING ({lon1} {lat1}, {lon2} {lat2})"

    pct_txt = "n/a" if improve_delay_pct is None else f"{improve_delay_pct:.1f}%"
    label = (
        f"{status} delay ({pct_txt}) | "
        f"Bypass near: {bottleneck_road} | "
        f"Connector: {a} ↔ {b} (~{length_m:.0f} m)"
    )

    return {
        "scenario_id": scenario_id,
        "baseline_bottleneck_u": base_u,
        "baseline_bottleneck_v": base_v,
        "u": a,
        "v": b,
        "key": 0,
        "name": f"Bypass near {bottleneck_road}",
        "label": label,  # ✅ use this in Streamlit hover
        "highway": "proposed_connector",
        "geometry_wkt": wkt,
        "length": float(length_m),
        "lanes": float(lanes),
        "maxspeed": float(speed_kph),
        "capacity": float(capacity),
        "t0": float(t0),
        "time": float(t0),
        "status": status,
        "improve_delay_veh_hours": float(improve_delay_veh_hours),
        "improve_delay_pct": None if improve_delay_pct is None else float(improve_delay_pct),
    }


def main() -> None:
    graph_path = base_dir() / "graph.gpickle"
    nodes_path = base_dir() / "nodes.parquet"
    edges_path = base_dir() / "edges.parquet"

    if not graph_path.exists():
        raise FileNotFoundError(f"Missing base graph: {graph_path}. Run scripts/build_graph.py first.")
    if not nodes_path.exists():
        raise FileNotFoundError(f"Missing base nodes: {nodes_path}. Run scripts/build_graph.py first.")
    if not edges_path.exists():
        raise FileNotFoundError(f"Missing base edges: {edges_path}. Run scripts/build_graph.py first.")

    baseline_runs = list_runs("baseline")
    baseline_run = baseline_runs[0] if baseline_runs else None
    if baseline_run is None:
        raise FileNotFoundError("No baseline runs found. Run scripts/run_baseline.py first.")

    run_path = create_run_dir("bottleneck_bypass")
    logger.info("Solution experiment run folder: {}", run_path)

    G = load_gpickle(graph_path)
    nodes = pd.read_parquet(nodes_path)
    node_lookup = _build_node_lookup(nodes)

    edges = pd.read_parquet(edges_path)  # ✅ FIX: load it
    od = load_od_parquet(od_path(baseline_run))
    btn = pd.read_parquet(baseline_bottlenecks_path(baseline_run))

    logger.info("Loaded baseline OD pairs: {}", len(od))
    logger.info("Loaded baseline bottlenecks rows: {}", len(btn))

    # Normalize join keys
    for df in (edges, btn):
        for c in ["u", "v", "key"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")

    # ✅ Merge bottlenecks with edge names/highway from edges.parquet
    btn_named = btn.merge(
        edges[["u", "v", "key", "name", "highway"]],
        on=["u", "v", "key"],
        how="left",
        suffixes=("", "_edge"),
    )

    TOP_N_BOTTLENECKS = 10
    btn_top = btn_named.sort_values(["delay", "v_c"], ascending=False).head(TOP_N_BOTTLENECKS)

    # Baseline assignment ONCE
    G0 = G.copy()
    G0 = msa_traffic_assignment(G0, od=od, iters=settings.msa_iters, alpha=settings.bpr_alpha, beta=settings.bpr_beta)
    base_tstt = float(total_system_travel_time(G0))
    base_delay = float(total_delay(G0))

    results_rows: list[dict] = []
    connector_rows: list[dict] = []
    seen_connectors: set[tuple[int, int]] = set()

    for i, r in enumerate(btn_top.itertuples(index=False), start=1):
        if pd.isna(r.u) or pd.isna(r.v):
            logger.warning("Skipping bottleneck with missing u/v: {}", r)
            continue

        u = int(r.u)
        v = int(r.v)

        # Build readable bottleneck road label
        road_name = _clean_osm_text(getattr(r, "name", None))
        highway = _clean_osm_text(getattr(r, "highway", None))
        bottleneck_road = road_name or highway or "Unnamed corridor"

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

        if str(a) not in node_lookup or str(b) not in node_lookup:
            logger.warning("Skipping connector {}->{} (missing node coordinates)", a, b)
            continue

        # Skip duplicates (unordered)
        undirected_key = (a, b) if a <= b else (b, a)
        if undirected_key in seen_connectors:
            logger.info("Skipping duplicate connector {}<->{} (already tested)", a, b)
            continue
        seen_connectors.add(undirected_key)

        speed_mps = float(spec.speed_kph) * 1000.0 / 3600.0
        t0 = float(spec.length_m) / max(1.0, speed_mps)
        capacity = 900.0 * float(spec.lanes)

        scenario_id = f"connector_{i:02d}_u{u}_v{v}_a{a}_b{b}"

        logger.info(
            "Bottleneck {}: {} | Proposed connector: {}<->{} (~{:.1f}m)",
            i, bottleneck_road, a, b, float(spec.length_m),
        )

        # Apply + assign
        G1 = G.copy()
        apply_connector(G1, spec)
        G1 = msa_traffic_assignment(G1, od=od, iters=settings.msa_iters, alpha=settings.bpr_alpha, beta=settings.bpr_beta)

        scen_tstt = float(total_system_travel_time(G1))
        scen_delay = float(total_delay(G1))

        improve_delay_veh_hours = base_delay - scen_delay  # positive = good
        improve_delay_pct = (improve_delay_veh_hours / base_delay * 100.0) if base_delay > 0 else None
        status = "Improves" if improve_delay_veh_hours > 0 else "Worsens"

        results_rows.append({
            "scenario_id": scenario_id,
            "scenario": "connector_bypass",
            "status": status,
            "bottleneck_road": bottleneck_road,
            "baseline_bottleneck_u": u,
            "baseline_bottleneck_v": v,
            "connector_a": a,
            "connector_b": b,
            "connector_length_m": float(spec.length_m),
            "connector_speed_kph": float(spec.speed_kph),
            "connector_lanes": float(spec.lanes),
            "baseline_tstt_veh_hours": base_tstt,
            "baseline_delay_veh_hours": base_delay,
            "scenario_tstt_veh_hours": scen_tstt,
            "scenario_delay_veh_hours": scen_delay,
            "delta_tstt_veh_hours": scen_tstt - base_tstt,
            "delta_delay_veh_hours": scen_delay - base_delay,
            "improve_delay_veh_hours": improve_delay_veh_hours,
            "improve_delay_pct": improve_delay_pct,
        })

        connector_rows.append(
            _connector_edges_row(
                node_lookup,
                a, b,
                scenario_id=scenario_id,
                base_u=u,
                base_v=v,
                bottleneck_road=bottleneck_road,
                length_m=float(spec.length_m),
                speed_kph=float(spec.speed_kph),
                lanes=float(spec.lanes),
                capacity=float(capacity),
                t0=float(t0),
                status=status,
                improve_delay_veh_hours=improve_delay_veh_hours,
                improve_delay_pct=improve_delay_pct,
            )
        )

    results = pd.DataFrame(results_rows)
    connector_edges = pd.DataFrame(connector_rows)

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
