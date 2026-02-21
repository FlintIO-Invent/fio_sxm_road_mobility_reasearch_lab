from __future__ import annotations

from pathlib import Path
from typing import Tuple
import pandas as pd
import plotly.graph_objects as go
from shapely import wkt
import streamlit as st


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
    extra_edges: pd.DataFrame | None = None,
) -> go.Figure:
    # Base network
    edges = _normalize_join_keys(edges)
    base_trace = build_network_trace(edges, max_edges=max_edges)
    center_lat, center_lon = compute_center(edges)

    fig = go.Figure()
    fig.add_trace(base_trace)

    # -------------------------
    # Bottlenecks overlay
    # -------------------------
    if bottlenecks is not None and not bottlenecks.empty:
        b = _normalize_join_keys(bottlenecks)

        merged = (
            b.merge(edges, on=["u", "v", "key"], how="left")
             .dropna(subset=["geometry_wkt"])
        )

        metric_col = "delay" if "delay" in merged.columns else None
        if metric_col:
            merged = merged.sort_values(metric_col, ascending=False)

        merged = merged.head(top_n)

        lons_all, lats_all, hover_all = [], [], []
        for _, row in merged.iterrows():
            w = row.get("geometry_wkt")
            if not isinstance(w, str) or not w:
                continue
            lons, lats = linestring_to_lonlat_lists(w)
            lons_all.extend(lons + [None])
            lats_all.extend(lats + [None])

            name = str(row.get("name", ""))
            delay = row.get("delay", None)
            vc = row.get("v_c", None)
            hover_all.append(
                f"{name}<br>delay={delay:.3f} veh-hrs" if isinstance(delay, (int, float)) else name
            )

        fig.add_trace(
            go.Scattermapbox(
                lon=lons_all,
                lat=lats_all,
                mode="lines",
                line=dict(width=3, color="red"),
                name="Top bottlenecks",
                hoverinfo="skip",  # we used concatenated trace; hover per-segment is tricky
            )
        )

    # -------------------------
    # Proposed connector overlay (robust)
    # -------------------------
    if extra_edges is not None and not extra_edges.empty:
        if "geometry_wkt" not in extra_edges.columns:
            raise ValueError("extra_edges must contain a geometry_wkt column (WKT LineString).")

        conn = extra_edges.dropna(subset=["geometry_wkt"]).copy()
        if conn.empty:
            # nothing to draw
            pass
        else:
            lons_all, lats_all, hovertext = [], [], []
            for _, row in conn.iterrows():
                w = row.get("geometry_wkt")
                if not isinstance(w, str) or not w:
                    continue
                lons, lats = linestring_to_lonlat_lists(w)
                lons_all.extend(lons + [None])
                lats_all.extend(lats + [None])

                # stakeholder hover
                scen = row.get("scenario_id", "")
                name = row.get("name", "Proposed connector")
                length_m = row.get("length", None)
                speed = row.get("maxspeed", None)
                imp_pct = row.get("improve_delay_pct", None)
                status = row.get("status", None)

                bits = [f"<b>{name}</b>"]
                if scen:
                    bits.append(f"Scenario: {scen}")
                if status:
                    bits.append(f"Impact: {status}")
                if imp_pct is not None and pd.notna(imp_pct):
                    bits.append(f"Delay change: {float(imp_pct):.1f}%")
                if length_m is not None and pd.notna(length_m):
                    bits.append(f"Length: {float(length_m):.0f} m")
                if speed is not None and pd.notna(speed):
                    bits.append(f"Speed: {speed} kph")

                hovertext.append("<br>".join(bits))

            fig.add_trace(
                go.Scattermapbox(
                    lon=lons_all,
                    lat=lats_all,
                    mode="lines",
                    line=dict(width=7, color="red"),
                    name="Proposed connector",
                    hoverinfo="text",
                    text=hovertext if hovertext else None,
                )
            )

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=13.5,
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        height=750,
        showlegend=True,
    )
    return fig


def show_column_help(df: pd.DataFrame, help_map: dict[str, str], *, title: str = "ℹ️ Column definitions") -> None:
    """
    Streamlit Option A:
    Expander right above the table, listing definitions for ALL columns in df.
    """
    if df is None or df.empty:
        return

    with st.expander(title, expanded=False):
        for col in df.columns:
            desc = help_map.get(col, "Definition not added yet for this column.")
            st.markdown(f"**{col}** : {desc}")
