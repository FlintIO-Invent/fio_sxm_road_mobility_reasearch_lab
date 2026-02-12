import networkx as nx

from sxm_mobility.assignment.metrics import total_delay


def test_total_delay_non_negative_for_reasonable_inputs():
    G = nx.MultiDiGraph()
    G.add_edge("a", "b", t0=10.0, time=12.0, flow=100.0)
    assert total_delay(G) >= 0.0
