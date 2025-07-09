import os
import pandas as pd

def load_data_from_csv(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"{filepath} not found.")
    
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == ".csv":
        df = pd.read_csv(filepath)
    elif ext in [".xlsx", ".xls"]:
        df = pd.read_excel(filepath)
    else:
        raise ValueError("Unsupported file format. Use .csv or .xlsx")

    df.columns = [col.strip().lower() for col in df.columns]
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)

    # Derive 'status' column
    df['status'] = df['response_status_code'].apply(
        lambda x: 'Success' if str(x).startswith('2') else 'Failure'
    )

    return df