from __future__ import annotations

from pathlib import Path
import pandas as pd
from loguru import logger
from datetime import datetime
from sxm_mobility.config import settings
from sxm_mobility.io.osm_ingest import load_gpickle
from sxm_mobility.demand.od_generation import load_od_parquet, scale_od
from sxm_mobility.assignment.msa import msa_traffic_assignment
from sxm_mobility.assignment.metrics import total_delay, total_system_travel_time
from sxm_mobility.experiments.run_manager import (
    base_dir,
    create_run_dir,
    write_manifest,
    RunManifest,
    list_runs,
    od_path,
    solution_experiment_path
    
)

def avg_minutes_per_vehicle(metric_veh_hours: float, total_demand_vph: float) -> float:
    if total_demand_vph <= 0:
        return 0.0
    return (metric_veh_hours / total_demand_vph) * 60.0

def main() -> None:
    graph_path = base_dir() / "graph.gpickle"
    if not graph_path.exists():
        raise FileNotFoundError(f"Missing base graph: {graph_path}. Run scripts/build_graph.py first.")
    G_base = load_gpickle(graph_path)
    baseline_runs = list_runs("baseline")
    baseline_run = baseline_runs[0] if baseline_runs else None
    G_base = load_gpickle(graph_path)
    od_base = load_od_parquet(od_path(baseline_run))

    run_path = create_run_dir("demand_reduction")
    logger.info("solution Experiment run folder: {}", run_path)

    base_demand = sum(q for *_, q in od_base)
    logger.info(f"Baseline total demand (vph): {base_demand:.2f}")

    # Choose a sweep (edit freely)
    reductions = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]

    rows: list[dict] = []

    # Optional: compute baseline KPIs for comparison
    G0 = G_base.copy()
    G0 = msa_traffic_assignment(G0, od=od_base, iters=settings.msa_iters, alpha=settings.bpr_alpha, beta=settings.bpr_beta)
    base_tstt = total_system_travel_time(G0)
    base_delay = total_delay(G0)
    base_avg_tt = avg_minutes_per_vehicle(base_tstt, base_demand)
    base_avg_delay = avg_minutes_per_vehicle(base_delay, base_demand)

    for r in reductions:
        factor = settings.od_factor - r
        od = scale_od(od_base, factor)
        total_demand = sum(q for *_, q in od)

        G = G_base.copy()
        G = msa_traffic_assignment(G, od=od, iters=settings.msa_iters, alpha=settings.bpr_alpha, beta=settings.bpr_beta)

        tstt = total_system_travel_time(G)
        delay = total_delay(G)

        rows.append({
            "reduction_pct": int(round(r * 100)),
            "factor": factor,
            "total_demand_vph": total_demand,
            "tstt_veh_hours": tstt,
            "delay_veh_hours": delay,
            "avg_travel_time_min": avg_minutes_per_vehicle(tstt, total_demand),
            "avg_delay_min": avg_minutes_per_vehicle(delay, total_demand),
            "delta_delay_veh_hours": delay - base_delay,
            "delta_avg_delay_min": avg_minutes_per_vehicle(delay, total_demand) - base_avg_delay,
        })

        logger.info(f"Reduction {int(r*100)}% -> avg_delay={rows[-1]['avg_delay_min']:.2f} min/veh")
    
    

    df = pd.DataFrame(rows).sort_values("reduction_pct")
    df.to_parquet(solution_experiment_path(run_path), index=False)

    manifest = RunManifest(
        run_name=run_path.name,
        experiment="demand_reduction",
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
    logger.info(f"Saved demand reduction sweep: {solution_experiment_path}")

    # Find the “ideal” reduction to hit a target
    target_avg_delay_min = 1.0  # edit: target average delay per vehicle
    hit = df[df["avg_delay_min"] <= target_avg_delay_min]
    if not hit.empty:
        best = hit.iloc[0]
        logger.info(f"Target hit: avg_delay <= {target_avg_delay_min} at reduction={best['reduction_pct']}%")
    else:
        logger.info(f"No reduction in sweep achieved avg_delay <= {target_avg_delay_min} min/veh")

if __name__ == "__main__":
    main()
