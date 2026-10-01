# Machine Learning

Data collection, feature extraction and classifier training for 6-Scents. The model takes the response of the gas sensors (BME688, SGP41 VOC/NOx) over a PURGE to SAMPLE cycle and classifies the sample as threat-analog or benign.

No heater-profile or heater-temperature handling is included, since heater control isn't in the firmware yet.

## Pipeline

1. `python mqtt_logger.py`: collect real ESP32 MQTT sessions. Each run logs 60 seconds, tagged with the sample name and a label (1 = threat-analog, 0 = benign). Set the broker IP at the top of the script.
2. `python feature_extraction.py`: convert each session into one feature row in `feature_matrix.csv`.
3. `python trainer_classifier.py`: GroupKFold evaluation, a Random Forest research model, and a small Decision Tree exported for on-device inference.

```bash
pip install paho-mqtt pandas numpy scikit-learn
```

## Samples tested

Six everyday samples, three per class. Safe analogs are used instead of real narcotics or explosives.

| # | Sample | Class | Label |
|---|--------|-------|-------|
| 1 | Concentrated hydrogen peroxide | Threat-analog | 1 |
| 2 | Concentrated acetone | Threat-analog | 1 |
| 3 | Isopropyl alcohol | Threat-analog | 1 |
| 4 | Perfume | Benign | 0 |
| 5 | Coffee Grounds | Benign | 0 |
| 6 | Nail polish | Benign | 0 |

The benign samples are strong, common smells found all over a railway station, so the model has to separate threat-like vapours from background interference rather than just react to "something strong".

## Features

Response features from the BME688 gas resistance and the SGP41 VOC and NOx signals: response magnitude, peak response, response timing, recovery behaviour, and the VOC/NOx relationship. Ambient temperature and humidity are kept as metadata or features where the extractor defines them.

- `threat_alert` is logged for debugging only and is never an ML input.
- `session_id` is used for grouping and traceability, not as a feature.

## Models

- **Random Forest**: the research model, used to evaluate how well the features separate the classes and to rank feature importances.
- **Decision Tree**: the small model that runs on the ESP32-S3, exported as a C header.

Evaluation uses GroupKFold cross-validation so data from one session never appears in both train and test.

## Results

<!-- Accuracy, false positive rate, confusion matrix, on-device latency -->

## Synthetic data

`sanity_check.py` generates fake sessions to check the pipeline runs end to end. It is for pipeline validation only and must not be presented as measured narcotics or explosives data.

## Not included yet

- BME688 heater-profile sweep and control
- Heater telemetry
