from __future__ import annotations

from datetime import datetime
import pandas as pd
from loguru import logger

from sxm_mobility.assignment.metrics import top_bottlenecks, total_delay, total_system_travel_time
from sxm_mobility.assignment.msa import msa_traffic_assignment
from sxm_mobility.config import settings
from sxm_mobility.io.osm_ingest import load_gpickle
from sxm_mobility.demand.od_generation import generate_od_weighted_total, save_od_parquet

from sxm_mobility.experiments.run_manager import (
    base_dir,
    create_run_dir,
    write_manifest,
    RunManifest,
    od_path,
    baseline_kpi_path,
    baseline_bottlenecks_path,
)


def main() -> None:
    """Baseline experiment run.

    Reads:
      - Base graph: data/processed/base/graph.gpickle

    Writes (into a new run folder):
      - data/processed/runs/baseline__.../od.parquet
      - data/processed/runs/baseline__.../baseline_bottlenecks.parquet
      - data/processed/runs/baseline__.../results_baseline.parquet
      - data/processed/runs/baseline__.../manifest.json
    """

    graph_path = base_dir() / "graph.gpickle"
    if not graph_path.exists():
        raise FileNotFoundError(f"Missing base graph: {graph_path}. Run scripts/build_graph.py first.")
    G = load_gpickle(graph_path)

    run_path = create_run_dir("baseline")
    logger.info("Run folder: {}", run_path)

    od = generate_od_weighted_total(
        G,
        n_pairs=settings.od_n_pairs,
        total_demand_vph=settings.od_total_demand_vph,
        seed=settings.od_seed,
    )
    save_od_parquet(od, od_path(run_path))

    total_demand_vph = float(sum(d for _, _, d in od))
    logger.info("OD pairs: {} | total_demand_vph: {:.2f}", len(od), total_demand_vph)

    # Run assignment (MSA mutates G, but we reassign for clarity)
    G = msa_traffic_assignment(
        G,
        od=od,
        iters=settings.msa_iters,
        alpha=settings.bpr_alpha,
        beta=settings.bpr_beta,
    )

    # Bottlenecks (consider adding this to Settings later)
    df_b = pd.DataFrame(top_bottlenecks(G, n=50))
    for c in ["u", "v", "key"]:
        if c in df_b.columns:
            df_b[c] = pd.to_numeric(df_b[c], errors="coerce").astype("Int64")
    df_b.to_parquet(baseline_bottlenecks_path(run_path), index=False)

    # KPI summary
    tstt = total_system_travel_time(G)
    delay = total_delay(G)

    # These KPIs are *system totals* per hour. Divide by demand to get per-vehicle averages.
    avg_travel_time_min = (tstt / total_demand_vph) * 60.0 if total_demand_vph > 0 else 0.0
    avg_delay_min = (delay / total_demand_vph) * 60.0 if total_demand_vph > 0 else 0.0

    summary = {
        "place_query": settings.place_query,
        "network_type": settings.network_type,
        "total_demand_vph": total_demand_vph,
        "msa_iters": settings.msa_iters,
        "bpr_alpha": settings.bpr_alpha,
        "bpr_beta": settings.bpr_beta,
        "od_pairs": len(od),
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        # System totals (vehicle-hours per hour)
        # (also written under legacy keys `tstt` and `delay` for dashboard compatibility)
        "tstt": tstt,
        "delay": delay,
        "tstt_vh_per_h": tstt,
        "delay_vh_per_h": delay,
        # Per-vehicle averages (minutes per trip)
        "avg_travel_time_min": avg_travel_time_min,
        "avg_delay_min": avg_delay_min,
    }
    pd.DataFrame([summary]).to_parquet(baseline_kpi_path(run_path), index=False)

    manifest = RunManifest(
        run_name=run_path.name,
        experiment="baseline",
        created_at=datetime.now().isoformat(timespec="seconds"),
        place_query=settings.place_query,
        network_type=settings.network_type,
        od_mode=settings.od_mode if hasattr(settings, "od_mode") else "weighted_total",
        total_demand_vph=total_demand_vph,
        n_pairs=len(od),
        msa_iters=settings.msa_iters,
        bpr_alpha=settings.bpr_alpha,
        bpr_beta=settings.bpr_beta,
        notes="Baseline run using saved OD and artifacts for reproducibility.",
    )
    write_manifest(run_path, manifest)

    logger.info("Saved baseline outputs to {}", run_path)


if __name__ == "__main__":
    main()
