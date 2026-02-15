from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import math
import networkx as nx
import pandas as pd


# ----------------------------
# Base Scenario types
# ----------------------------
@dataclass(frozen=True)
class Scenario:
    name: str
    description: str

    def apply(self, G: nx.MultiDiGraph) -> nx.MultiDiGraph:  # pragma: no cover
        raise NotImplementedError


# ----------------------------
# Connector Spec (DEFINE ONCE)
# ----------------------------
@dataclass(frozen=True)
class ConnectorSpec:
    a: int
    b: int
    length_m: float
    speed_kph: float = 40.0
    lanes: float = 1.0
    oneway: bool = False
    name: str = "Proposed connector / bypass"


# ----------------------------
# Example scenarios
# ----------------------------
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
        speed_mps = max(1.0, self.speed_kph * 1000.0 / 3600.0)
        t0 = float(self.length_m) / speed_mps
        H.add_edge(
            self.u,
            self.v,
            length=float(self.length_m),
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


# ----------------------------
# Geometry helpers
# ----------------------------
EARTH_R_M = 6_371_000.0


def _haversine_m(*args) -> float:
    """
    Distance in meters using haversine.
    Supports:
      _haversine_m(lon1, lat1, lon2, lat2)
      _haversine_m((lon1, lat1), (lon2, lat2))
    """
    if len(args) == 2:
        (lon1, lat1), (lon2, lat2) = args
    elif len(args) == 4:
        lon1, lat1, lon2, lat2 = args
    else:
        raise TypeError("_haversine_m expects 2 tuples or 4 floats")

    lon1 = math.radians(float(lon1))
    lat1 = math.radians(float(lat1))
    lon2 = math.radians(float(lon2))
    lat2 = math.radians(float(lat2))

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    c = 2.0 * math.asin(math.sqrt(a))
    return EARTH_R_M * c


# Optional public alias (so you can call haversine_m anywhere)
haversine_m = _haversine_m


# ----------------------------
# Path helpers
# ----------------------------
def _best_edge_attr(G: nx.MultiDiGraph, u: Any, v: Any, attr: str, default: float) -> float:
    """Pick the best (minimum) attr among parallel edges u->v."""
    try:
        data_dict = G[u][v]
    except Exception:
        return default
    best = None
    for k in data_dict:
        val = data_dict[k].get(attr, default)
        try:
            valf = float(val)
        except Exception:
            valf = default
        best = valf if best is None else min(best, valf)
    return default if best is None else float(best)


def _subpath_time_seconds(G: nx.MultiDiGraph, path_nodes: list[Any]) -> float:
    """Sum of best edge travel times along a node-path."""
    tt = 0.0
    for uu, vv in zip(path_nodes[:-1], path_nodes[1:]):
        tt += _best_edge_attr(G, uu, vv, "time", 1.0)
    return tt


def _path_has_edge(path_nodes: list[Any], u: Any, v: Any) -> list[int]:
    """Return all indices i where path[i]=u and path[i+1]=v."""
    idxs = []
    for i in range(len(path_nodes) - 1):
        if path_nodes[i] == u and path_nodes[i + 1] == v:
            idxs.append(i)
    return idxs


# ----------------------------
# Node indexing helpers
# ----------------------------
def _nodes_indexed(nodes_df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """
    Return (df_indexed, index_is_str).
    Ensures we can access rows by either int node ids or str node ids.
    """
    df = nodes_df.copy()

    if "osmid" not in df.columns:
        raise ValueError("nodes.parquet must contain 'osmid'")
    if "x" not in df.columns or "y" not in df.columns:
        raise ValueError("nodes.parquet must contain x (lon) and y (lat)")

    # Try numeric osmid first
    osmid_num = pd.to_numeric(df["osmid"], errors="coerce")
    if osmid_num.notna().all():
        df["osmid"] = osmid_num.astype(int)
        df = df.set_index("osmid", drop=False)
        return df, False

    # Fallback: string index
    df["osmid"] = df["osmid"].astype(str)
    df = df.set_index("osmid", drop=False)
    return df, True


# ----------------------------
# 1) Deterministic “near-edge” connector proposal
# ----------------------------
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
    nodes_df, idx_is_str = _nodes_indexed(nodes_df)

    def _idx(n: Any) -> Any:
        return str(n) if idx_is_str else int(n)

    def k_hop_neighborhood(seed: int) -> list[int]:
        seen: set[Any] = {seed}
        frontier: set[Any] = {seed}
        for _ in range(k_hops):
            nxt: set[Any] = set()
            for n in frontier:
                try:
                    nxt.update(G.successors(n))
                    nxt.update(G.predecessors(n))
                except Exception:
                    continue
            seen |= nxt
            frontier = nxt

        out = []
        for x in seen:
            try:
                xi = int(x)
            except Exception:
                continue
            if _idx(xi) in nodes_df.index:
                out.append(xi)
        return sorted(out)

    Nu = k_hop_neighborhood(u)
    Nv = k_hop_neighborhood(v)

    candidates: list[tuple[float, int, int, float]] = []  # (score, a, b, straight_m)
    checked = 0

    for a in Nu:
        lon1, lat1 = float(nodes_df.loc[_idx(a), "x"]), float(nodes_df.loc[_idx(a), "y"])
        for b in Nv:
            if a == b:
                continue
            if G.has_edge(a, b) or G.has_edge(b, a):
                continue

            lon2, lat2 = float(nodes_df.loc[_idx(b), "x"]), float(nodes_df.loc[_idx(b), "y"])
            straight_m = _haversine_m(lon1, lat1, lon2, lat2)
            if straight_m > max_straight_m:
                continue

            try:
                detour_sec = nx.shortest_path_length(G, a, b, weight="t0")
            except Exception:
                detour_sec = 10_000.0  # disconnected => strong candidate

            score = float(detour_sec) / max(10.0, float(straight_m))
            candidates.append((score, a, b, float(straight_m)))

            checked += 1
            if checked >= max_pairs:
                break
        if checked >= max_pairs:
            break

    if not candidates:
        # fallback: directly connect u->v
        lon1, lat1 = float(nodes_df.loc[_idx(u), "x"]), float(nodes_df.loc[_idx(u), "y"])
        lon2, lat2 = float(nodes_df.loc[_idx(v), "x"]), float(nodes_df.loc[_idx(v), "y"])
        straight_m = _haversine_m(lon1, lat1, lon2, lat2)
        return ConnectorSpec(a=int(u), b=int(v), length_m=float(straight_m))

    candidates.sort(key=lambda t: (-t[0], t[1], t[2]))
    _, a, b, straight_m = candidates[0]
    return ConnectorSpec(a=int(a), b=int(b), length_m=float(straight_m))


# ----------------------------
# 2) Shortest-path relief connectors (your new method)
# ----------------------------
def shortest_path_relief_connectors(
    G_time: nx.MultiDiGraph,
    od: list[tuple[int, int, float]],
    *,
    bottleneck_u: int,
    bottleneck_v: int,
    node_lookup: dict[str, tuple[float, float]],  # osmid(str) -> (lon, lat)
    road_label: str | None = None,
    k_back: int = 2,
    k_fwd: int = 2,
    max_straight_m: float = 350.0,
    speed_kph: float = 40.0,
    lanes: float = 1.0,
    per_bottleneck_max: int = 8,
) -> list[tuple[ConnectorSpec, float]]:
    """
    Generate connector candidates that reduce shortest-path travel time for OD trips
    that currently traverse bottleneck_u -> bottleneck_v.

    Returns list of (ConnectorSpec, heuristic_score) sorted high->low.
    Score = sum_over_OD( demand * max(0, old_subpath_time - new_connector_t0) ).
    """
    speed_mps = max(1.0, float(speed_kph) * 1000.0 / 3600.0)
    agg: dict[tuple[int, int], dict[str, Any]] = {}

    for o, d, demand in od:
        if o not in G_time or d not in G_time:
            continue

        try:
            path = nx.shortest_path(G_time, o, d, weight="time")
        except Exception:
            continue

        hits = _path_has_edge(path, bottleneck_u, bottleneck_v)
        if not hits:
            continue

        for hit_i in hits:
            for back in range(1, k_back + 1):
                for fwd in range(1, k_fwd + 1):
                    ia = hit_i - back
                    ib = hit_i + 1 + fwd
                    if ia < 0 or ib >= len(path):
                        continue

                    a = int(path[ia])
                    b = int(path[ib])
                    if a == b:
                        continue

                    if G_time.has_edge(a, b) or G_time.has_edge(b, a):
                        continue

                    ka, kb = str(a), str(b)
                    if ka not in node_lookup or kb not in node_lookup:
                        continue

                    lon1, lat1 = node_lookup[ka]
                    lon2, lat2 = node_lookup[kb]
                    straight_m = _haversine_m(lon1, lat1, lon2, lat2)
                    if straight_m > max_straight_m:
                        continue

                    sub_nodes = path[ia : ib + 1]
                    old_tt = _subpath_time_seconds(G_time, sub_nodes)
                    new_t0 = float(straight_m) / speed_mps

                    saved = old_tt - new_t0
                    if saved <= 0:
                        continue

                    key = (a, b) if a <= b else (b, a)
                    rec = agg.get(key)
                    if rec is None:
                        agg[key] = {
                            "a": a,
                            "b": b,
                            "length_m": float(straight_m),
                            "score": float(demand) * float(saved),
                        }
                    else:
                        rec["score"] += float(demand) * float(saved)

    label = (road_label or "").strip() or f"{bottleneck_u}->{bottleneck_v}"

    out: list[tuple[ConnectorSpec, float]] = []
    for rec in agg.values():
        a = int(rec["a"])
        b = int(rec["b"])
        name = f"Relief connector near {label} ({a} ↔ {b})"
        spec = ConnectorSpec(
            a=a,
            b=b,
            length_m=float(rec["length_m"]),
            speed_kph=float(speed_kph),
            lanes=float(lanes),
            name=name,
        )
        out.append((spec, float(rec["score"])))

    out.sort(key=lambda x: x[1], reverse=True)
    return out[:per_bottleneck_max]


# ----------------------------
# Apply connector to graph
# ----------------------------
def apply_connector(G: nx.MultiDiGraph, spec: ConnectorSpec, *, two_way: bool = True) -> None:
    """Add proposed connector edge(s) with required attributes for assignment."""
    speed_mps = max(1.0, float(spec.speed_kph) * 1000.0 / 3600.0)
    t0 = float(spec.length_m) / speed_mps
    capacity = 900.0 * float(spec.lanes)

    attrs = {
        "length": float(spec.length_m),
        "lanes": float(spec.lanes),
        "maxspeed": float(spec.speed_kph),
        "capacity": float(capacity),
        "t0": float(t0),
        "time": float(t0),
        "flow": 0.0,
        "name": spec.name,
        "highway": "proposed_connector",
    }

    G.add_edge(int(spec.a), int(spec.b), **attrs)
    if two_way and not spec.oneway:
        G.add_edge(int(spec.b), int(spec.a), **attrs)
