from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd


def download_osm_graph(place_query: str, network_type: str = "drive") -> nx.MultiDiGraph:
    """Download a road network graph using OSMnx.

    :param place_query: A place name/query accepted by OSMnx (e.g., "Amsterdam, Netherlands").
    :type place_query: str
    :param network_type: The OSMnx network type (e.g., "drive", "walk", "bike"), defaults to "drive".
    :type network_type: str, optional
    :raises ImportError: If `osmnx` is not installed (install geo extras).
    :return: A directed multigraph of the requested network.
    :rtype: nx.MultiDiGraph
    """
    try:
        import osmnx as ox
    except ImportError as e:
        raise ImportError("Install geo extras: `uv sync --extra geo`") from e

    ox.settings.use_cache = True
    ox.settings.log_console = False

    G = ox.graph_from_place(place_query, network_type=network_type, simplify=True)
    return nx.MultiDiGraph(G)


def _graphml_safe_value(v: Any) -> Any:
    """Convert common non-GraphML types to GraphML-safe scalar values.

    GraphML does not support nested types (lists/dicts) or geometry objects.
    This helper converts such values to strings (JSON or WKT) where possible.

    :param v: An attribute value to sanitize.
    :type v: Any
    :return: A GraphML-safe scalar value (str/int/float/bool) or string fallback.
    :rtype: Any
    """
    if v is None:
        return ""

    if isinstance(v, (str, int, float, bool)):
        return v

    # Shapely geometry -> WKT string (LineString/Point/etc.)
    wkt = getattr(v, "wkt", None)
    if wkt is not None:
        return wkt

    # list/tuple/set/dict -> JSON string
    if isinstance(v, (list, tuple, set)):
        return json.dumps(list(v), ensure_ascii=False)

    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)

    # fallback
    return str(v)


def make_graph_graphml_safe(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Return a copy of `G` where all attributes are GraphML-safe.

    :param G: Input graph with potentially complex attribute types.
    :type G: nx.MultiDiGraph
    :return: A copied graph with sanitized graph/node/edge attributes.
    :rtype: nx.MultiDiGraph
    """
    H = G.copy()

    # Graph-level attrs
    H.graph = {k: _graphml_safe_value(v) for k, v in H.graph.items()}

    # Node attrs
    for _, data in H.nodes(data=True):
        for k, v in list(data.items()):
            data[k] = _graphml_safe_value(v)

    # Edge attrs (MultiDiGraph)
    for _, _, _, data in H.edges(keys=True, data=True):
        for k, v in list(data.items()):
            data[k] = _graphml_safe_value(v)

    return H


def save_graphml(G: nx.MultiDiGraph, path: Path) -> None:
    """Save a GraphML artifact for sharing (Gephi/yEd/etc.).

    GraphML does not support lists/dicts/geometry objects, so attributes are
    sanitized to GraphML-safe values before writing.

    :param G: Graph to write.
    :type G: nx.MultiDiGraph
    :param path: Destination file path.
    :type path: Path
    :raises OSError: If the destination directory cannot be created or file cannot be written.
    :return: None
    :rtype: None
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    H = make_graph_graphml_safe(G)
    nx.write_graphml(H, path)


def load_graphml(path: Path) -> nx.MultiDiGraph:
    """Load a GraphML artifact into NetworkX.

    Warning: GraphML loads node ids and attribute values as strings.
    Prefer gpickle for internal computation.

    :param path: Path to the GraphML file.
    :type path: Path
    :raises OSError: If the file cannot be read.
    :return: The loaded graph.
    :rtype: nx.MultiDiGraph
    """
    return nx.read_graphml(path)  # type: ignore[return-value]


def save_gpickle(G: nx.Graph, path: str | Path) -> None:
    """Save a graph using Python pickle (fast, full-fidelity engine artifact).

    :param G: Graph to serialize.
    :type G: nx.Graph
    :param path: Destination file path.
    :type path: str | Path
    :raises OSError: If the destination directory cannot be created or file cannot be written.
    :return: None
    :rtype: None
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_gpickle(path: str | Path) -> nx.Graph:
    """Load a graph saved by :func:`save_gpickle`.

    :param path: Path to the gpickle file.
    :type path: str | Path
    :raises OSError: If the file cannot be read.
    :raises pickle.UnpicklingError: If the file is not a valid pickle.
    :return: The deserialized graph.
    :rtype: nx.Graph
    """
    path = Path(path)
    with path.open("rb") as f:
        return pickle.load(f)


def graph_basic_stats(G: nx.MultiDiGraph) -> dict[str, Any]:
    """Compute basic summary stats for a graph.

    :param G: Graph to summarize.
    :type G: nx.MultiDiGraph
    :return: Basic stats including node/edge counts and directedness.
    :rtype: dict[str, Any]
    """
    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "is_directed": G.is_directed(),
    }


def _to_json_string(v: Any) -> str:
    """Convert values into stable strings suitable for Parquet/Arrow.

    - Scalars become strings.
    - Lists/dicts/sets/tuples become JSON strings.
    - Shapely geometries become WKT (if `.wkt` is present).

    :param v: Value to normalize.
    :type v: Any
    :return: A string representation safe for tabular serialization.
    :rtype: str
    """
    if v is None:
        return ""
    # keep common scalars
    if isinstance(v, (str, int, float, bool)):
        return str(v)
    # lists/dicts/sets -> JSON
    if isinstance(v, (list, tuple, set, dict)):
        return json.dumps(v, ensure_ascii=False)
    # shapely -> WKT if present
    wkt = getattr(v, "wkt", None)
    if wkt is not None:
        return wkt
    return str(v)


def export_nodes_edges_parquet(
    G: nx.MultiDiGraph,
    nodes_path: str | Path,
    edges_path: str | Path,
) -> None:
    """Export graph nodes/edges to Parquet for dashboards or database ingestion.

    Uses OSMnx to convert the graph to GeoDataFrames, then:
    - Adds `geometry_wkt` columns for portability
    - Drops shapely geometry columns
    - Normalizes object-like columns to stable strings (JSON/WKT)
    - Preserves join keys (`u`, `v`, `key`, `node_id`) as numeric types when possible

    :param G: Input OSMnx/NetworkX graph.
    :type G: nx.MultiDiGraph
    :param nodes_path: Output path for the nodes parquet file.
    :type nodes_path: str | Path
    :param edges_path: Output path for the edges parquet file.
    :type edges_path: str | Path
    :raises ImportError: If `osmnx` is not installed (install geo extras).
    :raises OSError: If output directories cannot be created or files cannot be written.
    :return: None
    :rtype: None
    """
    try:
        import osmnx as ox
    except ImportError as e:
        raise ImportError("Install geo extras: `uv sync --extra geo`") from e

    nodes_path = Path(nodes_path)
    edges_path = Path(edges_path)
    nodes_path.parent.mkdir(parents=True, exist_ok=True)
    edges_path.parent.mkdir(parents=True, exist_ok=True)

    gdf_nodes, gdf_edges = ox.graph_to_gdfs(G, nodes=True, edges=True, fill_edge_geometry=True)

    # geometry as portable WKT
    gdf_nodes["geometry_wkt"] = gdf_nodes.geometry.to_wkt()
    gdf_edges["geometry_wkt"] = gdf_edges.geometry.to_wkt()

    # drop shapely geometry columns
    gdf_nodes = gdf_nodes.drop(columns=["geometry"])
    gdf_edges = gdf_edges.drop(columns=["geometry"])

    # bring index into columns (nodes: node id; edges: u,v,key)
    nodes_df = gdf_nodes.reset_index()
    edges_df = gdf_edges.reset_index()

    # Keep join keys numeric
    if "osmid" in nodes_df.columns:
        nodes_df["node_id"] = pd.to_numeric(nodes_df["osmid"], errors="coerce").astype("Int64")

    for c in ["u", "v", "key"]:
        if c in edges_df.columns:
            edges_df[c] = pd.to_numeric(edges_df[c], errors="coerce").astype("Int64")

    protected = {"u", "v", "key", "node_id"}  # do NOT stringify these

    # Normalize: first handle known troublemakers explicitly
    for c in [
        "highway",
        "name",
        "maxspeed",
        "lanes",
        "access",
        "bridge",
        "junction",
        "ref",
        "service",
        "tunnel",
        "osmid",
    ]:
        if c in edges_df.columns and c not in protected:
            edges_df[c] = edges_df[c].map(_to_json_string)

    # Now normalize all remaining object/string columns except protected
    for df in (nodes_df, edges_df):
        cols = df.select_dtypes(include=["object", "string"]).columns
        for c in cols:
            if c not in protected:
                df[c] = df[c].map(_to_json_string)

    # Final safety: if any column still contains list/dict/etc, force convert it
    def has_complex(series: pd.Series) -> bool:
        return series.map(lambda x: isinstance(x, (list, dict, tuple, set))).any()

    for df in (nodes_df, edges_df):
        for c in df.columns:
            if has_complex(df[c]):
                df[c] = df[c].map(_to_json_string)

    # drop rows missing join keys (rare but safe)
    edges_df = edges_df.dropna(subset=[c for c in ["u", "v", "key"] if c in edges_df.columns])

    nodes_df.to_parquet(nodes_path, index=False)
    edges_df.to_parquet(edges_path, index=False)
