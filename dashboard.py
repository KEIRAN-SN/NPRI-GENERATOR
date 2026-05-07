import streamlit as st
import plotly.express as px
import pydeck as pdk
from visuals import build_heat_layer

def render_main_dashboard(w_df):
    lang = st.session_state.get("lang", "EN")
    
    # Translations
    t_header = "🛠️ Active Workspace Summary" if lang == "EN" else "🛠️ Résumé de l'espace de travail"
    t_released = "Total Released" if lang == "EN" else "Total rejeté"
    t_facs = "Facilities" if lang == "EN" else "Installations"
    t_pols = "Pollutants" if lang == "EN" else "Substances"
    t_empty = "💡 Workspace Empty. Add layers to visualize." if lang == "EN" else "💡 Espace vide. Ajoutez des couches."
    
    if not w_df.empty:
        # 1. UNIT NORMALIZATION LOGIC
        # We check for 'Quantity_Tonnes' (added by data_engine.normalize_quantity)
        # falling back to 'Quantity' if it was already normalized in app.py
        qty_col = "Quantity_Tonnes" if "Quantity_Tonnes" in w_df.columns else "Quantity"
        total_tonnes = w_df[qty_col].sum()
        
        # Decide display unit (match generator logic: < 1t -> kg)
        if 0 < total_tonnes < 1.0:
            display_total = total_tonnes * 1000
            display_unit = "kg"
            chart_factor = 1000
        else:
            display_total = total_tonnes
            display_unit = "tonnes" if lang == "EN" else "tonnes métriques"
            chart_factor = 1

        st.subheader(t_header)
        m1, m2, m3 = st.columns(3)
        
        # --- DISPLAY UNITS BESIDE THE TOTAL ---
        m1.metric(t_released, f"{display_total:,.2f} {display_unit}")
        
        m2.metric(t_facs, w_df["NPRI_ID"].nunique())
        
        sub_col = f"Substance_{lang}"
        m3.metric(t_pols, w_df[sub_col].nunique())
        
        # 2. LINE CHART WITH DYNAMIC UNIT LABELS
        chart_data = w_df.groupby("Year")[qty_col].sum().reset_index()
        chart_data[qty_col] = chart_data[qty_col] * chart_factor
        
        fig = px.line(
            chart_data, 
            x="Year", y=qty_col, 
            markers=True,
            labels={qty_col: f"{t_released} ({display_unit})"}
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 3. HEATMAP
        layer, g = build_heat_layer(w_df, 30, 5)
        st.pydeck_chart(pdk.Deck(
            layers=[layer], 
            initial_view_state=pdk.ViewState(
                latitude=g["Lat"].mean(), 
                longitude=g["Lon"].mean(), 
                zoom=4
            ), 
            tooltip=True
        ))
        
        # 4. DATA TABLE
        cols_fr = ["Année", "Installation", "Entreprise", "Ville", "Province", "Substance", "Quantité", "Unités"]
        cols_en = ["Year", "Facility", "Display_Company", "City", "Province", "Substance", "Quantity", "Units"]
        
        display_cols = cols_en if lang == "EN" else cols_fr
        
        # We show the original raw Quantity/Units in the table for reference
        view_df = w_df[["Year", "Facility", "Display_Company", "City", "Province", sub_col, "Quantity", "Units"]].copy()
        view_df.columns = display_cols
        
        st.dataframe(view_df, use_container_width=True)
    else:
        st.info(t_empty)