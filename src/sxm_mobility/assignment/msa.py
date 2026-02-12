from __future__ import annotations

from collections import defaultdict
from typing import Hashable
from loguru import logger

import networkx as nx

from sxm_mobility.assignment.bpr import bpr_time


def update_edge_times(G: nx.MultiDiGraph, alpha: float, beta: float) -> None:
    """Update each edge's travel time using a BPR-style travel time function.

    For every edge in `G`, reads:
      - `t0`: free-flow travel time (defaults to 1.0 if missing)
      - `capacity`: edge capacity (defaults to 1.0 if missing)
      - `flow`: current assigned flow (defaults to 0.0 if missing)

    Then writes:
      - `time`: updated travel time computed by `bpr_time(...)`.

    Side effects:
      - Mutates `G` in-place by setting `data["time"]` for each edge.

    :param G: Directed multigraph whose edges contain `t0`, `capacity`, and `flow`
        attributes used to compute updated travel time.
    :type G: nx.MultiDiGraph
    :param alpha: BPR alpha parameter controlling congestion sensitivity.
    :type alpha: float
    :param beta: BPR beta parameter controlling congestion curvature.
    :type beta: float
    :return: None
    :rtype: None
    """
    for _, _, _, data in G.edges(keys=True, data=True):
        t0 = float(data.get("t0", 1.0))
        cap = float(data.get("capacity", 1.0))
        flow = float(data.get("flow", 0.0))
        data["time"] = bpr_time(t0=t0, flow=flow, capacity=cap, alpha=alpha, beta=beta)


def all_or_nothing_assignment(
    G: nx.MultiDiGraph,
    od: list[tuple[Hashable, Hashable, float]],
) -> dict[tuple[Hashable, Hashable, int], float]:
    """Assign all OD demand to current shortest paths (by edge travel time).

    For each OD pair `(origin, destination, demand)`:
      - Computes the shortest path using edge attribute `"time"` as the weight.
      - For each consecutive node pair `(u, v)` along the path, selects the parallel
        edge key with the minimum `"time"` and adds the OD demand to that edge.

    Notes:
      - Returns a mapping keyed by `(u, v, key)` using the graph's native node ids.
      - OD pairs whose endpoints are not present in `G` are skipped.

    :param G: Directed multigraph where edges carry a `"time"` attribute used for routing.
    :type G: nx.MultiDiGraph
    :param od: List of OD demands as `(origin, destination, demand)` tuples.
    :type od: list[tuple[Hashable, Hashable, float]]
    :return: Auxiliary flow assignment mapping `(u, v, key) -> assigned_flow`.
    :rtype: dict[tuple[Hashable, Hashable, int], float]
    """
    aux: dict[tuple[Hashable, Hashable, int], float] = defaultdict(float)

    for o, d, demand in od:
        if o not in G or d not in G:
            continue

        path = nx.shortest_path(G, o, d, weight="time")
        for u, v in zip(path[:-1], path[1:]):
            # choose best key among parallel edges
            best_key = min(G[u][v], key=lambda k: float(G[u][v][k].get("time", 1.0)))
            aux[(u, v, int(best_key))] += float(demand)

    return dict(aux)


def msa_traffic_assignment(
    G: nx.MultiDiGraph,
    od: list[tuple[Hashable, Hashable, float]],
    iters: int = 30,
    alpha: float = 0.15,
    beta: float = 4.0,
) -> nx.MultiDiGraph:
    """Run Method of Successive Averages (MSA) traffic assignment on a network.

    This routine iteratively updates edge flows using the MSA step size:
        step_k = 1 / (k + 1)

    High-level steps:
      1) Initialize each edge's `flow` and `time` (time starts as free-flow `t0` if available).
      2) For `iters` iterations:
         - Update edge travel times using a BPR-style function (`update_edge_times`).
         - Compute auxiliary "all-or-nothing" flows for the current travel times
           (`all_or_nothing_assignment`).
         - Update each edge's flow with the MSA convex combination.
      3) Update edge travel times one final time and return the modified graph.

    Side effects:
      - Mutates `G` in-place by updating edge attributes (at least `flow` and `time`).

    :param G: Directed multigraph representing the road network. Edges are expected to
        carry `time` and/or `t0` (free-flow time) and will be updated with `flow` and `time`.
    :type G: nx.MultiDiGraph
    :param od: List of OD demands as `(origin, destination, demand)` tuples. Origins and
        destinations must match node IDs present in `G`.
    :type od: list[tuple[Hashable, Hashable, float]]
    :param iters: Number of MSA iterations to perform, defaults to 30.
    :type iters: int, optional
    :param alpha: BPR alpha parameter passed through to `update_edge_times`,
        defaults to 0.15.
    :type alpha: float, optional
    :param beta: BPR beta parameter passed through to `update_edge_times`,
        defaults to 4.0.
    :type beta: float, optional
    :raises ValueError: If `iters` is negative.
    :return: The same graph instance `G`, with updated edge `flow` and `time` attributes.
    :rtype: nx.MultiDiGraph
    """
    if iters < 0:
        raise ValueError("iters must be >= 0")

    # Quick sanity check before assignment loops (helps debug OD/graph mismatch)
    assigned = 0
    failed = 0
    for o, d, _ in od:
        if o not in G or d not in G:
            failed += 1
            continue
        assigned += 1
    logger.info("Assigned OD (endpoints found): {}, Failed OD (missing endpoints): {}", assigned, failed)

    for _, _, _, data in G.edges(keys=True, data=True):
        data["flow"] = float(data.get("flow", 0.0))
        data["time"] = float(data.get("t0", data.get("time", 1.0)))

    for k in range(iters):
        update_edge_times(G, alpha=alpha, beta=beta)
        aux = all_or_nothing_assignment(G, od)

        step = 1.0 / (k + 1.0)

        for u, v, key, data in G.edges(keys=True, data=True):
            a = float(aux.get((u, v, int(key)), 0.0))
            f = float(data.get("flow", 0.0))
            data["flow"] = f + step * (a - f)

    update_edge_times(G, alpha=alpha, beta=beta)
    return G

