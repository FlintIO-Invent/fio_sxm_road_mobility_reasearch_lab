from __future__ import annotations

import networkx as nx

from sxm_mobility.assignment.metrics import total_delay, total_system_travel_time


def score_graph(G: nx.MultiDiGraph) -> dict[str, float]:
    return {
        "tstt": total_system_travel_time(G),
        "delay": total_delay(G),
    }
