import pandas as pd
import numpy as np
import os
import glob
import streamlit as st

def haversine(lat1, lon1, lat2, lon2):
    """Vectorized haversine calculation for high-performance distance filtering."""
    r = 6371 # Earth's radius in km
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi, dlambda = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    return 2 * r * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

def filter_by_radius(df, lat, lon, radius_km):
    """Fast bounding-box filter followed by precise distance check."""
    if radius_km <= 0:
        return df[df["Lat"] == lat] 
        
    lat_margin = radius_km / 111.0
    cos_val = np.cos(np.radians(lat))
    lon_margin = radius_km / (111.0 * cos_val) if abs(cos_val) > 0.0001 else 180.0
    
    # 1. Broad Bounding Box (Fast)
    mask = (df["Lat"].between(lat - lat_margin, lat + lat_margin)) & \
           (df["Lon"].between(lon - lon_margin, lon + lon_margin))
    
    subset = df[mask].copy()
    if subset.empty:
        return subset
        
    # 2. Vectorized Haversine (Precise)
    subset["dist"] = haversine(lat, lon, subset["Lat"].values, subset["Lon"].values)
    return subset[subset["dist"] <= radius_km]

@st.cache_data
def normalize_quantity(df):
    """
    Standardizes all emissions to Tonnes. 
    This is the ONLY place where conversion math should exist.
    """
    if df.empty:
        return df
    
    df = df.copy()

    def convert_to_tonnes(row):
        # Clean the unit string
        unit = str(row.get('Units', 'tonnes')).lower().strip()
        qty = float(row.get('Quantity', 0))
        
        # Exact matching to prevent partial string errors
        if unit in ['kg', 'kilograms', 'kilogrammes']:
            return qty / 1000
        if unit in ['g', 'grams', 'grammes']:
            return qty / 1000000
        if unit in ['ug', 'micrograms']:
            return qty / 1000000000
        # Default/Fallback: assume it's already in tonnes
        return qty 

    df['Quantity_Tonnes'] = df.apply(convert_to_tonnes, axis=1)
    return df

@st.cache_data(show_spinner=False, ttl=3600)
def process_files(path):
    """Loads CSVs, merges geometry, and captures the Units column for math integrity."""
    if not os.path.exists(path):
        return None, "Path not found."

    cache_file = os.path.join(path, "processed_cache.parquet")
    if os.path.exists(cache_file):
        try:
            return pd.read_parquet(cache_file), "Loaded from Cache (Fast)"
        except:
            pass 

    all_files = glob.glob(os.path.join(path, "*.csv"))
    if not all_files: return None, "No CSV files found."
    
    data_frames, geo_df = [], None
    
    for f in all_files:
        try:
            sample = pd.read_csv(f, nrows=0, encoding="latin1")
            cols = sample.columns.tolist()
            
            # A. GEOMETRY PARSING
            if any("Latitude" in c for c in cols):
                geo_df = pd.read_csv(f, encoding="latin1", usecols=["NPRI ID / ID INRP", "City / Ville", "Latitude / Latitude", "Longitude / Longitude"])
                geo_df.columns = ["NPRI_ID", "City", "Lat", "Lon"]
                geo_df["NPRI_ID"] = geo_df["NPRI_ID"].astype(str)
                geo_df = geo_df.drop_duplicates(subset="NPRI_ID")
            
            # B. DATA FILE PARSING
            elif any("Reporting_Year" in c for c in cols):
                def get_col(candidates):
                    for cand in candidates:
                        match = next((c for c in cols if cand in c), None)
                        if match: return match
                    return None

                col_map = {}
                c_year = get_col(["Reporting_Year"])
                c_id = get_col(["NPRI_ID", "NPRI ID"])
                c_comp = get_col(["Company_Name", "Company Name"])
                c_fac = get_col(["Facility_Name", "Facility Name"])
                c_prov = get_col(["PROVINCE", "Province"])
                c_sub_en = get_col(["Substance Name (English)", "Substance_Name_en"])
                c_sub_fr = get_col(["Substance Name (French)", "Substance_Name_fr"])
                c_qty = get_col(["Quantity", "Total_Quantity", "Value"])
                c_units = get_col(["Unit", "Units", "UNIT"]) # Added Units mapping
                
                if c_year: col_map[c_year] = "Year"
                if c_id: col_map[c_id] = "NPRI_ID"
                if c_comp: col_map[c_comp] = "Company"
                if c_fac: col_map[c_fac] = "Facility"
                if c_prov: col_map[c_prov] = "Province"
                if c_sub_en: col_map[c_sub_en] = "Substance_EN"
                if c_sub_fr: col_map[c_sub_fr] = "Substance_FR"
                if c_qty: col_map[c_qty] = "Quantity"
                if c_units: col_map[c_units] = "Units"

                if col_map:
                    tmp = pd.read_csv(f, encoding="latin1", usecols=list(col_map.keys()))
                    tmp = tmp.rename(columns=col_map)
                    tmp["NPRI_ID"] = tmp["NPRI_ID"].astype(str)
                    data_frames.append(tmp)
        except Exception as e:
            continue
        
    if not data_frames: return None, "No valid data found."
    
    df = pd.concat(data_frames, ignore_index=True)
    if geo_df is not None: 
        df = pd.merge(df, geo_df, on="NPRI_ID", how="left")
    
    # Create Display Company Name
    if "Year" in df.columns and "Company" in df.columns:
        latest_names = df.sort_values("Year", ascending=False).drop_duplicates("NPRI_ID")
        id_to_latest_name = dict(zip(latest_names["NPRI_ID"], latest_names["Company"]))
        df["Display_Company"] = df["NPRI_ID"].map(id_to_latest_name)
    else:
        df["Display_Company"] = df["Company"] if "Company" in df.columns else "Unknown"

    df["Display_Company"] = df["Display_Company"].fillna("Unknown")
    df["Substance_EN"] = df.get("Substance_EN", pd.Series(["Unknown"]*len(df))).fillna("Unknown")
    df["Substance_FR"] = df.get("Substance_FR", pd.Series(["Unknown"]*len(df))).fillna("Unknown")
    df["Units"] = df.get("Units", pd.Series(["tonnes"]*len(df))).fillna("tonnes") # Default to tonnes
    df["_uid"] = df.index.astype(str)

    try:
        df.to_parquet(cache_file, index=False)
    except:
        pass

    return df, "Data Synced"