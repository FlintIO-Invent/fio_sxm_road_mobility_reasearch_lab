from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sxm_mobility.config import settings



def processed_dir() -> Path:
    return Path(settings.data_dir) / "processed"


def base_dir() -> Path:
    return processed_dir() / "base"


def runs_dir() -> Path:
    return processed_dir() / "runs"


def now_stamp() -> str:
    # 20260210_1430
    return datetime.now().strftime("%Y%m%d_%H%M")


def slugify(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name.strip()).lower()


@dataclass
class RunManifest:
    run_name: str
    experiment: str
    created_at: str
    place_query: str
    network_type: str
    od_mode: str
    total_demand_vph: float
    n_pairs: int
    msa_iters: int
    bpr_alpha: float
    bpr_beta: float
    notes: str = ""


def create_run_dir(experiment: str, tag: str | None = None) -> Path:
    """Create a unique run folder under data/processed/runs/."""
    exp = slugify(experiment)
    suffix = slugify(tag) if tag else now_stamp()
    run_name = f"{exp}__{suffix}"
    run_path = runs_dir() / run_name
    run_path.mkdir(parents=True, exist_ok=False)
    return run_path


def write_manifest(run_path: Path, manifest: RunManifest) -> Path:
    path = run_path / "manifest.json"
    path.write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
    return path


def read_manifest(run_path: Path) -> dict[str, Any]:
    path = run_path / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def list_runs(experiment: str | None = None) -> list[Path]:
    """List run directories, optionally filtered by experiment prefix."""
    root = runs_dir()
    if not root.exists():
        return []
    runs = [p for p in root.iterdir() if p.is_dir()]
    runs.sort(key=lambda p: p.name, reverse=True)  # newest first (by name stamp)
    if experiment:
        exp = slugify(experiment)
        runs = [p for p in runs if p.name.startswith(exp + "__")]
    return runs


def latest_run(experiment: str | None = None) -> Path | None:
    runs = list_runs(experiment=experiment)
    return runs[0] if runs else None


# Standard artifact locations inside a run folder
def od_path(run_path: Path) -> Path:
    return run_path / "od.parquet"


def baseline_kpi_path(run_path: Path) -> Path:
    return run_path / "results_baseline.parquet"


def baseline_bottlenecks_path(run_path: Path) -> Path:
    return run_path / "baseline_bottlenecks.parquet"


def scenarios_path(run_path: Path) -> Path:
    return run_path / "results_scenarios.parquet"


def scenario_details_path(run_path: Path) -> Path:
    return run_path / "scenario_details.parquet"


def solution_experiment_path(run_path: Path) -> Path:
    return run_path / "results_solution_experiment_path.parquet"