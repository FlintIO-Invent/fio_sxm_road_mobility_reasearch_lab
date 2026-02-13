from __future__ import annotations
from pathlib import Path
from typing import Hashable, Any
import random
import networkx as nx
import pandas as pd

_HIGHWAY_WEIGHT = {
    "motorway": 5.0,
    "trunk": 4.0,
    "primary": 3.0,
    "secondary": 2.0,
    "tertiary": 1.5,
    "residential": 1.0,
    "service": 0.6,
}

def scale_od(od: list[tuple[Any, Any, float]], factor: float) -> list[tuple[Any, Any, float]]:
    """Scale OD demands by a constant factor (e.g. 0.85 for 15% reduction)."""
    if factor < 0:
        raise ValueError("factor must be >= 0")
    return [(o, d, float(q) * factor) for o, d, q in od]


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
