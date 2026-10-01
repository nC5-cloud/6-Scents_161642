# Machine Learning

Machine-learning pipeline for the **6-Scents** electronic-nose system.

The pipeline uses physically collected ESP32 sensor data from the **BME688** and **SGP41 (VOC/NOx)** sensors. Responses are recorded over repeated PURGE → SAMPLE cycles and converted into session-level features for binary classification as **threat-analog** or **benign**.

> No heater-profile or heater-temperature handling is included, because heater control has not yet been added to the firmware.

## Contents

- [Pipeline](#pipeline)
- [Experimental samples](#experimental-samples)
- [Features](#features)
- [Validation method](#validation-method)
- [Models](#models)
- [Output](#output)
- [Synthetic data](#synthetic-data)
- [Installation](#installation)
- [Running the pipeline](#running-the-pipeline)
- [Current status](#current-status)

## Pipeline

```text
Physical sample → ESP32 sensor array → MQTT telemetry → mqtt_logger.py
→ raw session CSV → feature_extraction.py → feature_matrix.csv
→ trainer_classifier.py → Random Forest + TinyML Decision Tree
```

### 1. Data collection

```bash
python mqtt_logger.py
```

Collects a real ESP32 MQTT session for a selected sample. Each session is:

- approximately 60 seconds long
- tagged with a sample (compound) name
- given a binary label: `1` = threat-analog, `0` = benign
- stored as an independent CSV

The MQTT broker address and topic are set at the top of `mqtt_logger.py`. Raw session data contains the sensor measurements plus timestamps, firmware state, label, session ID and sample name.

### 2. Feature extraction

```bash
python feature_extraction.py
```

Converts each valid raw session into **one feature vector**. The firmware runs `PURGE → SAMPLE → PURGE → SAMPLE ...`, and each valid PURGE → SAMPLE sequence is treated as one sensor-response cycle. Cycles within a session are aggregated, so:

```text
1 CSV session = 1 ML sample
```

Output is written to `feature_matrix.csv`.

### 3. Model training

```bash
python trainer_classifier.py
```

Runs session-aware cross-validation and trains:

- a **Random Forest** for research and evaluation
- a **small Decision Tree** for on-device inference on the ESP32

The Decision Tree is exported as a C header and integrated into the ESP32 firmware.

## Experimental samples

The dataset contains six physically tested samples: three threat-analog and three benign.

| # | Sample | Class | Label |
|---|--------|-------|-------|
| 1 | Concentrated hydrogen peroxide | Threat-analog | 1 |
| 2 | Concentrated acetone | Threat-analog | 1 |
| 3 | Isopropyl alcohol | Threat-analog | 1 |
| 4 | Coffee grounds | Benign | 0 |
| 5 | Hand sanitizer | Benign | 0 |
| 6 | Nail polish | Benign | 0 |

These are **proxy test substances** used for development. They are not actual narcotics or explosives, and successful classification of them must not be read as proof of narcotics or explosives detection.

The benign samples act as common background interferents, so the classifier isn't trained only to react to a strong vapour.

## Features

Features describe the sensor response over time and across sensors, rather than a single threshold.

| Source | Features |
|--------|----------|
| BME688 gas resistance | Response magnitude, maximum response, response timing, recovery behaviour |
| SGP41 VOC | Response magnitude, maximum response, response timing, recovery behaviour |
| SGP41 NOx | Response magnitude, maximum response, response timing, recovery behaviour |
| Cross-sensor | VOC/NOx relationship |
| Environment | Ambient temperature, ambient humidity |

**Not used as ML inputs**

- `threat_alert`: kept in raw telemetry for firmware debugging only
- `session_id`: used for traceability and group-based validation only

## Validation method

Evaluation uses **GroupKFold** cross-validation with `session_id` as the grouping variable, so measurements from the same session are never split between training and test sets. This avoids session-level data leakage and gives a more meaningful estimate of performance on unseen sessions.

## Models

**Random Forest**: the main research and evaluation model. Used to classify threat-analog vs benign sessions, evaluate features, examine feature importance, and provide a baseline for embedded deployment.

**Decision Tree**: a smaller model trained for TinyML. It is exported as a C header and runs on the ESP32 firmware for on-device inference.

## Output

`feature_matrix.csv` holds one row per processed session: the extracted features plus `label`, `session_id` and `compound`.

Training can also write model and evaluation outputs to the `models/` directory.

## Synthetic data

`Synthetic.py` is an auxiliary pipeline-testing tool. It generates artificial sensor sessions to verify that raw CSV → feature extraction → feature matrix → training runs correctly without new hardware measurements.

Synthetic data is **not part of the physical experimental dataset** and must not be presented as measured narcotics or explosives data.

## Installation

```bash
pip install -r requirements.txt
```

or:

```bash
pip install paho-mqtt pandas numpy scikit-learn
```

## Running the pipeline

**Real ESP32 data**

```bash
python mqtt_logger.py
python feature_extraction.py
python trainer_classifier.py
```

**Pipeline test with synthetic data**

```bash
python Synthetic.py
python feature_extraction.py
python trainer_classifier.py
```

## Current status

**Implemented**

- [x] ESP32 sensor-data collection and MQTT telemetry logging
- [x] Session-based dataset generation
- [x] PURGE → SAMPLE cycle processing
- [x] Temporal response features for BME688 and SGP41 VOC/NOx, plus VOC/NOx relationship
- [x] Session-level feature aggregation
- [x] GroupKFold validation
- [x] Random Forest training
- [x] Lightweight Decision Tree and C-header export
- [x] ESP32 on-device TinyML inference
- [x] Offline ESP32 flash-based data logging
- [x] Synthetic pipeline validation

**Not implemented yet**

- [ ] BME688 heater-profile sweep and control
- [ ] Heater-temperature telemetry
- [ ] Final multi-level alarm and output logic

These need firmware and hardware work and are not part of the Python ML pipeline.
