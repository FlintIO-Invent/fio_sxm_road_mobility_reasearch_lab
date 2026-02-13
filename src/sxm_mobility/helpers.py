import json
import pandas as pd

def clean_osm_value(x) -> str | None:
    """Turn messy OSMnx-exported values into a readable string (handles JSON/list-like strings)."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip()
    if s in ("", "nan", "None"):
        return None

    # If it looks like JSON, try to parse
    try:
        obj = json.loads(s)
        if isinstance(obj, list) and obj:
            return str(obj[0])
        if isinstance(obj, dict) and obj:
            return str(next(iter(obj.values())))
        return str(obj)
    except Exception:
        pass

    # If it looks like a python list string, keep it simple
    if s.startswith("[") and s.endswith("]"):
        return s.strip("[]").strip("'").strip('"')

    return s


def build_node_labels(nodes_df: pd.DataFrame, edges_df: pd.DataFrame) -> dict:
    """
    Create human-friendly junction labels using:
    - top road names touching each node
    - fallback to lat/lon if no names
    """
    # nodes_df expected columns: osmid (or index), x (lon), y (lat)
    if "osmid" in nodes_df.columns:
        nodes = nodes_df.set_index("osmid")
    else:
        # if already indexed by osmid
        nodes = nodes_df.set_index(nodes_df.columns[0]) if nodes_df.index.name is None else nodes_df

    # collect road names per node from edges
    e = edges_df.copy()
    if "name" in e.columns:
        e["road_name_clean"] = e["name"].map(clean_osm_value)
    else:
        e["road_name_clean"] = None

    # build adjacency road-name list for each node
    from_u = e[["u", "road_name_clean"]].rename(columns={"u": "node"})
    from_v = e[["v", "road_name_clean"]].rename(columns={"v": "node"})
    adj = pd.concat([from_u, from_v], ignore_index=True)
    adj = adj.dropna(subset=["road_name_clean"])

    # for each node, pick up to 2 most common road names
    counts = (
        adj.groupby(["node", "road_name_clean"])
        .size()
        .reset_index(name="n")
        .sort_values(["node", "n"], ascending=[True, False])
    )

    topnames = counts.groupby("node")["road_name_clean"].apply(lambda s: list(s.head(2))).to_dict()

    labels = {}
    for node_id, row in nodes.iterrows():
        lat = float(row["y"]) if "y" in row else None
        lon = float(row["x"]) if "x" in row else None

        roads = topnames.get(node_id, [])
        if roads:
            if len(roads) == 1:
                labels[node_id] = f"{roads[0]} junction"
            else:
                labels[node_id] = f"{roads[0]} × {roads[1]}"
        elif lat is not None and lon is not None:
            labels[node_id] = f"Near ({lat:.5f}, {lon:.5f})"
        else:
            labels[node_id] = "Junction"

    return labels