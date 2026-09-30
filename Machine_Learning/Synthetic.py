import numpy as np
import pandas as pd
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

DATA_DIR = Path("data")

# Number of independent synthetic sessions
SESSIONS_PER_COMPOUND = 15

# ESP32 telemetry is approximately once per second
SAMPLE_INTERVAL_SECONDS = 1.0

# Firmware cycle:
# PURGE = 4 seconds
# SAMPLE = 6 seconds
PURGE_SECONDS = 4
SAMPLE_SECONDS = 6

CYCLE_SECONDS = PURGE_SECONDS + SAMPLE_SECONDS

# Six complete cycles = 60 seconds
NUM_CYCLES = 6

TOTAL_SECONDS = CYCLE_SECONDS * NUM_CYCLES

# Reproducible randomness
RANDOM_SEED = 42


# ============================================================
# SYNTHETIC SAMPLE DEFINITIONS
# ============================================================

"""
Each profile describes a synthetic response tendency.

These are NOT physical measurements.

The numbers are deliberately overlapping so the ML model
cannot simply learn:

    "large response = threat"

Instead, it must use a combination of:

    - BME response
    - VOC response
    - NOx response
    - response timing
    - recovery behaviour
    - cross-sensor relationships
"""

COMPOUNDS = {

    # --------------------------------------------------------
    # THREAT-ANALOG PROXIES
    # --------------------------------------------------------

    "acetone_proxy": {
        "label": 1,

        # Relative response tendencies
        "bme": 0.32,
        "voc": 0.55,
        "nox": 0.20,

        # Characteristic response timing
        "bme_tau": 2.0,
        "voc_tau": 1.5,
        "nox_tau": 2.5,

        # Recovery tendency
        "recovery": 0.65,

        # Sensor-to-sensor variation
        "variation": 0.18,
    },

    "h2o2_proxy": {
        "label": 1,

        "bme": 0.48,
        "voc": 0.25,
        "nox": 0.50,

        "bme_tau": 3.0,
        "voc_tau": 2.5,
        "nox_tau": 1.8,

        "recovery": 0.45,
        "variation": 0.20,
    },

    "ipa_proxy": {
        "label": 1,

        "bme": 0.28,
        "voc": 0.62,
        "nox": 0.12,

        "bme_tau": 2.5,
        "voc_tau": 1.8,
        "nox_tau": 3.0,

        "recovery": 0.75,
        "variation": 0.20,
    },

    # --------------------------------------------------------
    # BENIGN / INTERFERENT SAMPLES
    # --------------------------------------------------------

    "perfume": {
        "label": 0,

        "bme": 0.35,
        "voc": 0.48,
        "nox": 0.10,

        "bme_tau": 3.5,
        "voc_tau": 2.8,
        "nox_tau": 3.5,

        "recovery": 0.40,
        "variation": 0.22,
    },

    "coffee": {
        "label": 0,

        "bme": 0.22,
        "voc": 0.30,
        "nox": 0.38,

        "bme_tau": 3.8,
        "voc_tau": 3.2,
        "nox_tau": 2.8,

        "recovery": 0.35,
        "variation": 0.20,
    },

    "hand_sanitizer": {
        "label": 0,

        "bme": 0.42,
        "voc": 0.58,
        "nox": 0.16,

        "bme_tau": 3.0,
        "voc_tau": 2.0,
        "nox_tau": 3.5,

        "recovery": 0.70,
        "variation": 0.22,
    },
}


# ============================================================
# BASE SENSOR VALUES
# ============================================================

def generate_environment(rng):
    """
    Generate a plausible laboratory environment for one session.
    """

    temperature = rng.normal(
        loc=27.0,
        scale=2.5
    )

    humidity = rng.normal(
        loc=55.0,
        scale=10.0
    )

    temperature = np.clip(
        temperature,
        20.0,
        35.0
    )

    humidity = np.clip(
        humidity,
        30.0,
        80.0
    )

    return temperature, humidity


def generate_sensor_baselines(rng):
    """
    Generate session-specific sensor baselines.

    This is important.

    Every synthetic session should NOT begin at exactly
    the same sensor value.
    """

    bme_baseline = rng.normal(
        100000.0,
        12000.0
    )

    voc_baseline = rng.normal(
        30000.0,
        1800.0
    )

    nox_baseline = rng.normal(
        10000.0,
        900.0
    )

    return (
        max(bme_baseline, 50000.0),
        max(voc_baseline, 20000.0),
        max(nox_baseline, 5000.0),
    )


# ============================================================
# RESPONSE FUNCTION
# ============================================================

def response_curve(
    time_in_sample,
    amplitude,
    tau,
    recovery,
    sample_duration,
):
    """
    Generate a smooth sensor response.

    During exposure:
        response rises approximately exponentially.

    Toward the end:
        recovery begins gradually.

    This creates a temporal signature rather than
    a single artificial threshold.
    """

    if time_in_sample < 0:
        return 0.0

    # Exposure response
    rise = amplitude * (
        1.0 - np.exp(
            -time_in_sample / tau
        )
    )

    # Begin recovery near the end of the sample period
    recovery_start = sample_duration * 0.65

    if time_in_sample > recovery_start:

        recovery_time = (
            time_in_sample
            - recovery_start
        )

        recovery_fraction = (
            1.0
            - np.exp(
                -recovery_time
                / (tau * 1.8)
            )
        )

        rise *= (
            1.0
            - recovery
            * recovery_fraction
        )

    return max(rise, 0.0)


# ============================================================
# SENSOR RESPONSE
# ============================================================

def generate_session(
    compound_name,
    session_number,
    rng,
):
    """
    Generate one complete synthetic 60-second session.
    """

    profile = COMPOUNDS[compound_name]

    label = profile["label"]

    # --------------------------------------------------------
    # Environment
    # --------------------------------------------------------

    base_temp, base_humidity = generate_environment(
        rng
    )

    # --------------------------------------------------------
    # Sensor baselines
    # --------------------------------------------------------

    bme_base, voc_base, nox_base = (
        generate_sensor_baselines(rng)
    )

    # --------------------------------------------------------
    # Session-specific variation
    #
    # This prevents every session of the same compound
    # from looking identical.
    # --------------------------------------------------------

    variation = profile["variation"]

    bme_strength = profile["bme"] * rng.normal(
        1.0,
        variation
    )

    voc_strength = profile["voc"] * rng.normal(
        1.0,
        variation
    )

    nox_strength = profile["nox"] * rng.normal(
        1.0,
        variation
    )

    bme_tau = profile["bme_tau"] * rng.normal(
        1.0,
        0.12
    )

    voc_tau = profile["voc_tau"] * rng.normal(
        1.0,
        0.12
    )

    nox_tau = profile["nox_tau"] * rng.normal(
        1.0,
        0.12
    )

    recovery = np.clip(
        profile["recovery"] * rng.normal(
            1.0,
            0.12
        ),
        0.1,
        0.95
    )

    # --------------------------------------------------------
    # Exposure strength
    #
    # Simulates small changes in sample/headspace
    # concentration between sessions.
    # --------------------------------------------------------

    exposure_strength = rng.uniform(
        0.70,
        1.30
    )

    # --------------------------------------------------------
    # Session-specific drift
    #
    # Slow baseline movement over the 60-second session.
    # --------------------------------------------------------

    bme_drift = rng.normal(
        0.0,
        0.0015
    )

    voc_drift = rng.normal(
        0.0,
        0.0010
    )

    nox_drift = rng.normal(
        0.0,
        0.0012
    )

    rows = []

    session_id = (
        f"synth_{compound_name}_{session_number:03d}"
    )

    # ========================================================
    # GENERATE TELEMETRY
    # ========================================================

    for second in range(
        int(TOTAL_SECONDS)
    ):

        # ----------------------------------------------------
        # Determine firmware state
        # ----------------------------------------------------

        position = second % CYCLE_SECONDS

        if position < PURGE_SECONDS:

            state = "PURGE"

            time_in_sample = -1.0

        else:

            state = "SAMPLE"

            time_in_sample = (
                position
                - PURGE_SECONDS
            )

        # ----------------------------------------------------
        # Environmental drift
        # ----------------------------------------------------

        temp_drift = (
            rng.normal(0.0, 0.015)
            + 0.005
            * np.sin(
                second / 15.0
            )
        )

        hum_drift = (
            rng.normal(0.0, 0.08)
            + 0.03
            * np.sin(
                second / 18.0
            )
        )

        ambient_temp = (
            base_temp
            + temp_drift
        )

        ambient_hum = (
            base_humidity
            + hum_drift
        )

        # ----------------------------------------------------
        # Slow environmental effect
        #
        # MOX-style sensors are affected by environmental
        # conditions, so we introduce a small coupling.
        # ----------------------------------------------------

        temp_factor = 1.0 + (
            (ambient_temp - 27.0)
            * 0.008
        )

        humidity_factor = 1.0 - (
            (ambient_hum - 55.0)
            * 0.0015
        )

        environment_factor = (
            temp_factor
            * humidity_factor
        )

        # ----------------------------------------------------
        # Chemical response
        # ----------------------------------------------------

        if state == "SAMPLE":

            bme_response = response_curve(
                time_in_sample,
                bme_strength
                * exposure_strength,
                max(bme_tau, 0.5),
                recovery,
                SAMPLE_SECONDS,
            )

            voc_response = response_curve(
                time_in_sample,
                voc_strength
                * exposure_strength,
                max(voc_tau, 0.5),
                recovery,
                SAMPLE_SECONDS,
            )

            nox_response = response_curve(
                time_in_sample,
                nox_strength
                * exposure_strength,
                max(nox_tau, 0.5),
                recovery,
                SAMPLE_SECONDS,
            )

        else:

            bme_response = 0.0
            voc_response = 0.0
            nox_response = 0.0

        # ----------------------------------------------------
        # Convert relative response into sensor values
        # ----------------------------------------------------

        # BME688:
        # Synthetic response is represented as a reduction
        # in gas resistance.
        #
        # SGP41:
        # We intentionally model raw VOC/NOx as decreasing
        # signals for this simulator. This is only a synthetic
        # convention and must NOT be interpreted as a measured
        # chemical response direction.
        # ----------------------------------------------------

        bme_value = (
            bme_base
            * (
                1.0
                - bme_response
                * environment_factor
            )
        )

        voc_value = (
            voc_base
            * (
                1.0
                - voc_response
                * environment_factor
            )
        )

        nox_value = (
            nox_base
            * (
                1.0
                - nox_response
                * environment_factor
            )
        )

        # ----------------------------------------------------
        # Add slow sensor drift
        # ----------------------------------------------------

        drift_multiplier = (
            1.0
            + bme_drift * second
        )

        bme_value *= drift_multiplier

        voc_value *= (
            1.0
            + voc_drift * second
        )

        nox_value *= (
            1.0
            + nox_drift * second
        )

        # ----------------------------------------------------
        # Cross-sensor interaction
        #
        # Real sensor arrays are not perfectly independent.
        # A response in one sensor can slightly influence
        # another.
        # ----------------------------------------------------

        voc_value *= (
            1.0
            + 0.03 * bme_response
        )

        nox_value *= (
            1.0
            + 0.025 * voc_response
        )

        # ----------------------------------------------------
        # Measurement noise
        # ----------------------------------------------------

        bme_noise = rng.normal(
            0.0,
            bme_base * 0.006
        )

        voc_noise = rng.normal(
            0.0,
            voc_base * 0.012
        )

        nox_noise = rng.normal(
            0.0,
            nox_base * 0.012
        )

        bme_value += bme_noise
        voc_value += voc_noise
        nox_value += nox_noise

        # ----------------------------------------------------
        # Physical limits
        # ----------------------------------------------------

        bme_value = max(
            bme_value,
            1000.0
        )

        voc_value = max(
            voc_value,
            1000.0
        )

        nox_value = max(
            nox_value,
            1000.0
        )

        # ----------------------------------------------------
        # Threat alert
        #
        # This is deliberately NOT connected to the label.
        #
        # It exists only because the actual ESP32 telemetry
        # contains this debug field.
        # ----------------------------------------------------

        threat_alert = 0

        # ----------------------------------------------------
        # Construct telemetry row
        # ----------------------------------------------------

        rows.append({

            "timestamp_ms":
                second * 1000,

            "uptime_ms":
                second * 1000,

            "state":
                state,

            "ambient_temp":
                round(
                    ambient_temp,
                    3
                ),

            "ambient_hum":
                round(
                    ambient_hum,
                    3
                ),

            "voc_raw":
                int(
                    round(voc_value)
                ),

            "nox_raw":
                int(
                    round(nox_value)
                ),

            "gas_resistance":
                round(
                    bme_value,
                    2
                ),

            "threat_alert":
                threat_alert,

            "label":
                label,

            "session_id":
                session_id,

            "compound":
                compound_name,
        })

    return pd.DataFrame(rows)


# ============================================================
# GENERATE ALL SESSIONS
# ============================================================

def main():

    print("========================================")
    print("  SYNTHETIC E-NOSE DATA GENERATOR")
    print("========================================")

    print(
        "\nGenerating physics-inspired synthetic"
        " sensor telemetry."
    )

    print(
        "\nIMPORTANT:"
        "\nThis is synthetic validation data."
        "\nIt is NOT real narcotics/explosives data."
    )

    # --------------------------------------------------------
    # Prepare output directory
    # --------------------------------------------------------

    DATA_DIR.mkdir(
        exist_ok=True
    )

    # --------------------------------------------------------
    # Create deterministic random generator
    # --------------------------------------------------------

    rng = np.random.default_rng(
        RANDOM_SEED
    )

    total_sessions = (
        len(COMPOUNDS)
        * SESSIONS_PER_COMPOUND
    )

    print(
        f"\nCompounds/classes: {len(COMPOUNDS)}"
    )

    print(
        f"Sessions per compound: "
        f"{SESSIONS_PER_COMPOUND}"
    )

    print(
        f"Total sessions: "
        f"{total_sessions}"
    )

    print(
        f"Duration per session: "
        f"{TOTAL_SECONDS} seconds"
    )

    # --------------------------------------------------------
    # Generate
    # --------------------------------------------------------

    session_count = 0

    for compound_name in COMPOUNDS:

        for session_number in range(
            1,
            SESSIONS_PER_COMPOUND + 1
        ):

            df = generate_session(
                compound_name,
                session_number,
                rng
            )

            output_file = (
                DATA_DIR
                / f"{df['session_id'].iloc[0]}.csv"
            )

            df.to_csv(
                output_file,
                index=False
            )

            session_count += 1

            print(
                f"[{session_count:02d}/"
                f"{total_sessions}] "
                f"{compound_name:18s} "
                f"→ {output_file.name}"
            )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("\n========================================")
    print("       GENERATION COMPLETE")
    print("========================================")

    print(
        f"\nGenerated "
        f"{session_count} synthetic sessions."
    )

    print(
        f"Saved inside: "
        f"{DATA_DIR.resolve()}"
    )

    print(
        "\nNext step:"
    )

    print(
        "    python feature_extraction.py"
    )

    print(
        "\nThen:"
    )

    print(
        "    python trainer_classifier.py"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()