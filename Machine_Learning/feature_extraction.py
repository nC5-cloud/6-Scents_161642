"""
Feature extraction for ESP32 e-nose sessions.

Protocol:
    PURGE -> SAMPLE -> PURGE -> SAMPLE ...

One CSV session is one ML sample. Each contiguous PURGE->SAMPLE
block is treated as one response cycle and the cycle features are
aggregated into one session-level feature vector.

The script works with real MQTT logger CSVs and the synthetic
telemetry produced by Synthetic.py.

Important:
- threat_alert is never used as an ML feature.
- session_id is kept only for grouping/traceability.
- compound is metadata, not an input feature.
"""

from pathlib import Path
import numpy as np
import pandas as pd

DATA_DIR = Path("data")
OUTPUT_FILE = Path("feature_matrix.csv")

REQUIRED_COLUMNS = [
    "timestamp_ms", "state", "ambient_temp", "ambient_hum",
    "voc_raw", "nox_raw", "gas_resistance",
    "label", "session_id", "compound",
]



def clean_numeric(series):
    return pd.to_numeric(series, errors="coerce")


def _normalized_delta(baseline, peak):
    if not np.isfinite(baseline) or baseline == 0 or not np.isfinite(peak):
        return 0.0
    return float((baseline - peak) / abs(baseline))


def _recovery_fraction(baseline, peak, end_value):
    """
    0 = no recovery from peak
    1 = returned to baseline
    Values are clipped for robustness.
    """
    denominator = baseline - peak
    if not np.isfinite(denominator) or abs(denominator) < 1e-12:
        return 0.0

    recovery = (end_value - peak) / denominator
    return float(np.clip(recovery, -1.0, 1.5))


def _safe_time_to_peak(sample, column):
    if sample.empty:
        return 0.0
    valid = sample[["timestamp_ms", column]].dropna()
    if valid.empty:
        return 0.0
    idx = valid[column].idxmin()
    return float(valid.loc[idx, "timestamp_ms"] - valid["timestamp_ms"].iloc[0])


def calculate_cycle_features(purge, sample):
    if purge.empty or sample.empty:
        return None

    purge = purge.sort_values("timestamp_ms")
    sample = sample.sort_values("timestamp_ms")

    bme_baseline = purge["gas_resistance"].mean()
    voc_baseline = purge["voc_raw"].mean()
    nox_baseline = purge["nox_raw"].mean()

    bme_peak = sample["gas_resistance"].min()
    voc_peak = sample["voc_raw"].min()
    nox_peak = sample["nox_raw"].min()

    bme_end = sample["gas_resistance"].iloc[-1]
    voc_end = sample["voc_raw"].iloc[-1]
    nox_end = sample["nox_raw"].iloc[-1]

    return {
        "delta_bme": _normalized_delta(bme_baseline, bme_peak),
        "bme_response_time": _safe_time_to_peak(sample, "gas_resistance"),
        "bme_recovery": _recovery_fraction(bme_baseline, bme_peak, bme_end),

        "delta_voc": _normalized_delta(voc_baseline, voc_peak),
        "voc_response_time": _safe_time_to_peak(sample, "voc_raw"),
        "voc_recovery": _recovery_fraction(voc_baseline, voc_peak, voc_end),

        "delta_nox": _normalized_delta(nox_baseline, nox_peak),
        "nox_response_time": _safe_time_to_peak(sample, "nox_raw"),
        "nox_recovery": _recovery_fraction(nox_baseline, nox_peak, nox_end),
    }


def _find_cycles(df):
    cycles = []
    purge_rows = []
    sample_rows = []
    in_sample = False

    for _, row in df.iterrows():
        state = row["state"]

        if state == "PURGE":
            if in_sample and purge_rows and sample_rows:
                cycles.append(
                    (pd.DataFrame(purge_rows), pd.DataFrame(sample_rows))
                )

            purge_rows = [row]
            sample_rows = []
            in_sample = False

        elif state == "SAMPLE":
            if purge_rows:
                sample_rows.append(row)
                in_sample = True

    if purge_rows and sample_rows:
        cycles.append(
            (pd.DataFrame(purge_rows), pd.DataFrame(sample_rows))
        )

    return cycles


def extract_session_features(df):
    df = df.copy()

    df["state"] = (
        df["state"].astype(str).str.upper().str.strip()
    )

    sensor_columns = [
        "gas_resistance", "voc_raw", "nox_raw",
        "ambient_temp", "ambient_hum", "timestamp_ms",
    ]

    for column in sensor_columns:
        df[column] = clean_numeric(df[column])

    df = df.dropna(
        subset=["timestamp_ms", "gas_resistance", "voc_raw", "nox_raw"]
    )
    df = df.sort_values("timestamp_ms").reset_index(drop=True)

    cycles = _find_cycles(df)

    if not cycles:
        print("  WARNING: No valid PURGE -> SAMPLE cycles found.")
        return None

    cycle_features = []
    for purge, sample in cycles:
        features = calculate_cycle_features(purge, sample)
        if features is not None:
            cycle_features.append(features)

    if not cycle_features:
        return None

    cycle_df = pd.DataFrame(cycle_features)

    delta_bme = cycle_df["delta_bme"].mean()
    delta_voc = cycle_df["delta_voc"].mean()
    delta_nox = cycle_df["delta_nox"].mean()

    features = {
        "delta_bme688_res_ohms": delta_bme,
        "max_delta_bme688_res_ohms": cycle_df["delta_bme"].max(),
        "response_bme688_res_ohms_ms": cycle_df["bme_response_time"].mean(),
        "recovery_bme688": cycle_df["bme_recovery"].mean(),

        "delta_sgp41_sraw_voc": delta_voc,
        "max_delta_sgp41_sraw_voc": cycle_df["delta_voc"].max(),
        "response_sgp41_sraw_voc_ms": cycle_df["voc_response_time"].mean(),
        "recovery_sgp41_voc": cycle_df["voc_recovery"].mean(),

        "delta_sgp41_sraw_nox": delta_nox,
        "max_delta_sgp41_sraw_nox": cycle_df["delta_nox"].max(),
        "response_sgp41_sraw_nox_ms": cycle_df["nox_response_time"].mean(),
        "recovery_sgp41_nox": cycle_df["nox_recovery"].mean(),

        "voc_nox_ratio": delta_voc / (abs(delta_nox) + 1e-6),

        "mean_ambient_temp": df["ambient_temp"].mean(),
        "mean_ambient_hum": df["ambient_hum"].mean(),
        "std_ambient_temp": df["ambient_temp"].std(ddof=0),
        "std_ambient_hum": df["ambient_hum"].std(ddof=0),

        "cycle_count": len(cycle_features),

        "label": int(df["label"].iloc[0]),
        "session_id": str(df["session_id"].iloc[0]),
        "compound": str(df["compound"].iloc[0]),
    }

    # Heater metadata is traceability metadata, not an ML input here.
    if "heater_profile" in df.columns:
        values = df["heater_profile"].dropna().astype(str)
        features["heater_profile"] = (
            values.mode().iloc[0] if not values.empty else "ambient"
        )
    else:
        features["heater_profile"] = "ambient"

    for heater_col in ["heater_temp_c", "bme_heater_temp_c"]:
        if heater_col in df.columns:
            numeric = clean_numeric(df[heater_col]).dropna()
            if not numeric.empty:
                features["heater_temp_c"] = float(numeric.mean())
                break
    else:
        features["heater_temp_c"] = np.nan

    return features


def process_file(csv_file):
    print(f"\nProcessing: {csv_file.name}")

    try:
        df = pd.read_csv(csv_file)
    except Exception as error:
        print(f"  ERROR reading file: {error}")
        return None

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        print(f"  ERROR missing columns: {missing}")
        return None

    features = extract_session_features(df)
    if features is None:
        return None

    print(
        f"  Compound={features['compound']} | "
        f"Label={features['label']} | "
        f"Cycles={features['cycle_count']} | "
        f"Heater={features['heater_profile']}"
    )
    return features


def main():
    csv_files = sorted(
        p for p in DATA_DIR.glob("*.csv")
        if p.name != OUTPUT_FILE.name
    )

    if not csv_files:
        print("No raw session CSV files found in data/")
        return

    print("========================================")
    print("   E-NOSE FEATURE EXTRACTION")
    print("========================================")
    print(f"Found {len(csv_files)} raw session file(s).")

    all_features = []

    for csv_file in csv_files:
        features = process_file(csv_file)
        if features is not None:
            all_features.append(features)

    if not all_features:
        print("\nNo valid sessions were processed.")
        return

    feature_df = pd.DataFrame(all_features)

    # Stable, readable column order.
    ordered = [
        "delta_bme688_res_ohms",
        "max_delta_bme688_res_ohms",
        "response_bme688_res_ohms_ms",
        "recovery_bme688",
        "delta_sgp41_sraw_voc",
        "max_delta_sgp41_sraw_voc",
        "response_sgp41_sraw_voc_ms",
        "recovery_sgp41_voc",
        "delta_sgp41_sraw_nox",
        "max_delta_sgp41_sraw_nox",
        "response_sgp41_sraw_nox_ms",
        "recovery_sgp41_nox",
        "voc_nox_ratio",
        "mean_ambient_temp",
        "mean_ambient_hum",
        "std_ambient_temp",
        "std_ambient_hum",
        "cycle_count",
        "label",
        "session_id",
        "compound",
        "heater_profile",
        "heater_temp_c",
    ]

    feature_df = feature_df[
        [c for c in ordered if c in feature_df.columns]
    ]

    feature_df.to_csv(OUTPUT_FILE, index=False)

    print("\n========================================")
    print("FEATURE EXTRACTION COMPLETE")
    print("========================================")
    print(f"Sessions processed: {len(feature_df)}")
    print(f"Output: {OUTPUT_FILE}")
    print("\nClass counts:")
    print(feature_df["label"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
