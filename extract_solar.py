"""
extract_solar.py
----------------
Extracts solar farm IoT data from CSV.
Validates schema and logs basic stats.

Run order: generate_solar_data.py → extract_solar.py → transform_solar.py → load_solar.py
Author: Marvellous Isijola | EMIMO
Project: Hagital Bootcamp - Group 2 (Solo)
"""

import pandas as pd
import os
import sys

# ─── Config ──────────────────────────────────────────────────────────────────
DATA_PATH = "data/solar_data.csv"

# Columns we expect in the raw CSV
EXPECTED_COLUMNS = [
    "timestamp", "panel_id", "irradiance_w_m2",
    "power_generated_kw", "consumption_kw",
    "net_energy_kw", "battery_soc_kwh", "temperature_c"
]


def extract_solar_data(filepath: str) -> pd.DataFrame:
    """
    Reads the solar CSV and performs basic validation.
    Returns a clean DataFrame if valid, exits with error if not.
    """
    # Check file exists before trying to read
    if not os.path.exists(filepath):
        print(f"[ERROR] File not found: {filepath}")
        print("Run generate_solar_data.py first.")
        sys.exit(1)

    print(f"[EXTRACT] Reading: {filepath}")
    df = pd.read_csv(filepath)

    # ── Schema check ─────────────────────────────────────────────────────────
    missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing_cols:
        print(f"[ERROR] Missing columns: {missing_cols}")
        sys.exit(1)

    # ── Type casting ─────────────────────────────────────────────────────────
    # Parse timestamp string to actual datetime object
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # ── Null check ───────────────────────────────────────────────────────────
    null_counts = df.isnull().sum()
    if null_counts.any():
        print("[WARNING] Null values found:")
        print(null_counts[null_counts > 0])
    else:
        print("[EXTRACT] No null values. Data is clean.")

    # ── Summary stats ────────────────────────────────────────────────────────
    print(f"\n[EXTRACT] Rows loaded   : {len(df):,}")
    print(f"[EXTRACT] Panels found  : {df['panel_id'].unique().tolist()}")
    print(f"[EXTRACT] Date range    : {df['timestamp'].min()} → {df['timestamp'].max()}")
    print(f"[EXTRACT] Avg generation: {df['power_generated_kw'].mean():.4f} kW")
    print(f"[EXTRACT] Avg consumption: {df['consumption_kw'].mean():.4f} kW")
    print(f"\n[EXTRACT] Sample (first 3 rows):")
    print(df.head(3).to_string())

    return df


if __name__ == "__main__":
    df = extract_solar_data(DATA_PATH)
    print("\n[EXTRACT] Extraction complete. Ready for transform.")
