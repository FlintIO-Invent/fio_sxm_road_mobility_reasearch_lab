from __future__ import annotations
from dataclasses import dataclass
import networkx as nx
import math
import pandas as pd


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str

    def apply(self, G: nx.MultiDiGraph) -> nx.MultiDiGraph:  # pragma: no cover
        raise NotImplementedError


@dataclass(frozen=True)
class ConnectorSpec:
    a: int
    b: int
    length_m: float
    speed_kph: float = 40.0
    lanes: float = 1.0
    oneway: bool = False
    name: str = "Proposed connector / bypass"

@dataclass(frozen=True)
class IncreaseCapacity(Scenario):
    u: int
    v: int
    key: int
    pct: float = 0.25

    def apply(self, G: nx.MultiDiGraph) -> nx.MultiDiGraph:
        H = G.copy()
        if H.has_edge(self.u, self.v, self.key):
            cap = float(H[self.u][self.v][self.key].get("capacity", 0.0))
            H[self.u][self.v][self.key]["capacity"] = cap * (1.0 + self.pct)
        return H


@dataclass(frozen=True)
class AddConnector(Scenario):
    u: int
    v: int
    length_m: float
    speed_kph: float = 40.0
    capacity_vph: float = 900.0

    def apply(self, G: nx.MultiDiGraph) -> nx.MultiDiGraph:
        H = G.copy()
        speed_mps = self.speed_kph * 1000.0 / 3600.0
        t0 = self.length_m / speed_mps
        H.add_edge(
            self.u,
            self.v,
            length=self.length_m,
            t0=float(t0),
            time=float(t0),
            capacity=float(self.capacity_vph),
            flow=0.0,
            scenario_edge=True,
        )
        return H


@dataclass(frozen=True)
class Closure(Scenario):
    u: int
    v: int
    key: int

    def apply(self, G: nx.MultiDiGraph) -> nx.MultiDiGraph:
        H = G.copy()
        if H.has_edge(self.u, self.v, self.key):
            H.remove_edge(self.u, self.v, self.key)
        return H


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _nodes_indexed(nodes_df: pd.DataFrame) -> pd.DataFrame:
    # Expect OSMnx-style: osmid, x (lon), y (lat)
    df = nodes_df.copy()
    if "osmid" in df.columns:
        df = df.set_index("osmid", drop=False)
    if "x" not in df.columns or "y" not in df.columns:
        raise ValueError("nodes.parquet must contain x (lon) and y (lat)")
    return df


def propose_connector_near_edge(
    G: nx.MultiDiGraph,
    nodes_df: pd.DataFrame,
    u: int,
    v: int,
    k_hops: int = 3,
    max_straight_m: float = 300.0,
    max_pairs: int = 800,
) -> ConnectorSpec:
    """
    Deterministic connector proposal:
    - take k-hop neighborhood around u and v
    - candidate pairs are (a in Nu, b in Nv) not already connected
    - keep only geographically close pairs (<= max_straight_m)
    - prefer those with large network detour time (t0-weighted)
    """
    nodes_df = _nodes_indexed(nodes_df)

    def k_hop_neighborhood(seed: int) -> list[int]:
        seen = {seed}
        frontier = {seed}
        for _ in range(k_hops):
            nxt = set()
            for n in frontier:
                nxt.update(G.successors(n))
                nxt.update(G.predecessors(n))
            seen |= nxt
            frontier = nxt
        # deterministic order
        return sorted(int(x) for x in seen if x in nodes_df.index)

    Nu = k_hop_neighborhood(u)
    Nv = k_hop_neighborhood(v)

    candidates: list[tuple[float, int, int, float]] = []  # (score, a, b, straight_m)
    checked = 0

    for a in Nu:
        lat1, lon1 = float(nodes_df.loc[a, "y"]), float(nodes_df.loc[a, "x"])
        for b in Nv:
            if a == b:
                continue
            if G.has_edge(a, b) or G.has_edge(b, a):
                continue

            lat2, lon2 = float(nodes_df.loc[b, "y"]), float(nodes_df.loc[b, "x"])
            straight_m = _haversine_m(lat1, lon1, lat2, lon2)
            if straight_m > max_straight_m:
                continue

            try:
                detour_sec = nx.shortest_path_length(G, a, b, weight="t0")
            except Exception:
                detour_sec = 10_000.0  # disconnected => strong candidate

            score = float(detour_sec) / max(10.0, float(straight_m))
            candidates.append((score, a, b, straight_m))

            checked += 1
            if checked >= max_pairs:
                break
        if checked >= max_pairs:
            break

    if not candidates:
        # fallback: directly connect the bottleneck endpoints
        lat1, lon1 = float(nodes_df.loc[u, "y"]), float(nodes_df.loc[u, "x"])
        lat2, lon2 = float(nodes_df.loc[v, "y"]), float(nodes_df.loc[v, "x"])
        straight_m = _haversine_m(lat1, lon1, lat2, lon2)
        return ConnectorSpec(a=int(u), b=int(v), length_m=float(straight_m))

    candidates.sort(key=lambda t: (-t[0], t[1], t[2]))
    _, a, b, straight_m = candidates[0]
    return ConnectorSpec(a=int(a), b=int(b), length_m=float(straight_m))


def apply_connector(G: nx.MultiDiGraph, spec: ConnectorSpec) -> None:
    """
    Adds connector edge(s) with assignment-ready attributes: t0, time, capacity, flow.
    We set key=0 for stable joins (safe because we only add if edge doesn't exist).
    """
    speed_mps = spec.speed_kph * 1000.0 / 3600.0
    t0 = spec.length_m / max(1.0, speed_mps)
    capacity = 900.0 * float(spec.lanes)

    attrs = {
        "length": float(spec.length_m),
        "lanes": float(spec.lanes),
        "maxspeed": float(spec.speed_kph),
        "capacity": float(capacity),
        "t0": float(t0),
        "time": float(t0),
        "flow": 0.0,
        "highway": "proposed_connector",
        "name": spec.name,
        "oneway": bool(spec.oneway),
        "is_scenario_edge": True,
    }

    G.add_edge(spec.a, spec.b, key=0, **attrs)
    if not spec.oneway:
        G.add_edge(spec.b, spec.a, key=0, **attrs)
