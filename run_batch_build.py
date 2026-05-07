from data_engine import process_files
from kiosk_automation import generate_kiosk_library

if __name__ == "__main__":
    # 1. Load data once into memory
    df, msg = process_files("./data")
    
    if df is not None:
        # 2. Run the batch generator
        generate_kiosk_library(df, output_folder="kiosk_outputs")
    else:
        print(f"Data Load Error: {msg}")