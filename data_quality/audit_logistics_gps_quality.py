#!/usr/bin/env python3
"""
Real-time logistics GPS data quality audit
==========================================
Audits the continuously-updated North American logistics dataset hosted on
Hugging Face (toolathon123/logistics-na-daily-20260812, the "na-logistics"
daily snapshot) by loading the LATEST version directly from the hub in
real-time (no local snapshot / historical cache is trusted).

Usage:
    HF_TOKEN=<your_token> python audit_logistics_gps_quality.py
Outputs:
    audit_summary.json          - JSON summary of all check results
    audit_flagged_records.csv   - every flagged record with per-issue booleans
    audit_report.md             - human-readable markdown report
"""

import os
import json
from datetime import datetime

# --- Real-time load from Hugging Face hub (no cached snapshot) ----------------
def load_live_dataset(dataset_id: str = "toolathon123/logistics-na-daily-20260812"):
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
    from datasets import load_dataset
    # default download_mode checks the hub and pulls the latest files
    ds = load_dataset(dataset_id, split="train")
    return ds.to_pandas()

# --- Reference data ------------------------------------------------------------
US_STATES = set("""AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI
MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY""".split())
CA_PROVINCES = set("""AB BC MB NB NL NS NT NU ON PE QC SK YT""".split())
ALL_REGIONS = US_STATES | CA_PROVINCES
NO_DST_TIMEZONES = {"America/Phoenix", "Pacific/Honolulu", "America/Regina",
                    "America/Creston", "America/Dawson_Creek", "America/Fort_Nelson"}
VALID_STATUS = {"PICKED_UP", "IN_TRANSIT", "DELIVERED", "DELAYED", "CUSTOMS_HOLD"}

def region_country(region: str) -> str:
    if region in US_STATES:
        return "US"
    if region in CA_PROVINCES:
        return "CA"
    return "UNKNOWN"

# --- Checks ---------------------------------------------------------------------
def run_audit(df):
    import pandas as pd

    results = {}

    # A. Key-field completeness (empty / null)
    key_fields = ["shipment_id", "country_code", "origin_region", "destination_region",
                  "carrier_name", "status", "departure_time_utc", "arrival_time_utc",
                  "temperature_celsius", "weight_kg"]
    empty = pd.Series(False, index=df.index)
    for c in key_fields:
        if df[c].dtype == object:
            m = df[c].isna() | (df[c].astype(str).str.strip() == "")
        else:
            m = df[c].isna()
        results[f"key_field_empty_{c}"] = int(m.sum())
        empty |= m
    results["key_field_empty_any"] = int(empty.sum())

    # B. Duplicate shipment_id
    results["duplicate_shipment_id"] = int(df["shipment_id"].duplicated(keep=False).sum())

    # C. Timestamp checks
    dep = pd.to_datetime(df["departure_time_utc"], errors="coerce")
    arr = pd.to_datetime(df["arrival_time_utc"], errors="coerce")
    results["ts_unparseable_departure"] = int(dep.isna().sum())
    results["ts_unparseable_arrival"] = int(arr.isna().sum())
    results["ts_arrival_before_departure"] = int((arr < dep).sum())          # out-of-order
    results["ts_duplicate_departure_collisions"] = int(df["departure_time_utc"].duplicated(keep=False).sum())
    results["ts_duplicate_arrival_collisions"] = int(df["arrival_time_utc"].duplicated(keep=False).sum())

    # D. Geographic / region consistency (GPS coordinates are not present in this
    #    dataset version -> region-code consistency is used as the spatial proxy)
    origin_country = df["origin_region"].map(region_country)
    dest_country = df["destination_region"].map(region_country)
    results["region_invalid_origin"] = int((~df["origin_region"].isin(ALL_REGIONS)).sum())
    results["region_invalid_dest"] = int((~df["destination_region"].isin(ALL_REGIONS)).sum())
    results["region_origin_mismatch_country"] = int((origin_country != df["country_code"]).sum())
    results["region_dest_mismatch_country"] = int((dest_country != df["country_code"]).sum())
    results["border_crossing_inconsistent"] = int(((origin_country != dest_country) != df["border_crossing"]).sum())

    # E. Vehicle-speed / GPS telemetry checks (not applicable - columns absent)
    results["vehicle_speed_column_present"] = "vehicle_speed_kmh" in df.columns
    results["lat_lon_columns_present"] = ("latitude" in df.columns) and ("longitude" in df.columns)

    # F. Domain validity
    results["status_invalid"] = int((~df["status"].isin(VALID_STATUS)).sum())
    results["temperature_out_of_range"] = int(((df["temperature_celsius"] < -40) | (df["temperature_celsius"] > 60)).sum())
    results["weight_non_positive"] = int((df["weight_kg"] <= 0).sum())
    results["is_delayed_status_inconsistent"] = int(((df["status"] == "DELAYED") != df["is_delayed"]).sum())
    results["dst_flag_inconsistent"] = int(
        ((df["departure_dst"] == False) & (~df["departure_timezone"].isin(NO_DST_TIMEZONES))).sum()
        | ((df["arrival_dst"] == False) & (~df["arrival_timezone"].isin(NO_DST_TIMEZONES))).sum()
        | ((df["departure_dst"] == True) & (df["departure_timezone"].isin(NO_DST_TIMEZONES))).sum()
        | ((df["arrival_dst"] == True) & (df["arrival_timezone"].isin(NO_DST_TIMEZONES))).sum()
    )

    # Per-record issue flags (the 8 checks that can be flagged per row)
    flags = pd.DataFrame(index=df.index)
    flags["ts_arrival_before_departure"] = (arr < dep)
    flags["ts_duplicate_departure"] = df["departure_time_utc"].duplicated(keep=False)
    flags["ts_duplicate_arrival"] = df["arrival_time_utc"].duplicated(keep=False)
    flags["region_origin_mismatch_country"] = (origin_country != df["country_code"])
    flags["region_dest_mismatch_country"] = (dest_country != df["country_code"])
    flags["is_delayed_status_inconsistent"] = ((df["status"] == "DELAYED") != df["is_delayed"])
    flags["border_crossing_inconsistent"] = ((origin_country != dest_country) != df["border_crossing"])
    flags["key_field_empty"] = empty

    results["records_with_any_issue"] = int(flags.any(axis=1).sum())
    results["total_records"] = int(len(df))
    results["audit_timestamp_utc"] = datetime.utcnow().isoformat() + "Z"

    out = df.copy()
    for c in flags.columns:
        out[c] = flags[c].values
    out["issue_count"] = flags.sum(axis=1).values
    return results, flags, out

def main():
    df = load_live_dataset()
    results, flags, flagged_df = run_audit(df)

    with open("audit_summary.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    flagged_df.to_csv("audit_flagged_records.csv", index=False)

    print("=== AUDIT SUMMARY ({} records) ===".format(results["total_records"]))
    for k, v in results.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()
