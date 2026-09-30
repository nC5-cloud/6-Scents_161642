"""
Phase 1 feature extraction for ESP32 MQTT sessions.

ESP32 protocol:

    PURGE  ->  SAMPLE -> PURGE -> SAMPLE ...

Each valid PURGE -> SAMPLE pair is treated as one response cycle.

One CSV session = one ML sample.

No heater is used in Phase 1.
"""

from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# SETTINGS
# ============================================================

DATA_DIR = Path("data")
OUTPUT_FILE = Path("feature_matrix.csv")


# ============================================================
# REQUIRED RAW DATA COLUMNS
# ============================================================

REQUIRED_COLUMNS = [
    "timestamp_ms",
    "state",
    "ambient_temp",
    "ambient_hum",
    "voc_raw",
    "nox_raw",
    "gas_resistance",
    "label",
    "session_id",
    "compound",
]


# ============================================================
# HELPER
# ============================================================

def clean_numeric(series):
    return pd.to_numeric(series, errors="coerce")


# ============================================================
# EXTRACT ONE CYCLE
# ============================================================

def calculate_cycle_features(purge, sample):
    """
    Calculate response features from one PURGE -> SAMPLE cycle.
    """

    if len(purge) == 0 or len(sample) == 0:
        return None

    # --------------------------------------------------------
    # Baseline = mean of PURGE
    # --------------------------------------------------------

    bme_baseline = purge["gas_resistance"].mean()
    voc_baseline = purge["voc_raw"].mean()
    nox_baseline = purge["nox_raw"].mean()

    # --------------------------------------------------------
    # Strongest SAMPLE response
    # --------------------------------------------------------

    bme_peak = sample["gas_resistance"].min()
    voc_peak = sample["voc_raw"].min()
    nox_peak = sample["nox_raw"].min()

    # --------------------------------------------------------
    # Normalized response
    # --------------------------------------------------------

    if bme_baseline != 0:
        delta_bme = (
            (bme_baseline - bme_peak)
            / bme_baseline
        )
    else:
        delta_bme = 0.0

    if voc_baseline != 0:
        delta_voc = (
            (voc_baseline - voc_peak)
            / voc_baseline
        )
    else:
        delta_voc = 0.0

    if nox_baseline != 0:
        delta_nox = (
            (nox_baseline - nox_peak)
            / nox_baseline
        )
    else:
        delta_nox = 0.0

    # --------------------------------------------------------
    # Response timing
    # --------------------------------------------------------

    sample = sample.sort_values("timestamp_ms")

    bme_peak_idx = sample["gas_resistance"].idxmin()
    voc_peak_idx = sample["voc_raw"].idxmin()
    nox_peak_idx = sample["nox_raw"].idxmin()

    first_sample_time = sample["timestamp_ms"].iloc[0]

    bme_response_time = (
        sample.loc[bme_peak_idx, "timestamp_ms"]
        - first_sample_time
    )

    voc_response_time = (
        sample.loc[voc_peak_idx, "timestamp_ms"]
        - first_sample_time
    )

    nox_response_time = (
        sample.loc[nox_peak_idx, "timestamp_ms"]
        - first_sample_time
    )

    return {
        "delta_bme": delta_bme,
        "bme_response_time": bme_response_time,

        "delta_voc": delta_voc,
        "voc_response_time": voc_response_time,

        "delta_nox": delta_nox,
        "nox_response_time": nox_response_time,
    }


# ============================================================
# EXTRACT SESSION
# ============================================================

def extract_session_features(df):
    """
    Find valid PURGE -> SAMPLE cycles and aggregate them
    into one feature vector for the session.
    """

    # --------------------------------------------------------
    # Clean state
    # --------------------------------------------------------

    df = df.copy()

    df["state"] = (
        df["state"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    # --------------------------------------------------------
    # Convert numeric columns
    # --------------------------------------------------------

    sensor_columns = [
        "gas_resistance",
        "voc_raw",
        "nox_raw",
        "ambient_temp",
        "ambient_hum",
        "timestamp_ms",
    ]

    for column in sensor_columns:
        df[column] = clean_numeric(df[column])

    df = df.sort_values("timestamp_ms").reset_index(drop=True)

    # --------------------------------------------------------
    # Find PURGE -> SAMPLE cycles
    # --------------------------------------------------------

    cycles = []

    current_purge = []

    for _, row in df.iterrows():

        state = row["state"]

        if state == "PURGE":

            # Start/continue current purge period
            current_purge.append(row)

        elif state == "SAMPLE":

            # A SAMPLE is valid only if we have a preceding PURGE
            if current_purge:

                purge_df = pd.DataFrame(current_purge)
                sample_rows = [row]

                # Continue collecting SAMPLE rows
                # until the next PURGE.
                cycles.append(
                    (purge_df, sample_rows)
                )

                current_purge = []

            else:
                # Ignore SAMPLE data before first PURGE
                continue

    # --------------------------------------------------------
    # The above detects cycle starts.
    # Now rebuild proper contiguous PURGE -> SAMPLE blocks.
    # --------------------------------------------------------

    cycles = []

    purge_rows = []
    sample_rows = []
    in_sample = False

    for _, row in df.iterrows():

        state = row["state"]

        if state == "PURGE":

            if in_sample and purge_rows and sample_rows:
                cycles.append(
                    (
                        pd.DataFrame(purge_rows),
                        pd.DataFrame(sample_rows)
                    )
                )

            purge_rows = [row]
            sample_rows = []
            in_sample = False

        elif state == "SAMPLE":

            if purge_rows:
                sample_rows.append(row)
                in_sample = True

    # Add final cycle
    if purge_rows and sample_rows:
        cycles.append(
            (
                pd.DataFrame(purge_rows),
                pd.DataFrame(sample_rows)
            )
        )

    # --------------------------------------------------------
    # Check cycles
    # --------------------------------------------------------

    if not cycles:
        print(
            "WARNING: No valid PURGE -> SAMPLE cycles found."
        )
        return None

    print(f"  Valid cycles : {len(cycles)}")

    # --------------------------------------------------------
    # Calculate features for every cycle
    # --------------------------------------------------------

    cycle_features = []

    for purge, sample in cycles:

        features = calculate_cycle_features(
            purge,
            sample
        )

        if features is not None:
            cycle_features.append(features)

    if not cycle_features:
        return None

    cycle_df = pd.DataFrame(cycle_features)

    # --------------------------------------------------------
    # Aggregate cycles into ONE session
    #
    # Mean = typical response
    # Max  = strongest response
    # --------------------------------------------------------

    delta_bme = cycle_df["delta_bme"].mean()
    delta_bme_max = cycle_df["delta_bme"].max()

    delta_voc = cycle_df["delta_voc"].mean()
    delta_voc_max = cycle_df["delta_voc"].max()

    delta_nox = cycle_df["delta_nox"].mean()
    delta_nox_max = cycle_df["delta_nox"].max()

    bme_response_time = cycle_df["bme_response_time"].mean()
    voc_response_time = cycle_df["voc_response_time"].mean()
    nox_response_time = cycle_df["nox_response_time"].mean()

    # --------------------------------------------------------
    # VOC / NOx relationship
    # --------------------------------------------------------

    voc_nox_ratio = (
        delta_voc
        / (abs(delta_nox) + 1e-6)
    )

    # --------------------------------------------------------
    # Environmental information
    # --------------------------------------------------------

    mean_temperature = df["ambient_temp"].mean()
    mean_humidity = df["ambient_hum"].mean()

    # --------------------------------------------------------
    # Build ONE feature row
    # --------------------------------------------------------

    features = {

        "delta_bme688_res_ohms": delta_bme,
        "max_delta_bme688_res_ohms": delta_bme_max,
        "response_bme688_res_ohms_ms": bme_response_time,

        "delta_sgp41_sraw_voc": delta_voc,
        "max_delta_sgp41_sraw_voc": delta_voc_max,
        "response_sgp41_sraw_voc_ms": voc_response_time,

        "delta_sgp41_sraw_nox": delta_nox,
        "max_delta_sgp41_sraw_nox": delta_nox_max,
        "response_sgp41_sraw_nox_ms": nox_response_time,

        "voc_nox_ratio": voc_nox_ratio,

        "mean_ambient_temp": mean_temperature,
        "mean_ambient_hum": mean_humidity,

        "label": int(df["label"].iloc[0]),
        "session_id": df["session_id"].iloc[0],
        "compound": df["compound"].iloc[0],
    }

    return features


# ============================================================
# PROCESS ONE CSV
# ============================================================

def process_file(csv_file):

    print(f"\nProcessing: {csv_file.name}")

    df = pd.read_csv(csv_file)

    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing:
        print("ERROR: Missing columns:")
        print(missing)
        return None

    features = extract_session_features(df)

    if features is None:
        return None

    print(f"  Compound : {features['compound']}")
    print(f"  Label    : {features['label']}")

    print(
        f"  BME ΔR   : "
        f"{features['delta_bme688_res_ohms']:.4f}"
    )

    print(
        f"  VOC Δ    : "
        f"{features['delta_sgp41_sraw_voc']:.4f}"
    )

    print(
        f"  NOx Δ    : "
        f"{features['delta_sgp41_sraw_nox']:.4f}"
    )

    return features


# ============================================================
# MAIN
# ============================================================

def main():

    csv_files = sorted(DATA_DIR.glob("*.csv"))

    if not csv_files:

        print("No CSV files found in data/")
        return

    print("========================================")
    print("   PHASE 1 FEATURE EXTRACTION")
    print("========================================")

    print(f"Found {len(csv_files)} CSV file(s).")

    all_features = []

    for csv_file in csv_files:

        features = process_file(csv_file)

        if features is not None:
            all_features.append(features)

    if not all_features:

        print("\nNo valid sessions were processed.")
        return

    feature_df = pd.DataFrame(all_features)

    feature_df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print("\n========================================")
    print("FEATURE EXTRACTION COMPLETE")
    print("========================================")

    print(
        f"Sessions processed: "
        f"{len(feature_df)}"
    )

    print(
        f"Output: {OUTPUT_FILE}"
    )

    print("\nFeature matrix:")
    print(
        feature_df.to_string(index=False)
    )


if __name__ == "__main__":
    main()