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

def sync_p_label(idx):
    """Updates the pollutant label field when the source substance is changed."""
    st.session_state[f"p_lab_{idx}"] = st.session_state[f"p_sel_{idx}"]

def auto_fill_time_cycles_callback(min_y, max_y):
    """Calculates and updates time cycle sliders evenly (run as a callback to avoid Streamlit API Exception)."""
    span = max_y - min_y + 1
    step = span / 6.0
    
    for i in range(6):
        start_yr = min_y + int(round(i * step))
        end_yr = min_y + int(round((i + 1) * step)) - 1
        
        # Ensure start and end don't overlap wrongly
        end_yr = max(start_yr, end_yr)
        
        # Make sure the last block extends perfectly to the maximum year
        if i == 5:
            end_yr = max_y
        
        st.session_state[f"t_slider_{i+1}"] = (start_yr, end_yr)
        # We don't need to manually sync to kiosk_times here because the sliders 
        # reading these new values will handle the sync dynamically when they render.


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
        cols = st.columns(3) # 3-column layout for detailed slot view
        
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
                    
                    # Split Action Buttons across the bottom of the card
                    act_c1, act_c2 = st.columns(2)
                    
                    # Edit / Reload into workspace button
                    if act_c1.button("✏️", key=f"edit_{s_id}", help=f"Edit {s_id}", use_container_width=True):
                        if "source_layers" in loc:
                            # Restore layers back to active_selections
                            st.session_state.active_selections = []
                            for layer in loc["source_layers"]:
                                restored = layer.copy()
                                restored["ids"] = set(restored["ids"])
                                st.session_state.active_selections.append(restored)
                            st.toast(f"Loaded {s_id} back into Workspace!")
                            st.rerun() # Full rerun to update workspace manager UI
                        else:
                            st.toast("No source data available for this slot.")

                    # Delete button
                    if act_c2.button("🗑️", key=f"clr_{s_id}", help=f"Clear {s_id}", use_container_width=True):
                        del st.session_state.kiosk_locs[s_id]
                        st.rerun(scope="fragment")
                        
                else:
                    st.markdown(f"**{s_id}** ❌")
                    st.markdown("**Empty**")
                    st.caption("No data assigned")
                    st.caption("&nbsp;") # Spacing to somewhat match height
                    st.caption("&nbsp;")

        if st.button("⚡ Bulk Fill Slots from Workspace", use_container_width=True, type="primary"):
            with st.spinner("Mapping..."):
                active_layers = [s for s in st.session_state.active_selections if s["type"] == "Include"]
                for i, layer in enumerate(active_layers[:6]):
                    s_id = f"L{i+1}"
                    # Prepare serializable layer
                    s_layer = layer.copy()
                    s_layer["ids"] = list(s_layer["ids"])

                    st.session_state.kiosk_locs[s_id] = {
                        "display_label": layer["label"].split("|")[0].strip(),
                        "full_context": layer["label"], # Saved full context for UI display
                        "workspace_mask": list(layer["ids"]),
                        "source_layers": [s_layer], # Store original layer for editing
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
            layer_labels = []
            saved_layers = []
            
            for s in st.session_state.active_selections:
                # Store serializable version of the layer for future editing
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
                "full_context": ctx_str, # Saved context for UI display
                "workspace_mask": list(w_ids),
                "source_layers": saved_layers, # Store original layers for editing
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
            
            # Initialization Check for Pollutants
            if f"p_sel_{i}" not in st.session_state:
                st.session_state[f"p_sel_{i}"] = st.session_state.kiosk_pols[p_id]["data_name"]
            if f"p_lab_{i}" not in st.session_state:
                st.session_state[f"p_lab_{i}"] = st.session_state.kiosk_pols[p_id]["display_name"]

            with p_cols[0 if i <= 3 else 1]:
                st.markdown(f"**Pollutant {i}**")
                
                st.selectbox(
                    f"Source ({p_id})", 
                    clean_subs, 
                    key=f"p_sel_{i}",
                    on_change=sync_p_label,
                    args=(i,)
                )
                
                st.text_input(f"Label ({p_id})", key=f"p_lab_{i}")
                
                # Sync logic back to master dictionaries
                st.session_state.kiosk_pols[p_id]["data_name"] = st.session_state[f"p_sel_{i}"]
                st.session_state.kiosk_pols[p_id]["display_name"] = st.session_state[f"p_lab_{i}"]

        st.divider()

        # --- TIME CYCLE MAPPING ---
        st.subheader("Time Cycle Mapping (T1 - T6)")
        t_cols = st.columns(2)

        for i in range(1, 7):
            t_id = f"T{i}"

            # Initialization Check for Times
            if f"t_slider_{i}" not in st.session_state:
                saved_time = next((t["years"] for t in st.session_state.kiosk_times if t["id"] == t_id), [max_y-5, max_y])
                st.session_state[f"t_slider_{i}"] = tuple(saved_time)

            with t_cols[0 if i <= 3 else 1]:
                st.slider(f"Time Cycle ({t_id})", min_y, max_y, key=f"t_slider_{i}")
                
                # Sync logic back to master dictionaries
                for t_entry in st.session_state.kiosk_times:
                    if t_entry["id"] == t_id:
                        t_entry["years"] = list(st.session_state[f"t_slider_{i}"])

        # Auto Fill Button for Time Cycles - USING CALLBACK
        st.button(
            "⏱️ Auto Fill Time Cycles", 
            use_container_width=True,
            on_click=auto_fill_time_cycles_callback,
            args=(min_y, max_y)
        )

        st.divider()

        # ZIP Build
        if st.button("🚀 Generate Kiosk Library ZIP", use_container_width=True, type="secondary"):
            if not st.session_state.kiosk_locs:
                st.error("No locations assigned to slots.")
            else:
                from kiosk_automation import generate_kiosk_zip
                progress_bar = st.progress(0)
                status_box = st.empty()
                
                # Setup callback for dynamic updates
                def build_progress_callback(current_step, total_steps, message):
                    percent = int((current_step / max(1, total_steps)) * 100)
                    progress_bar.progress(min(percent, 100))
                    status_box.info(f"⚙️ {message}...")
                
                try:
                    with st.spinner("Building Library..."):
                        # Passing the callback to the generator
                        result = generate_kiosk_zip(
                            raw_df, 
                            st.session_state.kiosk_locs, 
                            st.session_state.kiosk_pols, 
                            st.session_state.kiosk_times,
                            progress_callback=build_progress_callback
                        )
                        
                        # Unpack results securely
                        if isinstance(result, tuple):
                            z_file, missing_logs = result
                        else:
                            z_file = result
                            missing_logs = []

                    progress_bar.progress(100)
                    status_box.success("✅ Library Built!")
                    
                    # Display Warnings if missing data exists
                    if missing_logs:
                        st.warning("⚠️ **Missing Data Warning:** Some reports could not be generated because no data was recorded for the selected location, pollutant, and timeframe.")
                        with st.expander("Review Missing Reports Details"):
                            st.code("\n".join(missing_logs))
                    
                    st.download_button("📥 Download Kiosk ZIP", z_file, "Kiosk_Library.zip", use_container_width=True)
                    
                except TypeError as e:
                    if "progress_callback" in str(e):
                        st.error("⚠️ Setup needed: You must update `generate_kiosk_zip` in `kiosk_automation.py` to accept the `progress_callback` argument!")
                    else:
                        st.error(f"Generation Failed: {e}")
                except Exception as e:
                    st.error(f"Generation Failed: {e}")