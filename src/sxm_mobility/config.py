from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, ClassVar
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
    od_total_demand_vph: float = 25000.0
    od_seed: int = 42
    od_factor: float = 1.0 # percentage of reduction for this scenario's helper


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
    max_to_test : int = 100

    kpi_columns_mapping: ClassVar[Dict[str, str]] = {
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

    dr_columns_mapping: ClassVar[Dict[str, str]] = {
        # Inputs / sweep settings
        "reduction_pct": "Demand Reduction (%)",
        "factor": "Remaining Demand Factor",

        # System performance (absolute)
        "tstt_veh_hours": "Total Travel Time (veh-hours)",
        "delay_veh_hours": "Total Congestion Delay (veh-hours)",
        "avg_travel_time_min": "Avg Travel Time (min/vehicle)",
        "avg_delay_min": "Avg Congestion Delay (min/vehicle)",
        "total_demand_vph": "Total Demand (vehicles/hour)",

        # Change vs baseline
        "delta_delay_veh_hours": "Delay Change vs Baseline (veh-hours)",
        "delta_avg_delay_min": "Avg Delay Change vs Baseline (min/vehicle)",
    }

    BYPASS_COLUMNS_MAPPING: ClassVar[Dict[str, str]] = {
        "scenario_id": "Scenario ID",
        "connector_name": "Proposed Connector Name",
        "status": "Result (Improves/Worsens)",
        "improve_delay_veh_hours": "Delay Reduction (veh-hours)",
        "improve_delay_pct": "Delay Reduction (%)",
        "connector_length_m": "Connector Length (m)",
        "connector_speed_kph": "Assumed Speed (km/h)",
        "connector_lanes": "Assumed Lanes",
        "baseline_bottleneck_u": "Bottleneck Node (From)",
        "baseline_bottleneck_v": "Bottleneck Node (To)",
        "connector_a": "Connector Node A",
        "connector_b": "Connector Node B",
    }




    KPI_HELP: ClassVar[dict[str, str]] = {
        "Study Area": "The area the road network was downloaded/built for (e.g., Sint Maarten).",
        "Transport Mode (Drive / Walk / Bike)": "The network mode used when building the graph (drive / walk / bike).",
        "Total Demand (vehicles/hour)": "Total simulated demand loaded into the network per hour (vehicles/hour).",
        "Origin–Destination Pairs Modeled": "Number of origin–destination pairs used to generate the traffic load.",
        "Traffic Assignment Iterations": "Number of iterations used by the traffic assignment method (MSA).",
        "Congestion Sensitivity (Alpha)": "How strongly congestion increases travel time as roads fill up (BPR alpha).",
        "Congestion Curvature (Beta)": "How sharply travel time increases near/over capacity (BPR beta).",
        "Intersections Modeled": "Total intersections/junction points modeled in the graph.",
        "Road Segments Modeled": "Total road segments modeled in the graph.",
        "Total System Travel Time (vehicle-hours per hour)": "The sum of (flow × travel time) across all road segments, expressed in vehicle-hours per hour.",
        "Total Congestion Delay (vehicle-hours per hour)": "The sum of (flow × (time − free-flow time)) across all segments, expressed in vehicle-hours per hour.",
        "Average Travel Time (minutes per vehicle)": "Average travel time per vehicle (minutes). Computed from total system travel time divided by total demand.",
        "Average Congestion Delay (minutes per vehicle)": "Average congestion delay per vehicle (minutes). Computed from total delay divided by total demand.",
    }

    BOTTLENECK_HELP: ClassVar[dict[str, str]] ={
        "Road": "The road name (when available from OpenStreetMap). If missing, it may show the road type.",
        "From": "Start intersection of the road segment.",
        "To": "Start intersection of the road segment.",
        "delay": "Congestion delay contributed by this segment (vehicle-hours). Higher = bigger system impact.",
        "v_c": "Volume-to-capacity ratio (flow ÷ capacity). Around/above 1.0 indicates overload.",
        "flow": "Vehicles/hour using this road segment in the simulation.",
        "capacity": "Estimated vehicles/hour this road segment can handle (proxy until calibrated).",
        "length": "The road segment length in meters.",
        "avg delay (sec/veh)": "Average congestion delay per vehicle on that road segment (seconds/vehicle).",

    }

    DR_HELP: ClassVar[Dict[str, str]] = {
        "Demand Reduction (%)": (
            "How much we reduce peak-hour traffic in this test. "
            "Example: 10% means 10% fewer vehicles/trips on the road."
        ),
        "Remaining Demand Factor": (
            "The share of traffic still on the road after the reduction. "
            "Example: 0.90 means 90% of the original traffic remains."
        ),
        "Total Travel Time (veh-hours)": (
            "Total time spent by all vehicles traveling in the network during the simulated hour. "
            "Higher means the system is slower overall."
        ),
        "Total Congestion Delay (veh-hours)": (
            "Extra time caused by congestion across all vehicles (above free-flow conditions). "
            "Higher means more traffic-related delay."
        ),
        "Avg Travel Time (min/vehicle)": (
            "Average trip travel time per vehicle in minutes. "
            "This is easier to interpret than system totals."
        ),
        "Avg Congestion Delay (min/vehicle)": (
            "Average extra delay per vehicle due to congestion (in minutes). "
            "Lower is better."
        ),
        "Delay Change vs Baseline (veh-hours)": (
            "How total congestion delay changed compared with the baseline (no reduction). "
            "Negative means improvement (less delay); positive means worse."
        ),
        "Avg Delay Change vs Baseline (min/vehicle)": (
            "How average congestion delay per vehicle changed compared with baseline. "
            "Negative means improvement; positive means worse."
        ),
        "Total Demand (vehicles/hour)": (
            "Total simulated demand loaded into the network per hour (vehicles/hour)."
        ),
    }

    BYPASS_RESULTS_HELP: ClassVar[Dict[str, str]] = {
        "Scenario ID": (
            "Unique label for this test case so we can reference it consistently in tables and maps."
        ),
        "Proposed Connector Name": (
            "A readable name for the proposed new link, usually describing where it is and what it is meant to relieve."
        ),
        "Result (Improves/Worsens)": (
            "Whether the connector reduces total congestion delay compared with the baseline. "
            "‘Improves’ means less delay; ‘Worsens’ means more delay."
        ),
        "Delay Reduction (veh-hours)": (
            "How much total congestion delay is reduced across all drivers in the simulated busy hour. "
            "Bigger positive numbers mean a stronger improvement."
        ),
        "Delay Reduction (%)": (
            "The percent improvement in total congestion delay versus the baseline. "
            "Higher is better."
        ),
        "Connector Length (m)": (
            "Approximate straight-line length of the proposed connector (meters). "
            "Used to estimate travel time on the new link."
        ),
        "Assumed Speed (km/h)": (
            "Speed used to estimate the connector’s free-flow travel time (a planning assumption, not measured)."
        ),
        "Assumed Lanes": (
            "Lane count assumed for the connector (a planning assumption). "
            "Used to estimate how many vehicles it can carry."
        ),
        "Bottleneck Node (From)": (
            "Start junction of the original bottleneck road segment this connector is intended to relieve (node ID)."
        ),
        "Bottleneck Node (To)": (
            "End junction of the original bottleneck road segment this connector is intended to relieve (node ID)."
        ),
        "Connector Node A": (
            "Start junction of the proposed connector (node ID)."
        ),
        "Connector Node B": (
            "End junction of the proposed connector (node ID)."
        ),
    }


settings = Settings()
