import io, zipfile
from generator import create_html_report
from data_engine import filter_by_radius

def generate_kiosk_zip(df, loc_map, pol_map, time_list, progress_callback=None):
    """Synchronized batch generator producing both EN and FR reports with missing data warnings."""
    zip_buffer = io.BytesIO()
    # Track items that return no data for the final report
    missing_data_log = []
    
    # Calculate total steps for the progress bar
    valid_pols = [p for p in pol_map.values() if str(p.get("data_name", "")).strip()]
    total_steps = len(loc_map) * len(valid_pols) * len(time_list)
    current_step = 0
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for l_id, l_info in loc_map.items():
            # 1. IDENTIFY BASE DATASET FOR THIS LOCATION
            if l_info.get("is_aggregate") and "workspace_mask" in l_info:
                loc_df = df[df["_uid"].isin(l_info["workspace_mask"])].copy()
            else:
                loc_df = df.copy()
                target_city = l_info.get("name", "All")
                rad_km = float(l_info.get("radius", 0))
                if target_city != "All":
                    if rad_km > 0:
                        c_row = df[df["City"] == target_city].dropna(subset=["Lat", "Lon"])
                        if not c_row.empty: 
                            loc_df = filter_by_radius(loc_df, float(c_row.iloc[0].Lat), float(c_row.iloc[0].Lon), rad_km)
                    else: 
                        loc_df = loc_df[loc_df["City"] == target_city]

                if l_info.get("comp") and l_info["comp"] != "All":
                    loc_df = loc_df[loc_df["Display_Company"] == l_info["comp"]]
                if l_info.get("fac") and l_info["fac"] != "All":
                    loc_df = loc_df[loc_df["Facility"] == l_info["fac"]]

            # ENFORCE THE LABEL: Ensure we use the label defined in the Kiosk Config
            # This prevents "Mining" or other filter-based labels from overriding the user input.
            final_location_label = l_info.get("display_label", "Unknown Location")

            # 2. GENERATE BILINGUAL REPORTS
            for p_id, p_info in pol_map.items():
                p_target_en = str(p_info.get("data_name", "")).strip()
                if not p_target_en: continue 

                # Retrieve French substance name from data
                match_row = df[df["Substance_EN"] == p_target_en].head(1)
                p_target_fr = match_row["Substance_FR"].values[0] if not match_row.empty else p_target_en

                for t_info in time_list:
                    current_step += 1
                    years = t_info["years"]
                    time_label = f"{years[0]}-{years[1]}"
                    
                    # Update progress bar
                    if progress_callback:
                        progress_callback(current_step, total_steps, f"Processing {final_location_label} - {p_target_en} ({time_label})")
                    
                    # --- Generate English Version ---
                    mask_en = (loc_df["Substance_EN"] == p_target_en) & (loc_df["Year"].between(years[0], years[1]))
                    f_df_en = loc_df[mask_en].copy()
                    
                    if not f_df_en.empty:
                        en_label = p_info["display_name"] if p_info.get("display_name") else p_target_en
                        html_en = create_html_report(
                            f_df_en, 
                            f_df_en["Quantity"].sum(), 
                            f_df_en["Units"].iloc[0], 
                            en_label,            
                            final_location_label, # Use the enforced label here
                            time_label,
                            lang="EN"            
                        )
                        zip_file.writestr(f"{l_id}_{p_id}_{t_info['id']}.html", html_en)
                    else:
                        missing_data_log.append(f"MISSING (EN): {final_location_label} | {p_target_en} | {time_label}")

                    # --- Generate French Version (_FR) ---
                    mask_fr = (loc_df["Substance_FR"] == p_target_fr) & (loc_df["Year"].between(years[0], years[1]))
                    f_df_fr = loc_df[mask_fr].copy()
                    
                    if not f_df_fr.empty:
                        html_fr = create_html_report(
                            f_df_fr, 
                            f_df_fr["Quantity"].sum(), 
                            f_df_fr["Units"].iloc[0], 
                            p_target_fr,         
                            final_location_label, # Use the enforced label here
                            time_label,
                            lang="FR"            
                        )
                        zip_file.writestr(f"{l_id}_{p_id}_{t_info['id']}_FR.html", html_fr)
                    else:
                        missing_data_log.append(f"MISSING (FR): {final_location_label} | {p_target_fr} | {time_label}")
        
        # 3. APPEND WARNING FILE IF DATA WAS MISSING
        if missing_data_log:
            warning_content = "NPRI GENERATION WARNING REPORT\n"
            warning_content += "==============================\n"
            warning_content += "The following report requests yielded no data and were not generated:\n\n"
            warning_content += "\n".join(missing_data_log)
            zip_file.writestr("WARNINGS_MISSING_DATA.txt", warning_content)
                        
    zip_buffer.seek(0)
    
    # Return both the zip buffer and the missing data log array
    return zip_buffer, missing_data_log