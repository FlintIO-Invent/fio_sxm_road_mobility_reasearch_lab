from __future__ import annotations

from dataclasses import asdict
from typing import Hashable

import networkx as nx

from sxm_mobility.assignment.msa import msa_traffic_assignment
from sxm_mobility.scenarios.evaluator import score_graph


def run_scenario(
    base_graph: nx.MultiDiGraph,
    od: list[tuple[Hashable, Hashable, float]],
    scenario,
    iters: int,
    alpha: float,
    beta: float,
) -> dict:
    H = scenario.apply(base_graph)
    H = msa_traffic_assignment(H, od=od, iters=iters, alpha=alpha, beta=beta)
    scores = score_graph(H)
    return {"scenario": asdict(scenario), "scores": scores}
