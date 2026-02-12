from __future__ import annotations

from pathlib import Path
from loguru import logger

from sxm_mobility.config import settings
from sxm_mobility.network.build_graph import build_graph
from sxm_mobility.io.osm_ingest import (
    save_gpickle,
    save_graphml,
    export_nodes_edges_parquet,
)

def main() -> None:
    """Build graph artifacts and export tables for downstream use.

    Creates a `{data_dir}/processed` output directory, builds a graph for
    `settings.place_query` and `settings.network_type`, then writes:

    - `graph.gpickle` (engine artifact)
    - `graph.graphml` (shareable artifact)
    - `nodes.parquet` and `edges.parquet` (tabular exports)

    :raises OSError: If the output directory cannot be created.
    :raises Exception: If graph building or any export/save step fails.
    :return: None
    :rtype: None
    """
    out_dir: Path = Path(settings.data_dir) / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Downloading + building graph for: {settings.place_query}")
    G: "nx.MultiDiGraph" = build_graph(settings.place_query, settings.network_type)

    gpickle_path: Path = out_dir / "base/graph.gpickle"
    save_gpickle(G, gpickle_path)
    logger.info(f"Saved: {gpickle_path}")

    graphml_path: Path = out_dir / "base/graph.graphml"
    save_graphml(G, graphml_path)
    logger.info(f"Saved: {graphml_path}")

    nodes_path: Path = out_dir / "base/nodes.parquet"
    edges_path: Path = out_dir / "base/edges.parquet"
    export_nodes_edges_parquet(G, nodes_path, edges_path)
    logger.info(f"Saved: {nodes_path}")
    logger.info(f"Saved: {edges_path}")


if __name__ == "__main__":
    main()

