from __future__ import annotations

from datetime import datetime
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


def _build_node_lookup(nodes: pd.DataFrame) -> dict[str, tuple[float, float]]:
    required = {"osmid", "x", "y"}
    missing = required - set(nodes.columns)
    if missing:
        raise KeyError(f"nodes.parquet missing columns: {sorted(missing)}")

    out: dict[str, tuple[float, float]] = {}
    for r in nodes.itertuples(index=False):
        out[str(getattr(r, "osmid"))] = (float(getattr(r, "x")), float(getattr(r, "y")))
    return out


def _edge_label(edges_df: pd.DataFrame, u: int, v: int, key: int) -> str:
    if edges_df.empty:
        return f"Edge {u}->{v}"

    hit = edges_df.loc[(edges_df["u"] == u) & (edges_df["v"] == v) & (edges_df["key"] == key)]
    if hit.empty:
        return f"Edge {u}->{v}"

    r = hit.iloc[0]
    name = r.get("name", None)
    highway = r.get("highway", None)

    def _to_str(x) -> str | None:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return None
        if isinstance(x, list):
            return ", ".join(map(str, x))
        return str(x)

    name_s = _to_str(name)
    highway_s = _to_str(highway)

    if name_s and name_s.lower() != "nan":
        return name_s
    if highway_s and highway_s.lower() != "nan":
        return highway_s
    return f"Edge {u}->{v}"


def _connector_edges_row(
    node_lookup: dict[str, tuple[float, float]],
    a: int,
    b: int,
    *,
    scenario_id: str,
    base_u: int,
    base_v: int,
    connector_name: str,
    baseline_edge_name: str,
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

    return {
        "scenario_id": scenario_id,
        "baseline_bottleneck_u": base_u,
        "baseline_bottleneck_v": base_v,
        "u": a,
        "v": b,
        "key": 0,
        "name": connector_name,                 # <-- used on map hover
        "connector_name": connector_name,       # <-- used in table/choices
        "baseline_edge_name": baseline_edge_name,
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
    logger.info("Bottleneck bypass sweep run folder: {}", run_path)

    G = load_gpickle(graph_path)
    nodes = pd.read_parquet(nodes_path)
    edges_df = pd.read_parquet(edges_path)

    node_lookup = _build_node_lookup(nodes)

    od = load_od_parquet(od_path(baseline_run))
    btn = pd.read_parquet(baseline_bottlenecks_path(baseline_run))

    # normalize types for joins/labels
    for df in (btn, edges_df):
        for c in ["u", "v", "key"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")

    # sort worst first
    sort_cols = [c for c in ["delay", "v_c"] if c in btn.columns]
    if sort_cols:
        btn = btn.sort_values(sort_cols, ascending=False)
    
    btn_iter = btn

    # baseline assignment ONCE
    G0 = G.copy()
    G0 = msa_traffic_assignment(G0, od=od, iters=settings.msa_iters, alpha=settings.bpr_alpha, beta=settings.bpr_beta)
    base_tstt = float(total_system_travel_time(G0))
    base_delay = float(total_delay(G0))

    results_rows: list[dict] = []
    connector_rows: list[dict] = []

    tested = 0
    proposed = 0

    for i, r in enumerate(btn_iter.itertuples(index=False), start=1):
        u_val = getattr(r, "u", None)
        v_val = getattr(r, "v", None)
        k_val = getattr(r, "key", 0)

        if pd.isna(u_val) or pd.isna(v_val):
            continue

        u = int(u_val)
        v = int(v_val)
        key = int(k_val) if pd.notna(k_val) else 0

        tested += 1
        baseline_edge_name = _edge_label(edges_df, u=u, v=v, key=key)

        # propose connector near this bottleneck
        try:
            spec = propose_connector_near_edge(
                G,
                nodes_df=nodes,
                u=u,
                v=v,
                k_hops=6,              # broaden search a bit
                max_straight_m=1200.0, # allow longer bypasses
            )
        except Exception as e:
            logger.warning("No connector proposed for bottleneck {}->{}: {}", u, v, e)
            continue

        a, b = int(spec.a), int(spec.b)
        if str(a) not in node_lookup or str(b) not in node_lookup:
            continue

        proposed += 1

        speed_kph = float(spec.speed_kph)
        lanes = float(spec.lanes)
        length_m = float(spec.length_m)

        speed_mps = speed_kph * 1000.0 / 3600.0
        t0 = length_m / max(1.0, speed_mps)
        capacity = 900.0 * lanes

        scenario_id = f"bb_{proposed:04d}_u{u}_v{v}_a{a}_b{b}"
        connector_name = f"Bypass near {baseline_edge_name}"

        # apply + assign
        G1 = G.copy()
        apply_connector(G1, spec)
        G1 = msa_traffic_assignment(G1, od=od, iters=settings.msa_iters, alpha=settings.bpr_alpha, beta=settings.bpr_beta)

        scen_tstt = float(total_system_travel_time(G1))
        scen_delay = float(total_delay(G1))

        improve_delay = base_delay - scen_delay
        improve_pct = (improve_delay / base_delay * 100.0) if base_delay > 0 else None
        status = "Improves" if improve_delay > 0 else ("Worsens" if improve_delay < 0 else "No change")

        results_rows.append({
            "scenario_id": scenario_id,
            "status": status,
            "baseline_edge_name": baseline_edge_name,
            "baseline_bottleneck_u": u,
            "baseline_bottleneck_v": v,
            "connector_a": a,
            "connector_b": b,
            "connector_name": connector_name,
            "connector_length_m": length_m,
            "connector_speed_kph": speed_kph,
            "connector_lanes": lanes,
            "baseline_tstt_veh_hours": base_tstt,
            "baseline_delay_veh_hours": base_delay,
            "scenario_tstt_veh_hours": scen_tstt,
            "scenario_delay_veh_hours": scen_delay,
            "delta_tstt_veh_hours": scen_tstt - base_tstt,
            "delta_delay_veh_hours": scen_delay - base_delay,
            "improve_delay_veh_hours": improve_delay,
            "improve_delay_pct": improve_pct,
        })

        connector_rows.append(
            _connector_edges_row(
                node_lookup,
                a, b,
                scenario_id=scenario_id,
                base_u=u,
                base_v=v,
                connector_name=connector_name,
                baseline_edge_name=baseline_edge_name,
                length_m=length_m,
                speed_kph=speed_kph,
                lanes=lanes,
                capacity=float(capacity),
                t0=float(t0),
                status=status,
                improve_delay_veh_hours=float(improve_delay),
                improve_delay_pct=improve_pct,
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
        notes=f"One connector per bottleneck row. Tested={tested}, Proposed={proposed}.",
    )
    write_manifest(run_path, manifest)

    logger.info("Done. Tested bottlenecks: {}", tested)
    logger.info("Proposed connectors: {}", proposed)
    logger.info("Saved results rows: {}", len(results))
    logger.info("Saved connector edges rows: {}", len(connector_edges))


if __name__ == "__main__":
    main()
