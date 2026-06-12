"""
load_solar.py
-------------
Creates PostgreSQL tables and loads transformed solar farm data.
Also exports an Excel file with both sheets.

Tables created:
  - solar_readings   : hourly panel-level readings
  - solar_daily      : daily aggregates per panel

Run order: generate → extract → transform → load
Author: Marvellous Isijola | EMIMO
"""

import os
import sys

import pandas as pd
import psycopg2
from sqlalchemy import create_engine

sys.path.insert(0, os.path.dirname(__file__))
from extract_solar import extract_solar_data
from transform_solar import transform

# ─── Database config — update password if yours is different ─────────────────
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "solar_db",    # we'll create this database first
    "user": "postgres",
    "password": "yourpassword"  # ← change to your PostgreSQL password
}

DATA_PATH = "data/solar_data.csv"


def create_database_if_not_exists():
    """
    Connects to the default 'postgres' database and creates 'solar_db' if missing.
    PostgreSQL doesn't allow CREATE DATABASE inside a transaction, so we handle
    that by setting autocommit=True temporarily.
    """
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database="postgres",           # connect to default db first
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"]
        )
        conn.autocommit = True             # required for CREATE DATABASE
        cursor = conn.cursor()

        # Check if solar_db already exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'solar_db'")
        exists = cursor.fetchone()

        if not exists:
            cursor.execute("CREATE DATABASE solar_db")
            print("[LOAD] Database 'solar_db' created.")
        else:
            print("[LOAD] Database 'solar_db' already exists.")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"[ERROR] Could not create database: {e}")
        sys.exit(1)


def create_tables(conn):
    """
    Drops and recreates the two main tables.
    Using DROP + CREATE each run makes re-running the script safe.
    """
    cursor = conn.cursor()

    # Drop old tables if they exist (clean slate on each run)
    cursor.execute("DROP TABLE IF EXISTS solar_daily;")
    cursor.execute("DROP TABLE IF EXISTS solar_readings;")

    # ── solar_readings: one row per panel per hour ────────────────────────────
    cursor.execute("""
        CREATE TABLE solar_readings (
            id               SERIAL PRIMARY KEY,
            timestamp        TIMESTAMP NOT NULL,
            panel_id         VARCHAR(20) NOT NULL,
            irradiance_w_m2  NUMERIC(8, 2),
            power_generated_kw NUMERIC(8, 4),
            consumption_kw   NUMERIC(8, 4),
            net_energy_kw    NUMERIC(8, 4),
            battery_soc_kwh  NUMERIC(8, 4),
            battery_status   VARCHAR(15),
            efficiency_pct   NUMERIC(6, 2),
            peak_hour_flag   SMALLINT,
            temperature_c    NUMERIC(5, 1),
            hour             SMALLINT,
            date             DATE
        );
    """)

    # ── solar_daily: one row per panel per day ────────────────────────────────
    cursor.execute("""
        CREATE TABLE solar_daily (
            id                   SERIAL PRIMARY KEY,
            date                 DATE NOT NULL,
            panel_id             VARCHAR(20) NOT NULL,
            total_generated_kwh  NUMERIC(8, 4),
            total_consumed_kwh   NUMERIC(8, 4),
            net_energy_kwh       NUMERIC(8, 4),
            avg_efficiency_pct   NUMERIC(6, 2),
            avg_battery_soc_kwh  NUMERIC(8, 4),
            peak_hours_count     SMALLINT,
            avg_temperature_c    NUMERIC(5, 1)
        );
    """)

    conn.commit()
    cursor.close()
    print("[LOAD] Tables created: solar_readings, solar_daily")


def load_data(hourly_df: pd.DataFrame, daily_df: pd.DataFrame):
    """
    Uses SQLAlchemy to bulk-insert DataFrames into PostgreSQL.
    pandas .to_sql() with method='multi' is much faster than row-by-row inserts.
    """
    connection_string = (
        f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    engine = create_engine(connection_string)

    # Load hourly readings
    hourly_df.to_sql(
        "solar_readings",
        engine,
        if_exists="append",   # table already exists — just insert rows
        index=False,
        method="multi",       # batch inserts, faster than one-at-a-time
        chunksize=500
    )
    print(f"[LOAD] Inserted {len(hourly_df):,} rows into solar_readings")

    # Load daily summary
    daily_df.to_sql(
        "solar_daily",
        engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=500
    )
    print(f"[LOAD] Inserted {len(daily_df):,} rows into solar_daily")

    engine.dispose()


def verify_load(conn):
    """
    Quick sanity check — confirm row counts match what we loaded.
    """
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM solar_readings;")
    hourly_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM solar_daily;")
    daily_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT panel_id, ROUND(SUM(power_generated_kw)::numeric, 2) AS total_kwh
        FROM solar_readings
        GROUP BY panel_id
        ORDER BY panel_id;
    """)
    panel_totals = cursor.fetchall()

    print(f"\n[VERIFY] solar_readings rows : {hourly_count:,}")
    print(f"[VERIFY] solar_daily rows    : {daily_count:,}")
    print("[VERIFY] Total generation by panel:")
    for panel, total in panel_totals:
        print(f"         {panel}: {total} kWh")

    cursor.close()


def export_excel(hourly_df: pd.DataFrame, daily_df: pd.DataFrame):
    """
    Exports both DataFrames to a single Excel file with two sheets.
    This is the Excel deliverable required by the bootcamp.
    """
    output_path = "solar_output.xlsx"

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        hourly_df.to_excel(writer, sheet_name="Hourly_Readings", index=False)
        daily_df.to_excel(writer, sheet_name="Daily_Summary", index=False)

    print(f"\n[EXPORT] Excel saved: {output_path}")
    print(f"         Sheet 1: Hourly_Readings ({len(hourly_df)} rows)")
    print(f"         Sheet 2: Daily_Summary ({len(daily_df)} rows)")


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Step 1: Make sure the database exists
    create_database_if_not_exists()

    # Step 2: Connect to solar_db
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("[LOAD] Connected to solar_db")
    except Exception as e:
        print(f"[ERROR] Cannot connect to PostgreSQL: {e}")
        sys.exit(1)

    # Step 3: Create tables
    create_tables(conn)

    # Step 4: Run extract + transform
    raw_df = extract_solar_data(DATA_PATH)
    hourly_df, daily_df = transform(raw_df)

    # Step 5: Load into PostgreSQL
    load_data(hourly_df, daily_df)

    # Step 6: Verify
    verify_load(conn)

    # Step 7: Export Excel
    export_excel(hourly_df, daily_df)

    conn.close()
    print("\n[LOAD] Pipeline complete. solar_db is ready for Grafana.")
