# from __future__ import annotations
# import random
# from typing import Iterable
# import networkx as nx
# import random


# def random_od(
#     G: "nx.Graph",
#     n_pairs: int = 250,
#     min_demand: float = 50.0,
#     max_demand: float = 150.0,
#     seed: int = 42,
# ) -> list[tuple[Any, Any, float]]:
#     """Generate random(Because you don’t yet have real travel demand data (mobile-phone OD matrices, traffic counts per zone, surveys, etc.)) 
#     origin-destination (OD) demand pairs from a graph's nodes.

#     Samples `n_pairs` (origin, destination) node pairs uniformly at random from `G.nodes`,
#     ensuring origin != destination, and assigns each pair a random demand value drawn
#     uniformly from [`min_demand`, `max_demand`].

#     :param G: Input graph whose nodes are used to sample origins and destinations.
#     :type G: nx.Graph
#     :param n_pairs: Number of OD pairs to generate, defaults to 250.
#     :type n_pairs: int, optional
#     :param min_demand: Lower bound for the uniform demand draw, defaults to 50.0.
#     :type min_demand: float, optional
#     :param max_demand: Upper bound for the uniform demand draw, defaults to 150.0.
#     :type max_demand: float, optional
#     :param seed: Random seed for reproducible sampling, defaults to 42.
#     :type seed: int, optional
#     :raises ValueError: If `n_pairs` is negative.
#     :raises ValueError: If `min_demand` is greater than `max_demand`.
#     :raises ValueError: If `G` has fewer than 2 nodes.
#     :return: A list of `(origin, destination, demand)` tuples.
#     :rtype: list[tuple[Any, Any, float]]

#     How you’ll upgrade it later (natural evolution)
#         Replace “random OD” with:
#         zone-based OD (Airport, Philipsburg, Simpson Bay, etc.)
#         weighted by:
#             population density
#             hotel/POI density
#             commuter patterns
#             observed traffic counts
#     """
#     rng = random.Random(seed)
#     nodes = list(G.nodes)

#     if n_pairs < 0:
#         raise ValueError("n_pairs must be >= 0")
#     if min_demand > max_demand:
#         raise ValueError("min_demand must be <= max_demand")
#     if len(nodes) < 2:
#         raise ValueError("G must contain at least 2 nodes to generate OD pairs")

#     od = []
#     for _ in range(n_pairs):
#         o = rng.choice(nodes)
#         d = rng.choice(nodes)
#         while d == o:
#             d = rng.choice(nodes)

#         demand = rng.uniform(min_demand, max_demand)
#         od.append((o, d, demand))

#     return od



from __future__ import annotations

from pathlib import Path
from typing import Hashable

import random

import networkx as nx
import pandas as pd


# --- 1) Node weighting: simple + effective -------------------------------

_HIGHWAY_WEIGHT = {
    "motorway": 5.0,
    "trunk": 4.0,
    "primary": 3.0,
    "secondary": 2.0,
    "tertiary": 1.5,
    "residential": 1.0,
    "service": 0.6,
}


def _edge_importance(data: dict) -> float:
    hw = data.get("highway", "residential")
    if isinstance(hw, list) and hw:
        hw = hw[0]
    return float(_HIGHWAY_WEIGHT.get(str(hw), 1.0))


def node_weights_from_graph(G: nx.MultiDiGraph) -> dict[Hashable, float]:
    """Compute a simple 'importance' weight per node.

    Higher weights for nodes connected to higher-class roads (primary/secondary, etc.).
    This makes OD origins/destinations more likely on main corridors.
    """
    w: dict[Hashable, float] = {}
    for n in G.nodes:
        score = 1.0  # base weight so no node has 0 probability
        # look at adjacent edges (in + out)
        for _, _, _, data in G.in_edges(n, keys=True, data=True):
            score += _edge_importance(data)
        for _, _, _, data in G.out_edges(n, keys=True, data=True):
            score += _edge_importance(data)
        w[n] = score
    return w


def generate_od_weighted_total(
    G: nx.MultiDiGraph,
    n_pairs: int = 250,
    total_demand_vph: float = 8000.0,
    seed: int = 42,
    weights: dict[Hashable, float] | None = None,
) -> list[tuple[Hashable, Hashable, float]]:
    """Generate weighted OD pairs and scale demand to a fixed total.

    - Samples O and D from G.nodes using node weights (defaults to graph-derived weights).
    - Ensures O != D.
    - Draws random positive "raw" demands and rescales them so sum(demand) == total_demand_vph.
    """
    if n_pairs < 0:
        raise ValueError("n_pairs must be >= 0")
    if total_demand_vph < 0:
        raise ValueError("total_demand_vph must be >= 0")
    nodes = list(G.nodes)
    if len(nodes) < 2 and n_pairs > 0:
        raise ValueError("G must contain at least 2 nodes to generate OD pairs")

    rng = random.Random(seed)

    if weights is None:
        weights = node_weights_from_graph(G)

    # Build aligned lists for weighted sampling
    node_list = nodes
    w_list = [float(weights.get(n, 1.0)) for n in node_list]

    od_pairs: list[tuple[Hashable, Hashable]] = []
    raw_demands: list[float] = []

    for _ in range(n_pairs):
        o = rng.choices(node_list, weights=w_list, k=1)[0]
        d = rng.choices(node_list, weights=w_list, k=1)[0]
        while d == o:
            d = rng.choices(node_list, weights=w_list, k=1)[0]

        od_pairs.append((o, d))
        raw_demands.append(rng.random() + 1e-6)  # strictly > 0

    raw_sum = sum(raw_demands) if raw_demands else 1.0
    scale = (total_demand_vph / raw_sum) if raw_sum > 0 else 0.0

    od: list[tuple[Hashable, Hashable, float]] = []
    for (o, d), r in zip(od_pairs, raw_demands, strict=True):
        od.append((o, d, float(r * scale)))

    return od


def save_od_parquet(od: list[tuple[Hashable, Hashable, float]], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(od, columns=["origin", "destination", "demand"])
    # Keep numeric IDs for computation; for UI you can cast to string later.
    df.to_parquet(path, index=False)


def load_od_parquet(path: str | Path) -> list[tuple[int, int, float]]:
    """Load OD parquet and coerce ids to Python ints.

    This matters because pandas/arrow may return numpy/int64 values whose hashing can
    differ from Python ints. Converting to `int(...)` ensures membership checks like
    `o in G` work reliably.
    """
    df = pd.read_parquet(path)
    od: list[tuple[int, int, float]] = []
    for o, d, dem in df[["origin", "destination", "demand"]].itertuples(index=False, name=None):
        od.append((int(o), int(d), float(dem)))
    return od
