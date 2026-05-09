import streamlit as st
import json
import os
import pandas as pd

# This ensures the DB is always in the same folder as the script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "rfid_database.json")

def load_data():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {
        "locations": {f"l{i}": {"name": f"L{i}", "tag": "", "note": ""} for i in range(1, 11)},
        "timeframes": {f"t{i}": {"name": f"T{i}", "tag": "", "note": ""} for i in range(1, 11)},
        "pollutants": {f"p{i}": {"name": f"P{i}", "tag": "", "note": ""} for i in range(1, 11)}
    }

def save_data(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

# --- SIDEBAR: EXPORT OPTIONS ---
st.sidebar.header("📤 Export Data")

flattened_data = []
for cat, slots in data.items():
    for slot_id, info in slots.items():
        flattened_data.append({
            "Category": cat.capitalize(),
            "Slot": info["name"],
            "RFID_Tag": info["tag"],
            "Note": info["note"]
        })
df = pd.DataFrame(flattened_data)

# Save CSV to the script's root folder
if st.sidebar.button("Save as CSV to Root"):
    csv_path = os.path.join(BASE_DIR, 'rfid_export.csv')
    df.to_csv(csv_path, index=False)
    st.sidebar.success(f"Saved to {csv_path}")

# Save JSON to the script's root folder
if st.sidebar.button("Save raw JSON to Root"):
    json_path = os.path.join(BASE_DIR, 'config_export.json')
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=4)
    st.sidebar.success(f"Saved to {json_path}")

# --- MAIN UI ---
st.title("📡 RFID Database Mapper")

category = st.selectbox("Select Category", ["locations", "timeframes", "pollutants"])
slot_keys = list(data[category].keys())
selected_slot = st.selectbox("Select Slot", slot_keys, format_func=lambda x: data[category][x]["name"])

st.divider()
current_val = data[category][selected_slot]

new_tag = st.text_input("Scan RFID Tag Now", value=current_val["tag"])
new_note = st.text_area("Notes / Description", value=current_val["note"])

if st.button("Update Slot"):
    data[category][selected_slot]["tag"] = new_tag
    data[category][selected_slot]["note"] = new_note
    save_data(data)
    st.success(f"Saved {data[category][selected_slot]['name']}!")
    st.rerun()

st.divider()
st.subheader("Current Assignments")
st.dataframe(df)