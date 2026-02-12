from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from loguru import logger

from sxm_mobility.assignment.msa import msa_traffic_assignment
from sxm_mobility.config import settings
from sxm_mobility.io.osm_ingest import load_gpickle

from sxm_mobility.scenarios.catalog import AddConnector, Closure, IncreaseCapacity
from sxm_mobility.scenarios.runner import run_scenario
from sxm_mobility.scenarios.evaluator import score_graph

from sxm_mobility.demand.od_generation import load_od_parquet, save_od_parquet
from sxm_mobility.demand.od_generation import generate_od_weighted_total
from sxm_mobility.experiments.run_manager import (
    base_dir,
    create_run_dir,
    write_manifest,
    RunManifest,
    list_runs,
    od_path,
    scenarios_path,
    scenario_details_path,
    baseline_kpi_path,
)


def _as_json(x: object) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


def main() -> None:
    graph_path = base_dir() / "graph.gpickle"
    if not graph_path.exists():
        raise FileNotFoundError(f"Missing base graph: {graph_path}. Run scripts/build_graph.py first.")
    base_G = load_gpickle(graph_path)

    baseline_runs = list_runs("baseline")
    baseline_run = baseline_runs[0] if baseline_runs else None

    baseline_delay = 0.0
    baseline_tstt = 0.0
    if baseline_run:
        try:
            kpi = pd.read_parquet(baseline_kpi_path(baseline_run))
            baseline_delay = float(kpi.iloc[0].get("delay", 0.0))
            baseline_tstt = float(kpi.iloc[0].get("tstt", 0.0))
            logger.info("Using baseline run for deltas: {}", baseline_run.name)
        except Exception as e:
            logger.warning("Could not read baseline KPI (will compute baseline inside scenarios): {}", e)
            baseline_run = None

    run_path = create_run_dir("scenarios")
    logger.info("Scenario run folder: {}", run_path)

    if baseline_run and (od_path(baseline_run)).exists():
        od = load_od_parquet(od_path(baseline_run))
        logger.info("Loaded OD from baseline run: {}", baseline_run.name)
    else:
        od = generate_od_weighted_total(
            base_G,
            n_pairs=settings.od_n_pairs,
            total_demand_vph=settings.od_total_demand_vph,
            seed=settings.od_seed,
        )

        logger.info("Generated OD (fallback)")

    save_od_parquet(od, od_path(run_path))

    if not baseline_run:
        logger.info("Computing baseline inside scenarios (for deltas)")
        baseline_G = msa_traffic_assignment(
            base_G.copy(),
            od=od,
            iters=settings.msa_iters,
            alpha=settings.bpr_alpha,
            beta=settings.bpr_beta,
        )
        baseline_scores = score_graph(baseline_G)
        baseline_tstt = float(baseline_scores.get("tstt", 0.0))
        baseline_delay = float(baseline_scores.get("delay", 0.0))

    edges = list(base_G.edges(keys=True))
    scenarios = []

    for i, (u, v, k) in enumerate(edges[: settings.scenarios_cap_top_k]):
        scenarios.append(
            IncreaseCapacity(
                name=f"Increase capacity {i+1}",
                description="Increase capacity on a selected edge",
                u=int(u), v=int(v), key=int(k),
                pct=settings.scenarios_cap_pct,
            )
        )

    if settings.scenarios_do_closure and edges:
        u, v, k = edges[0]
        scenarios.append(
            Closure(
                name="Closure test (first edge)",
                description="Remove one edge to test fragility",
                u=int(u), v=int(v), key=int(k),
            )
        )

    if settings.scenarios_do_connector:
        nodes = list(base_G.nodes())
        if len(nodes) >= 2:
            scenarios.append(
                AddConnector(
                    name="Add connector (prototype)",
                    description="Add a hypothetical connector edge",
                    u=int(nodes[0]),
                    v=int(nodes[-1]),
                    length_m=settings.connector_length_m,
                    speed_kph=settings.connector_speed_kph,
                    capacity_vph=settings.connector_capacity_vph,
                )
            )

    results_rows = []
    details_rows = []

    for s in scenarios:
        res = run_scenario(
        base_graph=base_G.copy(),
        od=od,
        scenario=s,
        iters=settings.msa_iters,
        alpha=settings.bpr_alpha,
        beta=settings.bpr_beta,
    )

        scores = res["scores"]
        scenario_dict = res["scenario"]

        tstt = float(scores.get("tstt", 0.0))
        delay = float(scores.get("delay", 0.0))

        row = {
            "scenario_name": scenario_dict.get("name"),
            "scenario_type": s.__class__.__name__,
            "tstt": tstt,
            "delay": delay,
            "baseline_tstt": baseline_tstt,
            "baseline_delay": baseline_delay,
            "delta_tstt": tstt - baseline_tstt,
            "delta_delay": delay - baseline_delay,
            "delay_improvement": -(delay - baseline_delay),
            "delay_improvement_pct": (100.0 * (-(delay - baseline_delay) / baseline_delay)) if baseline_delay else 0.0,
            "od_pairs": len(od),
            "msa_iters": settings.msa_iters,
            "bpr_alpha": settings.bpr_alpha,
            "bpr_beta": settings.bpr_beta,
        }
        results_rows.append(row)

        details_rows.append(
            {
                "scenario_name": scenario_dict.get("name"),
                "scenario_type": s.__class__.__name__,
                "description": scenario_dict.get("description"),
                "params_json": _as_json({k: v for k, v in scenario_dict.items() if k not in {"name", "description"}}),
            }
        )

    df_results = pd.DataFrame(results_rows).sort_values("delay_improvement", ascending=False)
    df_details = pd.DataFrame(details_rows)

    df_results.to_parquet(scenarios_path(run_path), index=False)
    df_details.to_parquet(scenario_details_path(run_path), index=False)

    manifest = RunManifest(
        run_name=run_path.name,
        experiment="scenarios",
        created_at=datetime.now().isoformat(timespec="seconds"),
        place_query=settings.place_query,
        network_type=settings.network_type,
        od_mode="from_baseline_run" if baseline_run else "generated_fallback",
        total_demand_vph=float(sum(d for _, _, d in od)),
        n_pairs=len(od),
        msa_iters=settings.msa_iters,
        bpr_alpha=settings.bpr_alpha,
        bpr_beta=settings.bpr_beta,
        notes=f"Compared against baseline run: {baseline_run.name if baseline_run else 'computed inside scenarios'}",
    )
    write_manifest(run_path, manifest)

    logger.info("Saved scenario run outputs to {}", run_path)


if __name__ == "__main__":
    main()
