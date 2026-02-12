import networkx as nx

from sxm_mobility.network.attributes import add_freeflow_time_and_capacity
from sxm_mobility.demand.od_generation import generate_od_weighted_total
from sxm_mobility.assignment.msa import msa_traffic_assignment
from sxm_mobility.assignment.metrics import total_delay, total_system_travel_time


def _toy_graph() -> nx.MultiDiGraph:
    """Small connected graph with minimal OSM-like attributes."""
    G = nx.MultiDiGraph()
    # triangle with a short "main" edge
    G.add_edge(1, 2, key=0, length=500.0, maxspeed="50", highway="primary", lanes="2")
    G.add_edge(2, 3, key=0, length=800.0, maxspeed="40", highway="secondary", lanes="1")
    G.add_edge(1, 3, key=0, length=1200.0, maxspeed="30", highway="residential", lanes="1")
    return G


def test_edge_attributes_are_initialized():
    G = add_freeflow_time_and_capacity(_toy_graph())
    for *_, d in G.edges(keys=True, data=True):
        assert d["t0"] > 0
        assert d["capacity"] > 0
        assert d["time"] > 0
        assert d["time"] >= d["t0"]


def test_od_generation_hits_total_demand():
    G = add_freeflow_time_and_capacity(_toy_graph())
    od = generate_od_weighted_total(G, n_pairs=10, total_demand_vph=1000.0, seed=1)
    total = sum(d for _, _, d in od)
    assert abs(total - 1000.0) < 1e-6


def test_assignment_produces_positive_flows_and_nonnegative_delay():
    G = add_freeflow_time_and_capacity(_toy_graph())
    od = [(1, 3, 2000.0)]  # deliberately over capacity
    G = msa_traffic_assignment(G, od=od, iters=5)
    flows = [float(d.get("flow", 0.0)) for *_, d in G.edges(keys=True, data=True)]
    assert max(flows) > 0
    assert total_delay(G) >= 0
    assert total_system_travel_time(G) > 0
