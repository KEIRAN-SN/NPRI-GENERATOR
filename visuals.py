import pydeck as pdk
import numpy as np
import streamlit as st

def build_heat_layer(w_df, radius, intensity):
    """
    Creates a Pydeck HeatmapLayer supporting bilingual substance columns.
    """
    # Dynamically identify the substance column based on session state
    lang = st.session_state.get("lang", "EN")
    sub_col = f"Substance_{lang}"

    # Ensure we include the bilingual substance column in the selection
    base = (
        w_df[["NPRI_ID", "Facility", "Lat", "Lon", "Quantity", sub_col]]
        .dropna(subset=["Lat", "Lon"])
        .copy()
    )
    if base.empty:
        return None, base

    # Grouping must include the bilingual column to prevent KeyErrors in the dashboard
    g = base.groupby(["NPRI_ID", "Facility", "Lat", "Lon", sub_col], as_index=False).agg(
        Quantity=("Quantity", "sum")
    )
    
    # Natural log for better heat visualization of varying emission scales
    g["Weight"] = np.log1p(g["Quantity"])

    layer = pdk.Layer(
        "HeatmapLayer",
        data=g,
        get_position="[Lon, Lat]",
        get_weight="Weight",
        radius_pixels=radius,
        intensity=intensity,
        threshold=0.05,
    )
    return layer, g