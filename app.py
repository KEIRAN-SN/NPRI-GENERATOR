import streamlit as st
import pandas as pd
from data_engine import process_files, filter_by_radius, normalize_quantity
from ui_components import workspace_manager_ui, rfid_hardware_mapper_ui, kiosk_config_ui
from dashboard import render_main_dashboard

# --- PAGE SETUP ---
st.set_page_config(page_title="NPRI Data Explorer", layout="wide", page_icon="🌲")

# --- SESSION STATE INITIALIZATION ---
if "lang" not in st.session_state: 
    st.session_state.lang = "EN"
if "active_selections" not in st.session_state: 
    st.session_state.active_selections = []
if "kiosk_locs" not in st.session_state:
    st.session_state.kiosk_locs = {}
if "kiosk_pols" not in st.session_state:
    st.session_state.kiosk_pols = {}
if "kiosk_times" not in st.session_state:
    st.session_state.kiosk_times = []

# --- MULTI-DIRECTIONAL CROSS-FILTERING ENGINE ---
def get_filtered_options(df, filters, target):
    """
    Calculates available options for a specific dropdown based on ALL OTHER active filters.
    This creates true multi-directional cross-filtering without needing a Sync button.
    """
    mask = pd.Series(True, index=df.index)
    
    # 1. Always apply Mining mask if selected
    if filters.get("mining"):
        mask &= df["NAICS_Code"].astype(str).str.startswith(("21", "331"))
        
    # 2. Apply all other active filters EXCEPT the target we are currently generating options for
    if target != "Province" and filters.get("prov") not in ["All", "Tous"]:
        mask &= df["Province"] == filters["prov"]
        
    if target != "City" and filters.get("city") not in ["All", "Tous"]:
        rad = filters.get("rad", 0.0)
        if rad > 0:
            # If a radius is applied, filter by distance instead of strict city name
            c_row = df[df["City"] == filters["city"]].dropna(subset=["Lat", "Lon"])
            if not c_row.empty:
                rad_df = filter_by_radius(df, float(c_row.iloc[0].Lat), float(c_row.iloc[0].Lon), rad)
                mask &= df.index.isin(rad_df.index)
            else:
                mask &= df["City"] == filters["city"]
        else:
            mask &= df["City"] == filters["city"]
            
    if target != "Company" and filters.get("comp") not in ["All", "Tous"]:
        mask &= df["Display_Company"] == filters["comp"]
    if target != "Facility" and filters.get("fac") not in ["All", "Tous"]:
        mask &= df["Facility"] == filters["fac"]
    if target != "Pollutant" and filters.get("pol") not in ["All", "Tous"]:
        mask &= df[f"Substance_{st.session_state.lang}"] == filters["pol"]
        
    col_map = {
        "Province": "Province",
        "City": "City",
        "Company": "Display_Company",
        "Facility": "Facility",
        "Pollutant": f"Substance_{st.session_state.lang}"
    }
    
    # Return unique valid options + the "All" default
    opts = df[mask][col_map[target]].dropna().unique().tolist()
    return ["All" if st.session_state.lang == "EN" else "Tous"] + sorted(opts)

def get_final_selection(df):
    """Processes the final filtered DataFrame based on the current UI state."""
    lang = st.session_state.lang
    default_all = "All" if lang == "EN" else "Tous"
    f_df = df.copy()
    
    # Core Masking
    if st.session_state.get("f_mining"):
        f_df = f_df[f_df["NAICS_Code"].astype(str).str.startswith(("21", "331"))]
    if st.session_state.get("f_prov", default_all) != default_all:
        f_df = f_df[f_df["Province"] == st.session_state.f_prov]
        
    # City & Radius Math
    target_city = st.session_state.get("f_city", default_all)
    if target_city != default_all:
        rad = float(st.session_state.get("f_rad", 0.0))
        if rad > 0:
            c_row = df[df["City"] == target_city].dropna(subset=["Lat", "Lon"])
            if not c_row.empty:
                f_df = filter_by_radius(f_df, float(c_row.iloc[0].Lat), float(c_row.iloc[0].Lon), rad)
        else:
            f_df = f_df[f_df["City"] == target_city]
            
    # Granular Focus
    if st.session_state.get("f_comp", default_all) != default_all:
        f_df = f_df[f_df["Display_Company"] == st.session_state.f_comp]
    if st.session_state.get("f_fac", default_all) != default_all:
        f_df = f_df[f_df["Facility"] == st.session_state.f_fac]
        
    target_pol = st.session_state.get("f_pol", default_all)
    if target_pol != default_all:
        sub_col = f"Substance_{lang}"
        f_df = f_df[f_df[sub_col] == target_pol]
        
    years = st.session_state.get("f_years", (int(df["Year"].min()), int(df["Year"].max())))
    f_df = f_df[f_df["Year"].between(years[0], years[1])]
    
    # Construct UI Label
    parts = []
    if target_city != default_all:
        rad = float(st.session_state.get("f_rad", 0.0))
        parts.append(f"{target_city} (+{rad}km)" if rad > 0 else target_city)
    if st.session_state.get("f_comp", default_all) != default_all: parts.append(st.session_state.f_comp)
    if st.session_state.get("f_fac", default_all) != default_all: parts.append(st.session_state.f_fac)
    if not parts: parts.append("Canada")
    if target_pol != default_all: parts.append(target_pol)
    parts.append(f"{years[0]}-{years[1]}")
    
    ctx = {
        "name": target_city if target_city != default_all else "All",
        "pollutant": target_pol if target_pol != default_all else "All"
    }
    
    return f_df, " | ".join(parts), ctx

@st.fragment
def selection_sidebar_fragment(raw_df):
    """Renders the real-time cross-filtering sidebar."""
    lang = st.session_state.lang
    default_all = "All" if lang == "EN" else "Tous"
    
    st.header("🎯 Selection Builder" if lang == "EN" else "🎯 Créateur de sélection")
    
    # 1. Reset Filters Button
    if st.button("🔄 Reset Filters" if lang == "EN" else "🔄 Réinitialiser les filtres", use_container_width=True):
        for k in ["f_mining", "f_prov", "f_city", "f_comp", "f_fac", "f_pol", "f_rad"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun(scope="fragment")

    st.divider()
    
    # 2. Capture Current Filter State safely
    filters = {
        "mining": st.session_state.get("f_mining", False),
        "prov": st.session_state.get("f_prov", default_all),
        "city": st.session_state.get("f_city", default_all),
        "rad": float(st.session_state.get("f_rad", 0.0)),
        "comp": st.session_state.get("f_comp", default_all),
        "fac": st.session_state.get("f_fac", default_all),
        "pol": st.session_state.get("f_pol", default_all)
    }

    # Mining Checkbox
    st.checkbox("⛏️ Mining/Smelting Only" if lang == "EN" else "⛏️ Exploitation minière uniquement", key="f_mining")
    filters["mining"] = st.session_state.get("f_mining", False) # Instant update for options

    # 3. Calculate dynamic options for each dropdown
    with st.spinner("Syncing cross-filters..." if lang == "EN" else "Synchronisation des filtres..."):
        prov_opts = get_filtered_options(raw_df, filters, "Province")
        city_opts = get_filtered_options(raw_df, filters, "City")
        comp_opts = get_filtered_options(raw_df, filters, "Company")
        fac_opts  = get_filtered_options(raw_df, filters, "Facility")
        pol_opts  = get_filtered_options(raw_df, filters, "Pollutant")

    def safe_idx(opts, val):
        return opts.index(val) if val in opts else 0

    # 4. Render Auto-Updating Selectboxes
    st.selectbox("Province", prov_opts, index=safe_idx(prov_opts, filters["prov"]), key="f_prov")
    st.selectbox("City / Ville", city_opts, index=safe_idx(city_opts, filters["city"]), key="f_city")
    
    if st.session_state.get("f_city", default_all) != default_all:
        st.slider("Radius / Rayon (km)", 0.0, 500.0, float(st.session_state.get("f_rad", 0.0)), step=10.0, key="f_rad")
        
    st.selectbox("Company / Entreprise", comp_opts, index=safe_idx(comp_opts, filters["comp"]), key="f_comp")
    st.selectbox("Facility / Installation", fac_opts, index=safe_idx(fac_opts, filters["fac"]), key="f_fac")
    
    st.divider()
    
    st.selectbox("Pollutant / Polluant", pol_opts, index=safe_idx(pol_opts, filters["pol"]), key="f_pol")
    
    min_y, max_y = int(raw_df["Year"].min()), int(raw_df["Year"].max())
    st.slider("Years / Années", min_y, max_y, st.session_state.get("f_years", (min_y, max_y)), key="f_years")

    st.divider()
    
    # 5. Workspace Actions
    c1, c2 = st.columns(2)
    if c1.button("➕ Include", use_container_width=True, type="primary"):
        f_df, lbl, ctx = get_final_selection(raw_df)
        if not f_df.empty:
            st.session_state.active_selections.append({
                "type": "Include",
                "label": lbl,
                "ids": set(f_df["_uid"].tolist()),
                "filter_context": ctx
            })
            st.rerun() 
        else:
            st.error("No data found." if lang == "EN" else "Aucune donnée trouvée.")
            
    if c2.button("➖ Exclude", use_container_width=True):
        f_df, lbl, ctx = get_final_selection(raw_df)
        if not f_df.empty:
            st.session_state.active_selections.append({
                "type": "Exclude",
                "label": f"EXCLUDE: {lbl}",
                "ids": set(f_df["_uid"].tolist()),
                "filter_context": ctx
            })
            st.rerun()
        else:
            st.error("No data found." if lang == "EN" else "Aucune donnée trouvée.")

# --- MAIN APP EXECUTION ---
def main():
    # Setup Sidebar Global Components
    with st.sidebar:
        st.title("🌲 NPRI Explorer")
        
        # Bilingual Toggle
        new_lang = st.radio("Language / Langue", ["EN", "FR"], horizontal=True, label_visibility="collapsed")
        if new_lang != st.session_state.lang:
            st.session_state.lang = new_lang
            st.rerun()

        # Placeholder to show loading state in sidebar while data processes
        sidebar_placeholder = st.empty()
        sidebar_placeholder.info("⏳ Preparing workspace..." if st.session_state.lang == "EN" else "⏳ Préparation de l'espace...")

    # Render Main View Headers immediately so the app looks anchored while loading
    st.title("National Pollutant Release Inventory" if st.session_state.lang == "EN" else "Inventaire national des rejets de polluants")

    # Data Pipeline with a highly visible status component
    loading_msg = "🌍 Loading NPRI Datasets..." if st.session_state.lang == "EN" else "🌍 Chargement des données de l'INRP..."
    success_msg = "✅ Datasets Synced!" if st.session_state.lang == "EN" else "✅ Données synchronisées !"
    
    with st.status(loading_msg, expanded=True) as status:
        st.write("Processing files from `./data`. This may take a moment if the cache is empty..." if st.session_state.lang == "EN" else "Traitement des fichiers depuis `./data`. Cela peut prendre un moment si le cache est vide...")
        
        raw_df, load_msg = process_files("./data")
        
        if raw_df is not None:
            status.update(label=success_msg, state="complete", expanded=False)
        else:
            status.update(label="❌ Data Error" if st.session_state.lang == "EN" else "❌ Erreur de données", state="error", expanded=True)
            
    if raw_df is None:
        st.error(load_msg)
        return

    # Clear the sidebar placeholder now that data is ready
    sidebar_placeholder.empty()

    # Continue rendering the rest of the sidebar now that data is loaded
    with st.sidebar:
        # Workspace Utilities
        workspace_manager_ui()
        
        # Render Selection Builder logic inside Sidebar
        selection_sidebar_fragment(raw_df)

    # Compile Workspace Data Layers
    workspace_ids = set()
    for sel in st.session_state.active_selections:
        if sel["type"] == "Include": 
            workspace_ids.update(sel["ids"])
        else: 
            workspace_ids.difference_update(sel["ids"])

    w_df = raw_df[raw_df["_uid"].isin(workspace_ids)].copy()
    
    if not w_df.empty:
        w_df = normalize_quantity(w_df)
        
    # Render Dashboard Panel
    render_main_dashboard(w_df)
    
    st.divider()
    
    # Render Hardware & Kiosk Generation Tools
    rfid_hardware_mapper_ui()
    
    subs_list = raw_df[f"Substance_{st.session_state.lang}"].dropna().unique().tolist()
    min_y, max_y = int(raw_df["Year"].min()), int(raw_df["Year"].max())
    kiosk_config_ui(raw_df, subs_list, min_y, max_y, {})

if __name__ == "__main__":
    main()