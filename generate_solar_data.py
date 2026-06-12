"""
generate_solar_data.py
----------------------
Generates simulated solar farm IoT data for 30 days.
Produces: data/solar_data.csv

Run this once before running the ETL pipeline.
Author: Marvellous Isijola | EMIMO
Project: Hagital Bootcamp - Group 2 (Solo)
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

# Seed for reproducibility — same data every run
np.random.seed(42)

# ─── Config ─────────────────────────────────────────────────────────────────
START_DATE = datetime(2025, 1, 1)
DAYS = 30
PANELS = ["Panel_A", "Panel_B", "Panel_C"]
BATTERY_CAPACITY_KWH = 10.0  # max battery storage

# ─── Generate timestamps: one row per hour for 30 days ───────────────────────
timestamps = [START_DATE + timedelta(hours=h) for h in range(DAYS * 24)]

rows = []

battery_soc = 5.0  # start battery at 50% (5 kWh out of 10 kWh)

for ts in timestamps:
    hour = ts.hour

    # Solar irradiance follows a bell curve — peaks around noon
    # No generation at night (hours 0-5 and 19-23)
    if 6 <= hour <= 18:
        # Bell curve: peaks at hour 12, drops off at edges
        irradiance_factor = np.exp(-0.5 * ((hour - 12) / 3.5) ** 2)
        base_irradiance = 800 * irradiance_factor  # max ~800 W/m²
        # Add random weather noise
        irradiance = max(0, base_irradiance + np.random.normal(0, 50))
    else:
        irradiance = 0.0

    # Each panel has a slightly different efficiency (manufacturing variance)
    panel_efficiencies = {"Panel_A": 0.18, "Panel_B": 0.175, "Panel_C": 0.19}

    for panel in PANELS:
        # Power generated = irradiance × panel area (2m²) × efficiency
        panel_area = 2.0  # m²
        power_generated_kw = (irradiance * panel_area * panel_efficiencies[panel]) / 1000

        # Add small random noise to simulate real sensor readings
        power_generated_kw = max(0, power_generated_kw + np.random.normal(0, 0.005))

        # Household consumption — higher in morning (7-9) and evening (18-22)
        if 7 <= hour <= 9:
            consumption_kw = np.random.uniform(1.5, 2.5)  # breakfast peak
        elif 18 <= hour <= 22:
            consumption_kw = np.random.uniform(2.0, 3.5)  # evening peak
        elif 0 <= hour <= 5:
            consumption_kw = np.random.uniform(0.1, 0.3)  # night — minimal
        else:
            consumption_kw = np.random.uniform(0.5, 1.2)  # daytime base

        # Net energy = generated - consumed
        net_energy_kw = power_generated_kw - consumption_kw

        # Update battery SOC based on net energy
        # Charging when net > 0, discharging when net < 0
        battery_soc = battery_soc + net_energy_kw * 1  # 1 hour timestep
        battery_soc = max(0.0, min(BATTERY_CAPACITY_KWH, battery_soc))  # clamp 0–10 kWh

        rows.append({
            "timestamp": ts,
            "panel_id": panel,
            "irradiance_w_m2": round(irradiance, 2),
            "power_generated_kw": round(power_generated_kw, 4),
            "consumption_kw": round(consumption_kw, 4),
            "net_energy_kw": round(net_energy_kw, 4),
            "battery_soc_kwh": round(battery_soc, 4),
            "temperature_c": round(np.random.uniform(20, 38), 1),  # ambient temp
        })

# ─── Save to CSV ─────────────────────────────────────────────────────────────
os.makedirs("data", exist_ok=True)
df = pd.DataFrame(rows)
df.to_csv("data/solar_data.csv", index=False)

print(f"Generated {len(df)} rows of solar data.")
print(f"Date range: {df['timestamp'].min()} → {df['timestamp'].max()}")
print(f"Panels: {df['panel_id'].unique().tolist()}")
print(f"\nSample:\n{df.head(6).to_string()}")
print("\nCSV saved to: data/solar_data.csv")
