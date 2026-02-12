from __future__ import annotations
import networkx as nx
from .attributes import add_freeflow_time_and_capacity


def build_graph(place_query: str, network_type: str = "drive") -> nx.MultiDiGraph:
    """
    Build and return an OSM road network graph (no saving here).
    Saving/exporting is handled by scripts/build_graph.py.
    """
    try:
        import osmnx as ox
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "osmnx is required to build the graph. Install with: uv sync --extra geo"
        ) from e

    G = ox.graph_from_place(place_query, network_type=network_type, simplify=True)
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)
    G = add_freeflow_time_and_capacity(G)

    # Optional (recommended): keep largest strongly connected component for drive networks
    # (prevents weird disconnected islands from breaking assignment)
    try:
        G = ox.truncate.largest_component(G, strongly=True)
    except Exception:
        pass

    return G