import streamlit as st
import os
import pandas as pd
import json
import time
from data_engine import process_files, filter_by_radius, normalize_quantity
from ui_components import workspace_manager_ui, kiosk_config_ui
from dashboard import render_main_dashboard

# 1. PAGE CONFIG & STATE INITIALIZATION
st.set_page_config(layout="wide", page_title="NPRI Data Explorer")

# Initialize Session States
if "active_selections" not in st.session_state:
    st.session_state.active_selections = []
if "kiosk_locs" not in st.session_state: 
    st.session_state.kiosk_locs = {}
if "kiosk_pols" not in st.session_state: 
    st.session_state.kiosk_pols = {}
if "cascading_df" not in st.session_state:
    st.session_state.cascading_df = None
if "lang" not in st.session_state:
    st.session_state.lang = "EN"
if "raw_df_loaded" not in st.session_state:
    st.session_state.raw_df_loaded = None

# --- 2. GLOBAL SIDEBAR (DATA LOADING & LANGUAGE) ---
with st.sidebar:
    st.title("🌲 NPRI Explorer" if st.session_state.lang == "EN" else "🌲 Explorateur INRP")
    
    folder_path = st.text_input(
        "Data Path:" if st.session_state.lang == "EN" else "Chemin des données :", 
        value="./data"
    )
    
    # Language Toggle using Radio
    new_lang = st.radio("Language / Langue", ["EN", "FR"], 
                        index=0 if st.session_state.lang == "EN" else 1, 
                        horizontal=True)
    if new_lang != st.session_state.lang:
        st.session_state.lang = new_lang
        st.rerun()
    
    # Define Dynamic UI Labels globally for the fragment to access
    lang = st.session_state.lang
    L_SUB = "Substance_EN" if lang == "EN" else "Substance_FR"
    T_SYNC = "🔄 Sync All Filters" if lang == "EN" else "🔄 Synchroniser les filtres"
    T_INC = "➕ Include" if lang == "EN" else "➕ Inclure"
    T_EXC = "➖ Exclude" if lang == "EN" else "➖ Exclure"

# --- 3. DATA LOADING ---
if st.session_state.raw_df_loaded is None:
    if os.path.exists(folder_path):
        with st.status("📥 Syncing Database...") as status:
            df, message = process_files(folder_path)
            if df is not None:
                # Ensure every row has a unique ID for workspace masking
                df["_uid"] = df.index.astype(str)
                st.session_state.raw_df_loaded = df
                status.update(label=f"✅ {message}", state="complete")
            else:
                st.error(message)
                st.stop()
    else:
        st.info("📂 Please provide a valid data path.")
        st.stop()

raw_df = st.session_state.raw_df_loaded

# --- 4. SELECTION BUILDER FRAGMENT ---
@st.fragment
def selection_sidebar_fragment(raw_df):
    # Re-declare constants inside fragment scope
    lang = st.session_state.lang
    l_sub_col = "Substance_EN" if lang == "EN" else "Substance_FR"
    
    subs_list = sorted(raw_df[l_sub_col].dropna().unique())
    min_y, max_y = int(raw_df["Year"].min()), int(raw_df["Year"].max())

    t_sb = "🎯 Selection Builder" if lang == "EN" else "🎯 Constructeur de sélection"
    t_mining = "Mining/Smelting Only" if lang == "EN" else "Mines/Fonderies uniquement"
    t_city = "City Focus" if lang == "EN" else "Ville focus"
    t_radius = "Radius (km)" if lang == "EN" else "Rayon (km)"
    t_comp = "Company" if lang == "EN" else "Entreprise"
    t_fac = "Facility" if lang == "EN" else "Installation"
    t_poll = "Pollutant Focus" if lang == "EN" else "Substance d'intérêt"
    t_years = "Years Selection" if lang == "EN" else "Sélection des années"
    all_label = "All" if lang == "EN" else "Tous"

    with st.expander(t_sb, expanded=True):
        # Use cascading_df if filtered, otherwise use raw_df
        display_df = st.session_state.cascading_df if st.session_state.cascading_df is not None else raw_df
        
        mining_only = st.checkbox(t_mining)
        sel_p = st.selectbox("Province", [all_label] + sorted(raw_df["Province"].dropna().unique()))
        sel_c = st.selectbox(t_city, [all_label] + sorted(raw_df["City"].dropna().unique()))
        rad_km = st.slider(t_radius, 0, 500, 0)
        
        sel_comp = st.selectbox(t_comp, [all_label] + sorted(display_df["Display_Company"].dropna().unique()))
        sel_f = st.selectbox(t_fac, [all_label] + sorted(display_df["Facility"].dropna().unique()))

        if st.button(T_SYNC, use_container_width=True, type="primary"):
            t_df = raw_df.copy()
            if mining_only: 
                t_df = t_df[t_df["NAICS_Code"].astype(str).str.startswith(("21", "331"))]
            if sel_p not in ["All", "Tous"]: 
                t_df = t_df[t_df["Province"] == sel_p]
            if sel_c not in ["All", "Tous"]:
                c_row = raw_df[raw_df["City"] == sel_c].dropna(subset=["Lat", "Lon"])
                if not c_row.empty:
                    if rad_km > 0: 
                        t_df = filter_by_radius(t_df, float(c_row.iloc[0].Lat), float(c_row.iloc[0].Lon), rad_km)
                    else: 
                        t_df = t_df[t_df["City"] == sel_c]
            
            if sel_comp not in ["All", "Tous"]: 
                t_df = t_df[t_df["Display_Company"] == sel_comp]
            if sel_f not in ["All", "Tous"]: 
                t_df = t_df[t_df["Facility"] == sel_f]
            
            st.session_state.cascading_df = t_df
            st.rerun(scope="fragment")

        sel_s = st.selectbox(t_poll, [all_label] + subs_list)
        sel_range = st.slider(t_years, min_y, max_y, (min_y, max_y))

        st.divider()

        # INTERNAL HELPER: Apply filtering logic for buttons
        def get_final_selection():
            f_df = raw_df.copy()
            filter_desc = []
            if mining_only: 
                f_df = f_df[f_df["NAICS_Code"].astype(str).str.startswith(("21", "331"))]
                filter_desc.append("Mining" if lang == "EN" else "Mines")
            if sel_p not in ["All", "Tous"]: 
                f_df = f_df[f_df["Province"] == sel_p]
                filter_desc.append(sel_p)
            if sel_c not in ["All", "Tous"]:
                c_row = raw_df[raw_df["City"] == sel_c].dropna(subset=["Lat", "Lon"])
                if not c_row.empty:
                    if rad_km > 0: 
                        f_df = filter_by_radius(f_df, float(c_row.iloc[0].Lat), float(c_row.iloc[0].Lon), rad_km)
                        filter_desc.append(f"{sel_c} (+{rad_km}km)")
                    else: 
                        f_df = f_df[f_df["City"] == sel_c]
                        filter_desc.append(sel_c)
            
            if sel_comp not in ["All", "Tous"]: 
                f_df = f_df[f_df["Display_Company"] == sel_comp]
                filter_desc.append(sel_comp)
            if sel_f not in ["All", "Tous"]: 
                f_df = f_df[f_df["Facility"] == sel_f]
                filter_desc.append(sel_f)
            if sel_s not in ["All", "Tous"]: 
                f_df = f_df[f_df[l_sub_col] == sel_s]
                filter_desc.append(sel_s)
            
            filter_desc.append(f"{sel_range[0]}-{sel_range[1]}")
            label = " | ".join(filter_desc) if filter_desc else ("Full Dataset" if lang == "EN" else "Données complètes")
            
            final_df = f_df[(f_df["Year"] >= sel_range[0]) & (f_df["Year"] <= sel_range[1])]
            return final_df, label

        # BUTTON LOGIC
        c1, c2 = st.columns(2)
        if c1.button(T_INC, use_container_width=True): 
            curr_df, label = get_final_selection()
            st.session_state.active_selections.append({
                "type": "Include", 
                "label": label, 
                "ids": set(curr_df["_uid"].tolist()),
                "filter_context": {
                    "name": sel_c, "prov": sel_p, "radius": rad_km, 
                    "comp": sel_comp, "fac": sel_f, "pollutant": sel_s, "lang": lang
                }
            })
            st.rerun() # Full rerun to update main dashboard

        if c2.button(T_EXC, use_container_width=True): 
            curr_df, label = get_final_selection()
            st.session_state.active_selections.append({
                "type": "Exclude", 
                "label": label, 
                "ids": set(curr_df["_uid"].tolist()),
                "filter_context": {
                    "name": sel_c, "prov": sel_p, "radius": rad_km, 
                    "comp": sel_comp, "fac": sel_f, "pollutant": sel_s, "lang": lang
                }
            })
            st.rerun()

# --- 5. EXECUTION ---
if raw_df is not None:
    with st.sidebar:
        # 1. Fragmented Selection Builder
        selection_sidebar_fragment(raw_df)
        
        # 2. Workspace Manager (Now run as a sibling)
        workspace_manager_ui()
        
        # 3. Kiosk Config (Now run as a sibling)
        l_sub_col = "Substance_EN" if st.session_state.lang == "EN" else "Substance_FR"
        subs_list = sorted(raw_df[l_sub_col].dropna().unique())
        min_y, max_y = int(raw_df["Year"].min()), int(raw_df["Year"].max())
        kiosk_config_ui(raw_df, subs_list, min_y, max_y, {})

    # Calculate final masked dataframe
    workspace_ids = set()
    for sel in st.session_state.active_selections:
        if sel["type"] == "Include": 
            workspace_ids.update(sel["ids"])
        else: 
            workspace_ids.difference_update(sel["ids"])

    w_df = raw_df[raw_df["_uid"].isin(workspace_ids)].copy()
    
    if not w_df.empty:
        # Centralized Normalization (Unit scaling)
        w_df = normalize_quantity(w_df)
        render_main_dashboard(w_df)
    else:
        st.info("💡 Workspace Empty. Add layers to visualize." if lang == "EN" else "💡 Espace de travail vide. Ajoutez des couches.")