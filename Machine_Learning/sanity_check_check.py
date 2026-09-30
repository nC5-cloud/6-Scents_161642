"""
Sanity-check data generator.

This file creates fake RAW ESP32-style telemetry, not feature rows.
It is intended only to validate the pipeline:

    sanity_check_check.py
        -> feature_extraction.py
        -> trainer_classifier.py

It must never be presented as real chemical measurements.
"""

from pathlib import Path
import numpy as np
import pandas as pd

DATA_DIR = Path("data")
RUN_SECONDS = 60
SAMPLE_INTERVAL_SECONDS = 1
PURGE_SECONDS = 4
SAMPLE_SECONDS = 6
CYCLE_SECONDS = PURGE_SECONDS + SAMPLE_SECONDS
RANDOM_SEED = 7

COMPOUNDS = {
    "acetone_proxy": (1, 0.32, 0.55, 0.20),
    "h2o2_proxy": (1, 0.48, 0.25, 0.50),
    "ipa_proxy": (1, 0.28, 0.62, 0.12),
    "perfume": (0, 0.35, 0.48, 0.10),
    "coffee": (0, 0.22, 0.30, 0.38),
    "hand_sanitizer": (0, 0.42, 0.58, 0.16),
}


def generate_session(session_id, compound, rng):
    label, bme_strength, voc_strength, nox_strength = COMPOUNDS[compound]

    bme_base = rng.normal(100000, 9000)
    voc_base = rng.normal(30000, 1500)
    nox_base = rng.normal(10000, 700)

    temp_base = rng.uniform(24, 30)
    hum_base = rng.uniform(40, 70)

    rows = []

    for second in range(RUN_SECONDS):
        position = second % CYCLE_SECONDS

        if position < PURGE_SECONDS:
            state = "PURGE"
            response = 0.0
        else:
            state = "SAMPLE"
            sample_t = position - PURGE_SECONDS
            progress = 1.0 - np.exp(-sample_t / 2.5)
            recovery = max(0.0, (sample_t - 4.0) / 2.0)
            response = progress * (1.0 - 0.35 * recovery)

        env_temp = temp_base + rng.normal(0, 0.15)
        env_hum = hum_base + rng.normal(0, 0.7)

        env_factor = (
            1.0
            + 0.008 * (env_temp - 27.0)
            - 0.0015 * (env_hum - 55.0)
        )

        # Synthetic only: signal direction is an artificial convention.
        bme = bme_base * (
            1.0 - bme_strength * response * env_factor
        )
        voc = voc_base * (
            1.0 - voc_strength * response * env_factor
        )
        nox = nox_base * (
            1.0 - nox_strength * response * env_factor
        )

        bme += rng.normal(0, bme_base * 0.006)
        voc += rng.normal(0, voc_base * 0.012)
        nox += rng.normal(0, nox_base * 0.012)

        rows.append({
            "timestamp_ms": second * 1000,
            "uptime_ms": second * 1000,
            "state": state,
            "ambient_temp": round(env_temp, 3),
            "ambient_hum": round(env_hum, 3),
            "voc_raw": int(max(voc, 1000)),
            "nox_raw": int(max(nox, 1000)),
            "gas_resistance": round(max(bme, 1000), 2),
            "threat_alert": 0,
            "label": label,
            "session_id": session_id,
            "compound": compound,
        })

    return pd.DataFrame(rows)


def main():
    DATA_DIR.mkdir(exist_ok=True)
    rng = np.random.default_rng(RANDOM_SEED)

    # Only create files with a dedicated prefix so existing real data
    # is not overwritten.
    for old in DATA_DIR.glob("sanity_*.csv"):
        old.unlink()

    session_number = 0

    for compound in COMPOUNDS:
        for _ in range(5):
            session_number += 1
            session_id = f"sanity_{compound}_{session_number:03d}"
            df = generate_session(session_id, compound, rng)
            path = DATA_DIR / f"{session_id}.csv"
            df.to_csv(path, index=False)

    print("========================================")
    print(" SANITY RAW DATA GENERATION COMPLETE")
    print("========================================")
    print("Generated 30 synthetic raw sessions.")
    print("These are NOT real narcotics/explosives measurements.")
    print("\nNext:")
    print("  python feature_extraction.py")
    print("  python trainer_classifier.py")


if __name__ == "__main__":
    main()
