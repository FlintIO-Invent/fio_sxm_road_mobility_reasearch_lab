from __future__ import annotations

import networkx as nx


def largest_weakly_connected_component(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Keep only the largest weakly connected component."""
    if G.number_of_nodes() == 0:
        return G

    comp = max(nx.weakly_connected_components(G), key=len)
    return G.subgraph(comp).copy()
