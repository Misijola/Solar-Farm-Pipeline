"""
transform_solar.py
------------------
Transforms raw solar farm data into analysis-ready tables.

Transformations applied:
  1. efficiency_pct     — how much of available irradiance was converted
  2. battery_status     — Charging / Discharging / Idle
  3. peak_hour_flag     — marks peak solar hours (10am–2pm)
  4. daily_summary      — aggregated per panel per day
  5. hourly_aggregated  — cleaned hourly table ready for PostgreSQL

Run order: generate → extract → transform → load
Author: Marvellous Isijola | EMIMO
Project: Hagital Bootcamp - Group 2 (Solo)
"""

import pandas as pd
import sys
import os

# Import the extract function so we don't duplicate code
sys.path.insert(0, os.path.dirname(__file__))
from extract_solar import extract_solar_data

DATA_PATH = "data/solar_data.csv"

# ─── Theoretical max power per panel ─────────────────────────────────────────
# Panel area = 2 m², max irradiance = 1000 W/m² (STC standard)
# Max theoretical power = 1000 * 2 / 1000 = 2.0 kW
MAX_THEORETICAL_KW = 2.0


def transform(df: pd.DataFrame):
    """
    Takes the raw extracted DataFrame and returns two transformed DataFrames:
      - hourly_df   : row per panel per hour with all calculated fields
      - daily_df    : row per panel per day (aggregated)
    """

    print("\n[TRANSFORM] Starting transformations...")

    # ── 1. Efficiency % ───────────────────────────────────────────────────────
    # Efficiency = actual power generated ÷ theoretical max × 100
    # If irradiance is 0 (night), efficiency is 0 — avoid division by zero
    df["theoretical_max_kw"] = (df["irradiance_w_m2"] * 2.0) / 1000  # panel area = 2 m²

    df["efficiency_pct"] = df.apply(
        lambda row: (row["power_generated_kw"] / row["theoretical_max_kw"] * 100)
        if row["theoretical_max_kw"] > 0 else 0.0,
        axis=1
    )
    df["efficiency_pct"] = df["efficiency_pct"].round(2)

    # Cap efficiency at 100% (occasional numerical noise from simulation)
    df["efficiency_pct"] = df["efficiency_pct"].clip(0, 100)

    print("[TRANSFORM] ✓ efficiency_pct calculated")

    # ── 2. Battery status ─────────────────────────────────────────────────────
    # net_energy_kw > 0 means we generated more than consumed → battery charges
    # net_energy_kw < 0 means we consumed more than generated → battery discharges
    def classify_battery(net):
        if net > 0.05:     # small threshold to avoid floating-point noise
            return "Charging"
        elif net < -0.05:
            return "Discharging"
        else:
            return "Idle"

    df["battery_status"] = df["net_energy_kw"].apply(classify_battery)
    print("[TRANSFORM] ✓ battery_status classified")

    # ── 3. Peak hour flag ─────────────────────────────────────────────────────
    # Peak solar hours: 10am to 2pm (highest generation potential)
    df["hour"] = df["timestamp"].dt.hour
    df["peak_hour_flag"] = df["hour"].apply(lambda h: 1 if 10 <= h <= 14 else 0)
    print("[TRANSFORM] ✓ peak_hour_flag assigned")

    # ── 4. Time dimension columns (useful for SQL queries & Grafana) ──────────
    df["date"] = df["timestamp"].dt.date
    df["month"] = df["timestamp"].dt.month
    df["day_of_week"] = df["timestamp"].dt.day_name()

    # ── 5. Daily summary aggregation ─────────────────────────────────────────
    daily_df = df.groupby(["date", "panel_id"]).agg(
        total_generated_kwh=("power_generated_kw", "sum"),   # sum of hourly kW = kWh (1h intervals)
        total_consumed_kwh=("consumption_kw", "sum"),
        net_energy_kwh=("net_energy_kw", "sum"),
        avg_efficiency_pct=("efficiency_pct", "mean"),
        avg_battery_soc_kwh=("battery_soc_kwh", "mean"),
        peak_hours_count=("peak_hour_flag", "sum"),
        avg_temperature_c=("temperature_c", "mean"),
    ).reset_index()

    daily_df["avg_efficiency_pct"] = daily_df["avg_efficiency_pct"].round(2)
    daily_df["avg_battery_soc_kwh"] = daily_df["avg_battery_soc_kwh"].round(4)

    print("[TRANSFORM] ✓ daily_summary aggregated")

    # ── 6. Final column selection for hourly table ────────────────────────────
    # Keep only the columns we'll load into PostgreSQL
    hourly_df = df[[
        "timestamp", "panel_id", "irradiance_w_m2",
        "power_generated_kw", "consumption_kw", "net_energy_kw",
        "battery_soc_kwh", "battery_status", "efficiency_pct",
        "peak_hour_flag", "temperature_c", "hour", "date"
    ]].copy()

    # ── Print summaries ───────────────────────────────────────────────────────
    print(f"\n[TRANSFORM] Hourly table shape : {hourly_df.shape}")
    print(f"[TRANSFORM] Daily table shape  : {daily_df.shape}")

    print("\n[TRANSFORM] Battery status distribution:")
    print(df["battery_status"].value_counts().to_string())

    print("\n[TRANSFORM] Average efficiency by panel:")
    print(df.groupby("panel_id")["efficiency_pct"].mean().round(2).to_string())

    print("\n[TRANSFORM] Sample daily summary:")
    print(daily_df.head(6).to_string())

    return hourly_df, daily_df


if __name__ == "__main__":
    raw_df = extract_solar_data(DATA_PATH)
    hourly_df, daily_df = transform(raw_df)
    print("\n[TRANSFORM] Done. Ready for load_solar.py")
