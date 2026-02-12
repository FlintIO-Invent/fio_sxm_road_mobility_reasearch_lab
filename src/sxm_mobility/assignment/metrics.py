from __future__ import annotations

from typing import Any

import networkx as nx


def total_system_travel_time(G: nx.MultiDiGraph) -> float:
    """Compute total system travel time (TSTT) over all edges.

    TSTT is computed as the sum over edges of:
        flow * time

    Missing attributes default to 0.0.

    :param G: Directed multigraph whose edges contain `flow` and `time` attributes.
    :type G: nx.MultiDiGraph
    :return: Total system travel time (sum of flow * time).
    :rtype: float
    """
    # Note on units:
    #   - `time` is in seconds (t0/time)
    #   - `flow` is in vehicles/hour (from OD demand)
    # So flow * time gives vehicle-seconds per hour; divide by 3600 to get vehicle-hours per hour.
    return float(
        sum(float(d.get("flow", 0.0)) * float(d.get("time", 0.0)) for *_, d in G.edges(data=True, keys=True))
        / 3600.0
    )


def total_delay(G: nx.MultiDiGraph) -> float:
    """Compute total delay over all edges relative to free-flow time.

    Total delay is computed as the sum over edges of:
        flow * (time - t0)

    Where:
    - `time` is the (possibly congested) travel time on the edge
    - `t0` is the free-flow travel time
    - If `t0` is missing, it falls back to `time` (yielding zero delay for that edge)

    Missing `flow` defaults to 0.0.

    :param G: Directed multigraph whose edges contain `flow`, `time`, and optionally `t0`.
    :type G: nx.MultiDiGraph
    :return: Total delay (flow-weighted excess time over free-flow).
    :rtype: float
    """
    return float(
        sum(
            float(d.get("flow", 0.0))
            * (float(d.get("time", 0.0)) - float(d.get("t0", d.get("time", 0.0))))
            for *_, d in G.edges(data=True, keys=True)
        )
        / 3600.0
    )


def top_bottlenecks(G: nx.MultiDiGraph, n: int = 20) -> list[dict[str, Any]]:
    """Rank and return the top bottleneck edges by delay and volume/capacity.

    For each edge, this computes:
    - `v_c`: volume/capacity ratio (flow / capacity), with capacity<=0 treated as 0.0
    - `delay`: flow * (time - t0)

    Results are sorted descending by `(delay, v_c)` and truncated to the top `n`.

    :param G: Directed multigraph whose edges contain `flow`, `capacity`, `time`, and optionally `t0`.
    :type G: nx.MultiDiGraph
    :param n: Number of bottleneck rows to return, defaults to 20.
    :type n: int, optional
    :raises ValueError: If `n` is negative.
    :return: A list of dict rows with keys: u, v, key, flow, capacity, v_c, delay.
    :rtype: list[dict[str, Any]]
    """
    if n < 0:
        raise ValueError("n must be >= 0")

    rows = []
    for u, v, k, d in G.edges(keys=True, data=True):
        flow = float(d.get("flow", 0.0))
        cap = float(d.get("capacity", 1.0))
        vc = flow / cap if cap > 0 else 0.0
        # IMPORTANT: if t0 is missing, fall back to `time` so delay doesn't blow up.
        t = float(d.get("time", 0.0))
        t0 = float(d.get("t0", t))
        delay = flow * (t - t0) / 3600.0
        rows.append(
            {
                "u": u,
                "v": v,
                "key": int(k),
                "flow": flow,
                "capacity": cap,
                "v_c": vc,
                "delay": delay,
            }
        )

    rows.sort(key=lambda r: (r["delay"], r["v_c"]), reverse=True)
    return rows[:n]
