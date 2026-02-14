from __future__ import annotations
import math
from collections import Counter
import pandas as pd
import networkx as nx


def _safe_float(x, default: float) -> float:
    try:
        return float(x)
    except Exception:
        return default


def add_freeflow_time_and_capacity(
    G: nx.MultiDiGraph,
    default_speed_kph: float = 40.0,
    default_capacity_vph_per_lane: float = 900.0,
) -> nx.MultiDiGraph:
    """Add baseline edge attributes required for traffic assignment.

    Adds/initializes the following edge attributes:
      - `t0`: free-flow travel time in seconds.
      - `capacity`: capacity in vehicles per hour (vph).
      - `flow`: initialized to 0.0 if missing.
      - `time`: initialized to `t0` if missing.

    Uses OSMnx edge attributes when available:
      - `length` (meters) for distance
      - `maxspeed` (kph) for speed (may be str/list; digits are extracted)
      - `lanes` for lane count (may be str/list)

    Capacity is treated as a simple proxy:
        capacity = default_capacity_vph * lanes

    :param G: Road network graph whose edges will be augmented in-place.
    :type G: nx.MultiDiGraph
    :param default_speed_kph: Speed to assume (kph) when `maxspeed` is missing or
        unparsable, defaults to 40.0.
    :type default_speed_kph: float, optional
    :param default_capacity_vph: Capacity per lane (vehicles/hour) when `capacity`
        must be approximated, defaults to 900.0.
    :type default_capacity_vph: float, optional
    :return: The same graph instance `G` with updated edge attributes.
    :rtype: nx.MultiDiGraph
    """
    CAP_PER_LANE = {
        "motorway": 1800, "trunk": 1700, "primary": 1400,
        "secondary": 1100, "tertiary": 900,
        "residential": 600, "service": 400,
    }

    for _, _, _, data in G.edges(keys=True, data=True):
        length_m = _safe_float(data.get("length"), 50.0)

        # Prefer OSMnx travel_time if present
        travel_time = data.get("travel_time")
        t0 = _safe_float(travel_time, math.nan)

        if not math.isfinite(t0):
            # fallback: compute from maxspeed/default
            maxspeed = data.get("maxspeed")
            if isinstance(maxspeed, list) and maxspeed:
                maxspeed = maxspeed[0]
            if isinstance(maxspeed, str):
                digits = "".join(ch for ch in maxspeed if ch.isdigit() or ch == ".")
                speed_kph = _safe_float(digits, default_speed_kph)
            else:
                speed_kph = _safe_float(maxspeed, default_speed_kph)

            speed_kph = max(5.0, speed_kph)
            speed_mps = speed_kph * 1000.0 / 3600.0
            t0 = length_m / speed_mps

        lanes = data.get("lanes")
        if isinstance(lanes, list) and lanes:
            lanes = lanes[0]
        if isinstance(lanes, str):
            lanes = lanes.replace("|", ";").split(";")[0].strip()
        lanes_f = max(1.0, _safe_float(lanes, 1.0))

        hw = data.get("highway", "residential")
        if isinstance(hw, list) and hw:
            hw = hw[0]
        cap_per_lane = CAP_PER_LANE.get(str(hw), default_capacity_vph_per_lane)
        capacity = max(50.0, float(cap_per_lane * lanes_f))

        data["t0"] = float(t0)
        data["capacity"] = capacity
        data.setdefault("flow", 0.0)
        data.setdefault("time", float(t0))

    return G


def _clean_name(x) -> str | None:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip()
    if not s or s.lower() in {"nan", "none"}:
        return None
    return s


def infer_node_road_label(edges: pd.DataFrame, node_id: int) -> str:
    """Pick the most common named road touching this node (fallback to highway class)."""
    # edges should contain: u, v, name, highway
    m = (edges["u"] == node_id) | (edges["v"] == node_id)
    local = edges.loc[m]

    # Prefer actual road names
    names = [_clean_name(x) for x in local.get("name", pd.Series(dtype=object)).tolist()]
    names = [n for n in names if n]
    if names:
        return Counter(names).most_common(1)[0][0]

    # Fallback: use highway class
    hw = [_clean_name(x) for x in local.get("highway", pd.Series(dtype=object)).tolist()]
    hw = [h for h in hw if h]
    if hw:
        return Counter(hw).most_common(1)[0][0]

    return f"Junction {node_id}"


def make_connector_name(
    edges: pd.DataFrame,
    a: int,
    b: int,
    bottleneck_road_name: str | None = None,
) -> str:
    a_label = infer_node_road_label(edges, a)
    b_label = infer_node_road_label(edges, b)

    if bottleneck_road_name:
        bn = _clean_name(bottleneck_road_name)
        if bn:
            return f"{a_label} ↔ {b_label} Connector (Bypass near {bn})"

    return f"{a_label} ↔ {b_label} Connector"


def clean_osm_text(x) -> str | None:
    if x is None:
        return None
    if isinstance(x, list) and x:
        x = x[0]
    s = str(x).strip()
    if s.lower() in {"nan", "none", ""}:
        return None
    return s
