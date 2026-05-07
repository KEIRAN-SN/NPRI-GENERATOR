import streamlit as st
import pandas as pd
import json
import os
import time

# --- UTILITY FUNCTIONS ---

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
        col_ex.download_button("📥 Export .json", ws_json, "npri_workspace.json", "application/json", use_container_width=True)
        
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

        # 3. ACTIVE LAYER LIST (With Restored Previews)
        st.subheader(t_layers)
        if not st.session_state.active_selections:
            st.info("No filters applied yet." if lang == "EN" else "Aucun filtre appliqué.")
        else:
            for idx, sel in enumerate(reversed(st.session_state.active_selections)):
                real_idx = len(st.session_state.active_selections) - 1 - idx
                with st.container(border=True):
                    icon = "➕" if sel["type"] == "Include" else "➖"
                    col_a, col_b = st.columns([0.8, 0.2])
                    col_a.markdown(f"**{icon} {sel['label']}**")
                    
                    ctx = sel.get("filter_context", {})
                    if ctx:
                        details = []
                        if ctx.get("name") not in ["All", "Tous"]: details.append(f"📍 {ctx['name']}")
                        if ctx.get("pollutant") not in ["All", "Tous"]: details.append(f"☁️ {ctx['pollutant']}")
                        if details: st.caption(" | ".join(details))

                    if col_b.button("🗑️", key=f"del_{real_idx}"):
                        st.session_state.active_selections.pop(real_idx)
                        st.rerun()

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

    with st.expander("📟 RFID Kiosk Configuration", expanded=False):
        slots = [f"L{i}" for i in range(1, 7)]
        cols = st.columns(6)
        for i, s_id in enumerate(slots):
            status = "✅" if s_id in st.session_state.kiosk_locs else "❌"
            cols[i].markdown(f"**{s_id}**\n{status}")

        if st.button("⚡ Bulk Fill Slots from Workspace", use_container_width=True, type="primary"):
            with st.spinner("Mapping..."):
                active_layers = [s for s in st.session_state.active_selections if s["type"] == "Include"]
                for i, layer in enumerate(active_layers[:6]):
                    s_id = f"L{i+1}"
                    st.session_state.kiosk_locs[s_id] = {
                        "display_label": layer["label"].split("|")[0].strip(),
                        "workspace_mask": list(layer["ids"]),
                        "is_aggregate": True
                    }
                time.sleep(0.2)
            st.rerun(scope="fragment")

        st.divider()

        # Slot Assignment
        c1, c2 = st.columns([0.3, 0.7])
        l_slot = c1.selectbox("Slot", slots)
        existing = st.session_state.kiosk_locs.get(l_slot, {})
        k_label = c2.text_input("Display Label", value=existing.get("display_label", ""))

        if st.button(f"Assign Workspace to {l_slot}", use_container_width=True):
            w_ids = set()
            for s in st.session_state.active_selections:
                if s["type"] == "Include": w_ids.update(s["ids"])
                else: w_ids.difference_update(s["ids"])
            
            st.session_state.kiosk_locs[l_slot] = {
                "display_label": k_label if k_label else "Custom Region",
                "workspace_mask": list(w_ids),
                "is_aggregate": True
            }
            st.toast(f"Slot {l_slot} Assigned!")
            st.rerun(scope="fragment")

        st.divider()

        # --- SUBSTANCE & TIME CYCLE MAPPING ---
        st.subheader("Substance & Time Cycle Mapping")
        p_cols = st.columns(2)
        clean_subs = [""] + sorted([s for s in subs_list if s])
        
        for i in range(1, 7):
            p_id, t_id = f"P{i}", f"T{i}"
            
            # Initialization Check
            if f"p_sel_{i}" not in st.session_state:
                st.session_state[f"p_sel_{i}"] = st.session_state.kiosk_pols[p_id]["data_name"]
            if f"p_lab_{i}" not in st.session_state:
                st.session_state[f"p_lab_{i}"] = st.session_state.kiosk_pols[p_id]["display_name"]
            if f"t_slider_{i}" not in st.session_state:
                saved_time = next((t["years"] for t in st.session_state.kiosk_times if t["id"] == t_id), [max_y-5, max_y])
                st.session_state[f"t_slider_{i}"] = tuple(saved_time)

            with p_cols[0 if i <= 3 else 1]:
                st.markdown(f"**Group {i}**")
                
                # We remove 'index=' and 'value=' to let the Session State 'key' handle the value.
                # This fixes the Duplicate Value error.
                st.selectbox(f"Source ({p_id})", clean_subs, key=f"p_sel_{i}")
                st.text_input(f"Label ({p_id})", key=f"p_lab_{i}")
                st.slider(f"Cycle ({t_id})", min_y, max_y, key=f"t_slider_{i}")
                
                # Sync logic back to master dictionaries
                st.session_state.kiosk_pols[p_id]["data_name"] = st.session_state[f"p_sel_{i}"]
                st.session_state.kiosk_pols[p_id]["display_name"] = st.session_state[f"p_lab_{i}"]
                for t_entry in st.session_state.kiosk_times:
                    if t_entry["id"] == t_id:
                        t_entry["years"] = list(st.session_state[f"t_slider_{i}"])

        st.divider()

        # ZIP Build
        if st.button("🚀 Generate Kiosk Library ZIP", use_container_width=True, type="secondary"):
            if not st.session_state.kiosk_locs:
                st.error("No locations assigned to slots.")
            else:
                from kiosk_automation import generate_kiosk_zip
                progress_bar = st.progress(0)
                status_box = st.empty()
                
                try:
                    with st.spinner("Building Library..."):
                        status_box.info("⚙️ Normalizing units and bundling reports...")
                        z_file = generate_kiosk_zip(raw_df, st.session_state.kiosk_locs, st.session_state.kiosk_pols, st.session_state.kiosk_times)
                        progress_bar.progress(100)
                    status_box.success("✅ Library Built!")
                    st.download_button("📥 Download Kiosk ZIP", z_file, "Kiosk_Library.zip", use_container_width=True)
                except Exception as e:
                    st.error(f"Generation Failed: {e}")