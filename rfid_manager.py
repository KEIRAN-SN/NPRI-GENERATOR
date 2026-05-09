import streamlit as st
import pandas as pd
import json
import os

# Use the same base directory logic as your existing app
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RFID_DB_FILE = os.path.join(BASE_DIR, "rfid_database.json")

def load_rfid_data():
    if os.path.exists(RFID_DB_FILE):
        with open(RFID_DB_FILE, "r") as f:
            return json.load(f)
    # Default structure if file doesn't exist
    return {
        "locations": {f"l{i}": {"name": f"L{i}", "tag": "", "note": ""} for i in range(1, 11)},
        "timeframes": {f"t{i}": {"name": f"T{i}", "tag": "", "note": ""} for i in range(1, 11)},
        "pollutants": {f"p{i}": {"name": f"P{i}", "tag": "", "note": ""} for i in range(1, 11)}
    }

def save_rfid_data(data):
    with open(RFID_DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

def render_rfid_manager():
    st.header("?? RFID Hardware Mapper")
    
    rfid_data = load_rfid_data()

    # Create layout columns
    col1, col2 = st.columns([0.4, 0.6])

    with col1:
        st.subheader("Edit Mapping")
        category = st.selectbox("Category", ["locations", "timeframes", "pollutants"], key="rfid_cat")
        slot_keys = list(rfid_data[category].keys())
        selected_slot = st.selectbox("Slot", slot_keys, format_func=lambda x: rfid_data[category][x]["name"])

        current_val = rfid_data[category][selected_slot]
        new_tag = st.text_input("RFID Tag ID", value=current_val["tag"], key="rfid_tag_input")
        new_note = st.text_area("Notes", value=current_val["note"], key="rfid_note_input")

        if st.button("Update Mapping", type="primary", use_container_width=True):
            rfid_data[category][selected_slot]["tag"] = new_tag
            rfid_data[category][selected_slot]["note"] = new_note
            save_rfid_data(rfid_data)
            st.success(f"Linked {new_tag} to {rfid_data[category][selected_slot]['name']}")
            st.rerun()

    with col2:
        st.subheader("Current Registry")
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
        st.dataframe(df_rfid, use_container_width=True, height=400)
        
        if st.download_button("Export Registry (CSV)", df_rfid.to_csv(index=False), "rfid_mapping.csv"):
            st.toast("Registry Exported")