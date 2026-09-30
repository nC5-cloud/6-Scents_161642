"""
Sanity-check generator only, not for real training. Makes fake 60s/2Hz
sessions matching the Phase 1 protocol (baseline/exposure/recovery) so you
can confirm feature_extraction.py and train_classifier.py run cleanly
before your first real CSVs come off the ESP32.
"""

import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(7)
INTERVAL_MS = 500
RUN_MS = 60_000
N = RUN_MS // INTERVAL_MS + 1
BASE_IDX = int(10_000 // INTERVAL_MS)

BME_BASE, VOC_BASE, NOX_BASE = 100_000.0, 32_000.0, 32_000.0

COMPOUNDS = {
    "acetone": (1, 0.55, 900, 4000),
    "h2o2": (1, 0.30, 2500, 9000),
    "ipa": (1, 0.60, 700, 3500),
    "perfume": (0, 0.35, 1500, 6000),
    "coffee_grounds": (0, 0.20, 3000, 12000),
    "hand_sanitizer": (0, 0.45, 800, 4000),
}


def make_session(session_id, compound):
    label, depth, rise_ms, recover_ms = COMPOUNDS[compound]
    t = np.arange(0, RUN_MS + 1, INTERVAL_MS)

    def channel(base, depth_scale):
        sig = np.full(N, base) + RNG.normal(0, base * 0.008, N)
        peak_idx = BASE_IDX + int(rise_ms / INTERVAL_MS)
        recover_idx = peak_idx + int(recover_ms / INTERVAL_MS)
        for i in range(BASE_IDX, min(peak_idx, N)):
            frac = (i - BASE_IDX) / max(1, peak_idx - BASE_IDX)
            sig[i] -= base * depth * depth_scale * frac
        if peak_idx < N:
            sig[peak_idx] -= base * depth * depth_scale
        for i in range(peak_idx, min(recover_idx, N)):
            frac = (i - peak_idx) / max(1, recover_idx - peak_idx)
            sig[i] = sig[peak_idx] + (base - sig[peak_idx]) * frac
        if recover_idx < N:
            sig[recover_idx:] = base + RNG.normal(0, base * 0.008, N - recover_idx)
        return sig

    bme = channel(BME_BASE, 1.0)
    voc = channel(VOC_BASE, 0.8 if label else 0.5)
    nox = channel(NOX_BASE, 0.3 if label else 0.55)

    return pd.DataFrame({
        "timestamp_ms": t, "bme688_res_ohms": bme,
        "sgp41_sraw_voc": voc, "sgp41_sraw_nox": nox,
        "label": label, "session_id": session_id, "compound": compound,
    })


def generate_dataset(out_dir="data", reps=5):
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    sid = 0
    plan = list(COMPOUNDS.keys()) * reps
    RNG.shuffle(plan)
    for compound in plan:
        make_session(sid, compound).to_csv(out_path / f"session_{sid:03d}.csv", index=False)
        sid += 1
    print(f"Generated {sid} sanity-check sessions in '{out_path}/'")


if __name__ == "__main__":
    generate_dataset()
