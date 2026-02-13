from __future__ import annotations

from pathlib import Path
from typing import Tuple
import pandas as pd
import plotly.graph_objects as go
from shapely import wkt


def linestring_to_lonlat_lists(wkt_str: str) -> tuple[list[float], list[float]]:
    geom = wkt.loads(wkt_str)
    xs, ys = geom.xy  # xs=lon, ys=lat
    return list(xs), list(ys)


def build_network_trace(edges_df: pd.DataFrame, max_edges: int | None = None) -> go.Scattermapbox:
    if max_edges is not None:
        edges_df = edges_df.head(max_edges)

    lons_all, lats_all = [], []
    for w in edges_df["geometry_wkt"].dropna():
        lons, lats = linestring_to_lonlat_lists(w)
        lons_all.extend(lons + [None])
        lats_all.extend(lats + [None])

    return go.Scattermapbox(
        lon=lons_all,
        lat=lats_all,
        mode="lines",
        line=dict(width=1),
        hoverinfo="skip",
        name="Road network",        
    )


def compute_center(edges_df: pd.DataFrame) -> tuple[float, float]:
    sample = edges_df["geometry_wkt"].dropna().head(200)
    lons_sum, lats_sum, n = 0.0, 0.0, 0
    for w in sample:
        xs, ys = linestring_to_lonlat_lists(w)
        lons_sum += sum(xs)
        lats_sum += sum(ys)
        n += len(xs)

    if n == 0:
        return 18.0, -63.1
    return (lats_sum / n), (lons_sum / n)


def _normalize_join_keys(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in ["u", "v", "key"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").astype("Int64")
    return out


def make_network_figure(
    edges: pd.DataFrame,
    max_edges: int,
    bottlenecks: pd.DataFrame | None = None,
    top_n: int = 50,
) -> go.Figure:
    edges = _normalize_join_keys(edges)

    base_trace = build_network_trace(edges, max_edges=max_edges)
    center_lat, center_lon = compute_center(edges)

    fig = go.Figure()
    fig.add_trace(base_trace)

    if bottlenecks is not None and len(bottlenecks) > 0:
        b = _normalize_join_keys(bottlenecks)
        merged = b.merge(edges, on=["u", "v", "key"], how="left").dropna(subset=["geometry_wkt"])

        metric_col = "delay" if "delay" in merged.columns else None
        if metric_col:
            merged = merged.sort_values(metric_col, ascending=False)

        merged = merged.head(top_n)

        lons_all, lats_all = [], []
        for w in merged["geometry_wkt"]:
            lons, lats = linestring_to_lonlat_lists(w)
            lons_all.extend(lons + [None])
            lats_all.extend(lats + [None])

        hovertext = None
        if "name" in merged.columns:
            hovertext = merged["name"].astype(str).tolist()

        fig.add_trace(
            go.Scattermapbox(
                lon=lons_all,
                lat=lats_all,
                mode="lines",
                line=dict(width=3, color="red"),
                name="Top bottlenecks",
                hoverinfo="text" if hovertext else "skip",
                text=hovertext,
            )
            
        )

    fig.update_layout(
        #  The built-in plotly.js styles objects are:
        mapbox=dict(style="open-street-map", center=dict(lat=center_lat, lon=center_lon), zoom=12),
        margin=dict(l=0, r=0, t=40, b=0),
        height=750,
        showlegend=True,
    )

    
    return fig
