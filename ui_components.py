import streamlit as st
import pandas as pd
import json
import os
import time
import io
import zipfile

# --- UTILITY FUNCTIONS ---

RFID_DB_FILE = "./rfid_database.json"

def load_rfid_data():
    if os.path.exists(RFID_DB_FILE):
        with open(RFID_DB_FILE, "r") as f:
            return json.load(f)
    # Default structure mapping to 10 slots (l1-l10, t1-t10, p1-p10) for full hardware compatibility
    return {
        "locations": {f"l{i}": {"name": f"L{i}", "tag": "", "note": ""} for i in range(1, 11)},
        "timeframes": {f"t{i}": {"name": f"T{i}", "tag": "", "note": ""} for i in range(1, 11)},
        "pollutants": {f"p{i}": {"name": f"P{i}", "tag": "", "note": ""} for i in range(1, 11)}
    }

def save_rfid_data(data):
    with open(RFID_DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

@st.cache_data(show_spinner=False, ttl=3600)
def create_data_zip(folder_path="./data"):
    """Creates a ZIP archive of all raw files in the data folder, excluding the cache."""
    zip_buffer = io.BytesIO()
    has_files = False
    
    if os.path.exists(folder_path):
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for root, _, files in os.walk(folder_path):
                for file in files:
                    # Skip the large generated cache file to save bandwidth
                    if file.endswith(".parquet"):
                        continue
                    
                    file_path = os.path.join(root, file)
                    zip_file.write(file_path, os.path.relpath(file_path, folder_path))
                    has_files = True
                    
    if not has_files:
        return None
        
    zip_buffer.seek(0)
    return zip_buffer.getvalue()

def serialize_workspace():
    """Converts session state into a JSON-ready string, ensuring widget keys are synced."""
    if "active_selections" not in st.session_state:
        return json.dumps({})

    # 1. Handle Active Selections (Sets to Lists)
    serializable_selections = []
    for sel in st.session_state.active_selections:
        new_sel = sel.copy()
        if isinstance(new_sel.get("ids"), set):
            new_sel["ids"] = list(new_sel["ids"]) 
        serializable_selections.append(new_sel)
    
    # 2. Final Sync: Ensure the dictionaries match the current widget values
    kiosk_pols = st.session_state.get("kiosk_pols", {})
    for i in range(1, 7):
        p_id = f"P{i}"
        if f"p_sel_{i}" in st.session_state:
            kiosk_pols[p_id]["data_name"] = st.session_state[f"p_sel_{i}"]
        if f"p_lab_{i}" in st.session_state:
            kiosk_pols[p_id]["display_name"] = st.session_state[f"p_lab_{i}"]

    workspace_data = {
        "active_selections": serializable_selections,
        "kiosk_locs": st.session_state.get("kiosk_locs", {}),
        "kiosk_pols": kiosk_pols,
        "kiosk_times": st.session_state.get("kiosk_times", []), 
        "lang": st.session_state.get("lang", "EN")
    }
    return json.dumps(workspace_data, indent=4)

def apply_loaded_state(data):
    """Utility to map JSON data back into Session State and Widget Keys."""
    if not data:
        return
        
    # Restore Selections
    for sel in data.get("active_selections", []):
        if "ids" in sel:
            sel["ids"] = set(sel["ids"])
    st.session_state.active_selections = data.get("active_selections", [])
    
    # Restore Locations
    st.session_state.kiosk_locs = data.get("kiosk_locs", {})
    
    # Restore Pollutants & Update Widget Keys (Removing default value conflicts)
    pols = data.get("kiosk_pols", {})
    st.session_state.kiosk_pols = pols
    for i in range(1, 7):
        p_id = f"P{i}"
        if p_id in pols:
            st.session_state[f"p_sel_{i}"] = pols[p_id]["data_name"]
            st.session_state[f"p_lab_{i}"] = pols[p_id]["display_name"]

    # Restore Times & Update Widget Keys
    times = data.get("kiosk_times", [])
    st.session_state.kiosk_times = times
    for t_entry in times:
        idx = t_entry["id"].replace("T", "")
        st.session_state[f"t_slider_{idx}"] = tuple(t_entry["years"])
    
    if "lang" in data:
        st.session_state.lang = data["lang"]


# --- UI COMPONENTS ---

@st.fragment
def workspace_manager_ui():
    lang = st.session_state.get("lang", "EN")
    save_path = "last_session.json"
    
    t_title = "💾 Workspace Management" if lang == "EN" else "💾 Gestion de l'espace"
    t_layers = "Active Layers" if lang == "EN" else "Couches actives"
    t_save_loc = "Save Locally" if lang == "EN" else "Sauvegarder"
    t_rest_loc = "Restore Last" if lang == "EN" else "Restaurer"

    with st.expander(t_title, expanded=True):
        c1, c2, c3 = st.columns(3)
        
        if c1.button(t_save_loc, use_container_width=True):
            with st.spinner("Saving..." if lang == "EN" else "Sauvegarde..."):
                with open(save_path, "w") as f:
                    f.write(serialize_workspace())
                time.sleep(0.2) 
            st.toast("✅ Saved!" if lang == "EN" else "✅ Enregistré !")

        if os.path.exists(save_path):
            if c2.button(t_rest_loc, use_container_width=True, type="primary"):
                with st.status("Restoring State..." if lang == "EN" else "Restauration...") as s:
                    with open(save_path, "r") as f:
                        data = json.load(f)
                        apply_loaded_state(data)
                    time.sleep(0.2) 
                    s.update(label="✅ Restored!" if lang == "EN" else "✅ Restauré !", state="complete")
                st.rerun() 
        else:
            c2.button(t_rest_loc, use_container_width=True, disabled=True)

        if c3.button("🗑️ Clear All", use_container_width=True):
            st.session_state.active_selections = []
            st.session_state.kiosk_locs = {}
            st.session_state.kiosk_pols = {}
            st.session_state.kiosk_times = []
            st.toast("🧹 Workspace cleared" if lang == "EN" else "🧹 Espace vidé")
            st.rerun()

        st.divider()

        # 2. FILE IMPORT/EXPORT
        col_ex, col_im = st.columns(2)
        ws_json = serialize_workspace()
        col_ex.download_button("📥 Export Config (.json)", ws_json, "npri_workspace.json", "application/json", use_container_width=True)
        
        uploaded_ws = col_im.file_uploader("Upload Config", type="json", label_visibility="collapsed", key="ws_uploader")
        if uploaded_ws is not None:
            if "last_upload" not in st.session_state or st.session_state.last_upload != uploaded_ws.name:
                with st.status("Syncing State..." if lang == "EN" else "Synchronisation...") as s:
                    apply_loaded_state(json.load(uploaded_ws))
                    st.session_state.last_upload = uploaded_ws.name
                    time.sleep(0.2)
                    s.update(label="✅ Success!" if lang == "EN" else "✅ Succès !", state="complete")
                st.rerun()

        st.divider()
        
        # 3. SERVER CONTROLS
        st.markdown("**⚙️ Server Controls**" if lang == "EN" else "**⚙️ Contrôles du serveur**")
        
        # Upload Datasets
        uploaded_data_files = st.file_uploader(
            "Upload NPRI Datasets (.csv)" if lang == "EN" else "Téléverser des jeux de données INRP (.csv)", 
            type="csv", 
            accept_multiple_files=True, 
            key="server_data_uploader"
        )
        if uploaded_data_files:
            if st.button("💾 Save Uploaded Datasets" if lang == "EN" else "💾 Enregistrer les jeux de données", use_container_width=True, type="primary"):
                os.makedirs("./data", exist_ok=True)
                for f in uploaded_data_files:
                    with open(os.path.join("./data", f.name), "wb") as out_f:
                        out_f.write(f.getbuffer())
                
                st.success(f"Saved {len(uploaded_data_files)} files. Reloading data..." if lang == "EN" else f"{len(uploaded_data_files)} fichiers enregistrés. Rechargement...")
                time.sleep(1)
                st.rerun()

        # Download ZIP and Clear Cache row
        c_ctrl1, c_ctrl2 = st.columns(2)
        
        zip_bytes = create_data_zip("./data")
        if zip_bytes:
            c_ctrl1.download_button(
                label="📥 Download ./data (ZIP)" if lang == "EN" else "📥 Télécharger ./data (ZIP)",
                data=zip_bytes,
                file_name="NPRI_Server_Data.zip",
                mime="application/zip",
                use_container_width=True
            )
        else:
            c_ctrl1.button("📥 Download ./data" if lang == "EN" else "📥 Télécharger ./data", disabled=True, use_container_width=True)

        if c_ctrl2.button("🗑️ Clear Parquet Cache" if lang == "EN" else "🗑️ Vider le cache Parquet", use_container_width=True):
            cache_path = "./data/processed_cache.parquet"
            if os.path.exists(cache_path):
                try:
                    os.remove(cache_path)
                    st.toast("✅ Cache cleared! Rebuilding on next load." if lang == "EN" else "✅ Cache vidé ! Reconstruction au prochain chargement.")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error clearing cache: {e}")
            else:
                st.toast("No cache file found." if lang == "EN" else "Aucun fichier cache trouvé.")

        st.divider()

        # 4. ACTIVE LAYER LIST
        st.subheader(t_layers)
        if not st.session_state.active_selections:
            st.info("No filters applied yet." if lang == "EN" else "Aucun filtre appliqué.")
        else:
            for idx, sel in enumerate(reversed(st.session_state.active_selections)):
                real_idx = len(st.session_state.active_selections) - 1 - idx
                with st.container(border=True):
                    icon = "➕" if sel["type"] == "Include" else "➖"
                    st.markdown(f"**{icon} {sel['label']}**")
                    
                    ctx = sel.get("filter_context", {})
                    if ctx:
                        details = []
                        if ctx.get("name") not in ["All", "Tous"]: details.append(f"📍 {ctx['name']}")
                        if ctx.get("pollutant") not in ["All", "Tous"]: details.append(f"☁️ {ctx['pollutant']}")
                        if details: st.caption(" | ".join(details))

                    # Full-width remove button under the details
                    if st.button("🗑️ Remove Layer", key=f"del_{real_idx}", use_container_width=True):
                        st.session_state.active_selections.pop(real_idx)
                        st.rerun()

@st.fragment
def rfid_hardware_mapper_ui():
    """Renders the UI for mapping physical RFID tags to the 10 available slots."""
    lang = st.session_state.get("lang", "EN")
    title = "💳 RFID Hardware Mapper" if lang == "EN" else "💳 Mappeur de matériel RFID"
    
    with st.expander(title, expanded=False):
        rfid_data = load_rfid_data()
        col1, col2 = st.columns([0.4, 0.6])

        with col1:
            st.subheader("Edit Mapping" if lang == "EN" else "Modifier le mappage")
            
            # Bilingual Category mapping updated for 10 slots
            cat_map = {
                "Locations (L1-L10)": "locations", 
                "Timeframes (T1-T10)": "timeframes", 
                "Pollutants (P1-P10)": "pollutants"
            } if lang == "EN" else {
                "Lieux (L1-L10)": "locations", 
                "Périodes (T1-T10)": "timeframes", 
                "Polluants (P1-P10)": "pollutants"
            }
            
            display_cat = st.selectbox("Category" if lang == "EN" else "Catégorie", list(cat_map.keys()), key="rfid_cat")
            category = cat_map[display_cat]
            
            slot_keys = list(rfid_data[category].keys())
            selected_slot = st.selectbox("Slot" if lang == "EN" else "Emplacement", slot_keys, format_func=lambda x: rfid_data[category][x]["name"], key="rfid_slot_selector")

            current_val = rfid_data[category][selected_slot]
            new_tag = st.text_input("RFID Tag ID" if lang == "EN" else "ID de l'étiquette RFID", value=current_val["tag"], key="rfid_tag_input")
            new_note = st.text_area("Notes", value=current_val["note"], key="rfid_note_input")

            if st.button("💾 Update Mapping" if lang == "EN" else "💾 Mettre à jour", type="primary", use_container_width=True):
                rfid_data[category][selected_slot]["tag"] = new_tag
                rfid_data[category][selected_slot]["note"] = new_note
                save_rfid_data(rfid_data)
                st.success(f"Linked '{new_tag}' to slot {selected_slot.upper()}!" if lang == "EN" else f"'{new_tag}' lié à {selected_slot.upper()}!")
                st.rerun(scope="fragment") 

        with col2:
            st.subheader("Current Registry" if lang == "EN" else "Registre actuel")
            flattened = []
            for cat, slots in rfid_data.items():
                for s_id, info in slots.items():
                    flattened.append({
                        "Category": cat.capitalize(),
                        "Slot": info["name"],
                        "RFID_Tag": info["tag"],
                        "Note": info["note"]
                    })
            df_rfid = pd.DataFrame(flattened)
            st.dataframe(df_rfid, use_container_width=True, height=350)
            
            st.divider()
            # Server-side Export Action
            if st.button("🚀 Export Config to Server (`./kiosk_app/config.json`)" if lang == "EN" else "🚀 Exporter config au serveur", type="primary", use_container_width=True):
                try:
                    kiosk_app_dir = "./kiosk_app"
                    os.makedirs(kiosk_app_dir, exist_ok=True)
                    export_path = os.path.join(kiosk_app_dir, "config.json")
                    
                    with open(export_path, "w") as f:
                        json.dump(rfid_data, f, indent=4)
                        
                    st.success(f"Successfully exported JSON to `{export_path}`!" if lang == "EN" else f"JSON exporté avec succès vers `{export_path}` !")
                except Exception as e:
                    st.error(f"Error exporting file: {e}")

def sync_p_label(idx):
    """Updates the pollutant label field when the source substance is changed."""
    st.session_state[f"p_lab_{idx}"] = st.session_state[f"p_sel_{idx}"]

def auto_fill_time_cycles_callback(min_y, max_y):
    """Calculates and updates time cycle sliders evenly."""
    span = max_y - min_y + 1
    step = span / 6.0
    
    for i in range(6):
        start_yr = min_y + int(round(i * step))
        end_yr = min_y + int(round((i + 1) * step)) - 1
        end_yr = max(start_yr, end_yr)
        if i == 5: end_yr = max_y
        st.session_state[f"t_slider_{i+1}"] = (start_yr, end_yr)

@st.fragment
def kiosk_config_ui(raw_df, subs_list, min_y, max_y, current_filters):
    lang = st.session_state.lang
    
    # Initialize Structures if missing
    if "kiosk_times" not in st.session_state or not st.session_state.kiosk_times:
        st.session_state.kiosk_times = [{"id": f"T{i}", "years": [max_y-5, max_y]} for i in range(1, 7)]
    if "kiosk_pols" not in st.session_state:
        st.session_state.kiosk_pols = {}

    for i in range(1, 7):
        p_key = f"P{i}"
        if p_key not in st.session_state.kiosk_pols:
            st.session_state.kiosk_pols[p_key] = {"data_name": "", "display_name": ""}

    with st.expander("📟 RFID Kiosk Data Configuration" if lang == "EN" else "📟 Configuration des données du kiosque", expanded=False):
        slots = [f"L{i}" for i in range(1, 7)]
        cols = st.columns(3) 
        
        for i, s_id in enumerate(slots):
            with cols[i % 3].container(border=True):
                if s_id in st.session_state.kiosk_locs:
                    loc = st.session_state.kiosk_locs[s_id]
                    lbl = loc.get("display_label", "Unknown")
                    ctx_str = loc.get("full_context", "")
                    mask_len = len(loc.get("workspace_mask", []))
                    
                    st.markdown(f"**{s_id}** ✅")
                    st.markdown(f"**{lbl}**")
                    if ctx_str:
                        st.caption(f"📍 {ctx_str}")
                    st.caption(f"📊 {mask_len} records")
                    
                    act_c1, act_c2 = st.columns(2)
                    if act_c1.button("✏️", key=f"edit_{s_id}", help=f"Edit {s_id}", use_container_width=True):
                        if "source_layers" in loc:
                            st.session_state.active_selections = []
                            for layer in loc["source_layers"]:
                                restored = layer.copy()
                                restored["ids"] = set(restored["ids"])
                                st.session_state.active_selections.append(restored)
                            st.toast(f"Loaded {s_id} back into Workspace!")
                            st.rerun() 
                        else:
                            st.toast("No source data available for this slot.")

                    if act_c2.button("🗑️", key=f"clr_{s_id}", help=f"Clear {s_id}", use_container_width=True):
                        del st.session_state.kiosk_locs[s_id]
                        st.rerun(scope="fragment")
                        
                else:
                    st.markdown(f"**{s_id}** ❌")
                    st.markdown("**Empty**")
                    st.caption("No data assigned")
                    st.caption("&nbsp;\n&nbsp;") 

        if st.button("⚡ Bulk Fill Slots from Workspace", use_container_width=True, type="primary"):
            with st.spinner("Mapping..."):
                active_layers = [s for s in st.session_state.active_selections if s["type"] == "Include"]
                for i, layer in enumerate(active_layers[:6]):
                    s_id = f"L{i+1}"
                    s_layer = layer.copy()
                    s_layer["ids"] = list(s_layer["ids"])

                    st.session_state.kiosk_locs[s_id] = {
                        "display_label": layer["label"].split("|")[0].strip(),
                        "full_context": layer["label"], 
                        "workspace_mask": list(layer["ids"]),
                        "source_layers": [s_layer], 
                        "is_aggregate": True
                    }
                time.sleep(0.2)
            st.rerun(scope="fragment")

        st.divider()

        # Slot Assignment
        c1, c2 = st.columns([0.3, 0.7])
        l_slot = c1.selectbox("Slot", slots, key="kiosk_slot_assignment")
        existing = st.session_state.kiosk_locs.get(l_slot, {})
        k_label = c2.text_input("Display Label", value=existing.get("display_label", ""), key="kiosk_label_assignment")

        if st.button(f"Assign Workspace to {l_slot}", use_container_width=True):
            w_ids = set()
            layer_labels = []
            saved_layers = []
            
            for s in st.session_state.active_selections:
                s_copy = s.copy()
                s_copy["ids"] = list(s_copy["ids"])
                saved_layers.append(s_copy)

                if s["type"] == "Include": 
                    w_ids.update(s["ids"])
                    layer_labels.append(s["label"])
                else: 
                    w_ids.difference_update(s["ids"])
            
            ctx_str = " + ".join([lbl.split("|")[0].strip() for lbl in layer_labels]) if layer_labels else "Combined Layers"
            
            st.session_state.kiosk_locs[l_slot] = {
                "display_label": k_label if k_label else "Custom Region",
                "full_context": ctx_str, 
                "workspace_mask": list(w_ids),
                "source_layers": saved_layers, 
                "is_aggregate": True
            }
            st.toast(f"Slot {l_slot} Assigned!")
            st.rerun(scope="fragment")

        st.divider()

        # --- SUBSTANCE MAPPING ---
        st.subheader("Substance Mapping (P1 - P6)")
        p_cols = st.columns(2)
        clean_subs = [""] + sorted([s for s in subs_list if s])
        
        for i in range(1, 7):
            p_id = f"P{i}"
            
            if f"p_sel_{i}" not in st.session_state:
                st.session_state[f"p_sel_{i}"] = st.session_state.kiosk_pols[p_id]["data_name"]
            if f"p_lab_{i}" not in st.session_state:
                st.session_state[f"p_lab_{i}"] = st.session_state.kiosk_pols[p_id]["display_name"]

            with p_cols[0 if i <= 3 else 1]:
                st.markdown(f"**Pollutant {i}**")
                st.selectbox(f"Source ({p_id})", clean_subs, key=f"p_sel_{i}", on_change=sync_p_label, args=(i,))
                st.text_input(f"Label ({p_id})", key=f"p_lab_{i}")
                
                st.session_state.kiosk_pols[p_id]["data_name"] = st.session_state[f"p_sel_{i}"]
                st.session_state.kiosk_pols[p_id]["display_name"] = st.session_state[f"p_lab_{i}"]

        st.divider()

        # --- TIME CYCLE MAPPING ---
        st.subheader("Time Cycle Mapping (T1 - T6)")
        t_cols = st.columns(2)

        for i in range(1, 7):
            t_id = f"T{i}"

            if f"t_slider_{i}" not in st.session_state:
                saved_time = next((t["years"] for t in st.session_state.kiosk_times if t["id"] == t_id), [max_y-5, max_y])
                st.session_state[f"t_slider_{i}"] = tuple(saved_time)

            with t_cols[0 if i <= 3 else 1]:
                st.slider(f"Time Cycle ({t_id})", min_y, max_y, key=f"t_slider_{i}")
                
                for t_entry in st.session_state.kiosk_times:
                    if t_entry["id"] == t_id:
                        t_entry["years"] = list(st.session_state[f"t_slider_{i}"])

        st.button("⏱️ Auto Fill Time Cycles", use_container_width=True, on_click=auto_fill_time_cycles_callback, args=(min_y, max_y))

        st.divider()

        # --- EXPORT OPTIONS ---
        st.subheader("Export Options" if lang == "EN" else "Options d'exportation")
        c_exp1, c_exp2 = st.columns(2)
        export_local = c_exp1.checkbox("📥 Local Download (.zip)" if lang == "EN" else "📥 Téléchargement local (.zip)", value=True)
        export_server = c_exp2.checkbox("🚀 Deploy to Server (`./kiosk_app/Kiosk_Library`)" if lang == "EN" else "🚀 Déployer sur le serveur (`./kiosk_app/Kiosk_Library`)", value=False)

        # ZIP Build
        if st.button("⚙️ Generate Kiosk Library" if lang == "EN" else "⚙️ Générer la bibliothèque", use_container_width=True, type="secondary"):
            if not st.session_state.kiosk_locs:
                st.error("No locations assigned to slots." if lang == "EN" else "Aucun emplacement attribué.")
            else:
                from kiosk_automation import generate_kiosk_zip
                progress_bar = st.progress(0)
                status_box = st.empty()
                
                def build_progress_callback(current_step, total_steps, message):
                    percent = int((current_step / max(1, total_steps)) * 100)
                    progress_bar.progress(min(percent, 100))
                    status_box.info(f"⚙️ {message}...")
                
                try:
                    with st.spinner("Building Library..." if lang == "EN" else "Construction de la bibliothèque..."):
                        # Now returns actual bytes (getvalue())
                        z_bytes, missing_logs = generate_kiosk_zip(
                            raw_df, 
                            st.session_state.kiosk_locs, 
                            st.session_state.kiosk_pols, 
                            st.session_state.kiosk_times,
                            progress_callback=build_progress_callback
                        )

                    progress_bar.progress(100)
                    status_box.success("✅ Library Built!" if lang == "EN" else "✅ Bibliothèque générée !")
                    
                    if missing_logs:
                        st.warning("⚠️ **Missing Data Warning:** Some reports could not be generated because no data was recorded for the selected location, pollutant, and timeframe.")
                        with st.expander("Review Missing Reports Details" if lang == "EN" else "Voir les détails des rapports manquants"):
                            st.code("\n".join(missing_logs))
                    
                    # SERVER DEPLOYMENT
                    if export_server:
                        extract_path = "./kiosk_app/Kiosk_Library"
                        os.makedirs(extract_path, exist_ok=True)
                        with zipfile.ZipFile(io.BytesIO(z_bytes)) as zf:
                            zf.extractall(extract_path)
                        st.success(f"🚀 Extracted library to `{extract_path}`!" if lang == "EN" else f"🚀 Bibliothèque extraite vers `{extract_path}` !")

                    # LOCAL DOWNLOAD
                    if export_local:
                        st.download_button("📥 Download Kiosk ZIP" if lang == "EN" else "📥 Télécharger le ZIP", z_bytes, "Kiosk_Library.zip", use_container_width=True)
                    
                except Exception as e:
                    st.error(f"Generation Failed: {e}")