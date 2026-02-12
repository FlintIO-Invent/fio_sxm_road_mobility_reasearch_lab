from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration (env vars or local .env)."""

    model_config = SettingsConfigDict(env_prefix="SXM_", extra="ignore")

    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])
    data_dir: Path = Field(default_factory=lambda: Path("data"))

    # -----------------
    # Base network build
    # -----------------
    place_query: str = "Sint Maarten"
    network_type: str = "drive"

    # -----------------
    # Edge model defaults (used to compute t0/capacity if missing)
    # -----------------
    default_speed_kph: float = 40.0
    default_capacity_vph_per_lane: float = 900.0

    # -----------------
    # Demand (OD) toggles
    # -----------------
    od_mode: str = "weighted_total"  # "random" | "weighted_total" | "zone" (later)
    od_n_pairs: int = 250
    od_total_demand_vph: float = 8000.0
    od_seed: int = 42

    # -----------------
    # Assignment (BPR/MSA)
    # -----------------
    bpr_alpha: float = 0.15
    bpr_beta: float = 4.0
    msa_iters: int = 30

    # -----------------
    # Scenarios toggles
    # -----------------
    scenarios_enabled: bool = True

    # A simple scenario “preset” approach:
    scenarios_preset: str = "v1"  # change in .env to switch scenario sets

    # Advanced: define scenario set as JSON in .env (optional)
    # Example in .env:
    # SXM_SCENARIOS_JSON=[{"type":"IncreaseCapacity","select":"top_bottlenecks","top_k":5,"pct":0.25}]
    scenarios_json: str = "[]"

    scenarios_cap_top_k: int = 5
    scenarios_cap_pct: float = 0.25
    scenarios_do_closure: bool = True
    scenarios_do_connector: bool = True
    connector_length_m: float = 350.0
    connector_speed_kph: float = 40.0
    connector_capacity_vph: float = 900.0

    def scenarios_spec(self) -> List[Dict[str, Any]]:
        """Parse scenarios_json into Python objects."""
        try:
            obj = json.loads(self.scenarios_json)
            return obj if isinstance(obj, list) else []
        except Exception:
            return []
        
    # -----------------
    # Scenarios toggles
    # -----------------
    baseline_top_n_bottlenecks: int = 50


    kpi_columns: Dict[str, str] = {
        "place_query": "Study Area",
        "network_type": "Transport Mode (Drive / Walk / Bike)",
        "total_demand_vph": "Total Demand (vehicles/hour)",
        "msa_iters": "Traffic Assignment Iterations",
        "bpr_alpha": "Congestion Sensitivity (Alpha)",
        "bpr_beta": "Congestion Curvature (Beta)",
        "od_pairs": "Origin–Destination Pairs Modeled",
        "nodes": "Intersections Modeled",
        "edges": "Road Segments Modeled",
        "tstt": "Total System Travel Time (vehicle-hours per hour)",
        "delay": "Total Congestion Delay (vehicle-hours per hour)",
        "avg_travel_time_min": "Average Travel Time (minutes per vehicle)",
        "avg_delay_min": "Average Congestion Delay (minutes per vehicle)",
    }

    btn_columns: Dict[str, str] = {
        "u": "Origin Node ID",
        "v": "Destination Node ID",
        "key": "Edge Key",
        "flow": "Traffic Flow (vehicles/hour)",
        "capacity": "Edge Capacity (vehicles/hour)",
        "v_c": "Volume-to-Capacity Ratio",
        "delay": "Congestion Delay (hours)",
    }

    scen_columns: Dict[str, str] = {
        "scenario_name": "Scenario Name",
        "scenario_type": "Transport Mode (Drive / Walk / Bike)",
        "tstt": "Total System Travel Time (hours)",
        "delay": "Total Congestion Delay (hours)",
        "delta_tstt": "Change in Total System Travel Time (hours)",
        "delta_delay": "Change in Total Congestion Delay (hours)",
        "baseline_tstt": "Baseline Total System Travel Time (hours)",
        "baseline_delay": "Baseline Total Congestion Delay (hours)",
        "od_pairs": "Origin–Destination Pairs Modeled",
        "msa_iters": "Traffic Assignment Iterations",
        "bpr_alpha": "Congestion Sensitivity (Alpha)",
        "bpr_beta": "Congestion Curvature (Beta)",
        "delay_improvement": "Congestion Delay Improvement (%)",
       
    }

    

    





settings = Settings()
