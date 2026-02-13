from __future__ import annotations

from dataclasses import dataclass

import networkx as nx


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str

    def apply(self, G: nx.MultiDiGraph) -> nx.MultiDiGraph:  # pragma: no cover
        raise NotImplementedError


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


@dataclass(frozen=True)
class DemandReduction(Scenario):
    pass
    