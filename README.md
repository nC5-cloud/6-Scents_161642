# 6-Scents

A portable multi-sensor pod that sniffs the air for volatile compounds linked to narcotics and explosives, built for Indian Railways screening. It is a handheld (and robot-mountable) electronic nose: a small array of gas sensors, an ESP32-S3, and an ML classifier that separates threat-like vapours from everyday background smells like perfume, sanitizer and cleaners.

Built for Smart India Hackathon 2026.

<!-- Add a photo of the pod and a short demo GIF here -->

## Why

Railway screening today is mostly fixed: X-ray at gates and trace portals at about 200 major stations. Once a passenger is through, nothing checks for chemical traces. X-ray and metal detectors don't identify chemicals, and sniffer dogs tire after 20 to 30 minutes and are hard to deploy everywhere. A cheap handheld sniffer can cover trains, parcels and hard-to-reach areas.

## How it works

The firmware runs a 10 second, two-state cycle:

| State | Duration | What happens |
|-------|----------|--------------|
| PURGE | 4 s | Pump flushes the chamber with ambient air, sensors return to baseline |
| SAMPLE | 6 s | Pump draws in vapour, sensors respond to the plume |

Once per second the ESP32-S3 reads all sensors, shows status on the OLED, and publishes a JSON packet over MQTT to `sniffer/telemetry`.

Sensor array:

| Sensor | Role |
|--------|------|
| Sensirion SHT40 | Temperature and humidity, used to compensate MOX drift |
| Sensirion SGP41 | Raw VOC and NOx signals |
| Bosch BME688 | Gas resistance from the heated MOX plate |
| 1.3" SH1106 OLED | Local status display |
| 5V micro pump | Draws sample in, purges chamber |
| Buzzer | Threat alert output |

Using several sensors with different response behaviour is what lets the classifier tell a real threat-like plume from background interference.

## ML pipeline

Currently in Phase 1: collecting labelled data and building the feature pipeline.

1. **Log**: `mqtt_logger.py` subscribes to the telemetry topic and saves a 60 second session to `data/session_<timestamp>.csv`, tagged with the compound name and a label (1 = threat-analog, 0 = benign).
2. **Extract features**: `feature_extraction.py` finds each PURGE to SAMPLE cycle in a session, takes the PURGE mean as baseline, and computes for each of BME688, VOC and NOx: normalised response depth (mean and max across cycles) and time to peak. It also adds a VOC/NOx ratio and mean ambient temperature and humidity. One session becomes one row in `feature_matrix.csv`.
3. **Train**: `train_classifier.py` trains a Random Forest (100 trees, max depth 5) on 10 features: response depth, max response depth and time to peak for each of BME688, SGP41 VOC and SGP41 NOx, plus the VOC/NOx ratio. It runs 5-fold GroupKFold cross-validation, prints accuracy, confusion matrix and feature importances per fold, then fits a final model on all data. The plan is to export that model as C arrays to run on the ESP32-S3 (TinyML).
4. **Sanity check**: `sanity_check.py` generates fake sessions so the pipeline can be tested before real data exists. Not for training.

Safe analog compounds are used for data collection (acetone, hydrogen peroxide, IPA as threat analogs; perfume, coffee grounds, hand sanitizer as benign).

## Repository structure

```
6-Scents_161642/
├── Detection_Firmware/     # ESP32-S3 firmware (PlatformIO / Arduino)
│   ├── main.cpp            # state machine, Wi-Fi, MQTT telemetry
│   ├── SensorHub.hpp       # sensor init, reads, OLED
│   ├── Actuators.hpp       # pump and buzzer control
│   └── pinout.h            # pin assignments
├── Machine_Learning/
│   ├── mqtt_logger.py      # logs labelled sessions from MQTT
│   ├── feature_extraction.py
│   ├── train_classifier.py # Random Forest training + cross-validation
│   └── sanity_check.py     # synthetic data for pipeline testing
├── .gitignore
└── README.md
```

## Getting started

### Firmware

Libraries: PubSubClient, ArduinoJson, Sensirion I2C SGP41, Adafruit SHT4x, Adafruit BME680, Adafruit SH110X.

1. Put your Wi-Fi and broker details in the config section of `main.cpp` (or a `secrets.h` that is git-ignored).
2. Build and flash to an ESP32-S3.
3. On boot the SGP41 runs a 10 second conditioning routine, then the cycle starts.

### Data collection

Run an MQTT broker (e.g. Mosquitto) on the same network, then:

```bash
pip install paho-mqtt pandas numpy
cd Machine_Learning
python mqtt_logger.py
```

Enter the compound name and label when prompted. Each run records 60 seconds.

### Feature extraction

```bash
python feature_extraction.py
```

Reads every CSV in `data/` and writes `feature_matrix.csv`.

### Training

```bash
pip install scikit-learn
python train_classifier.py
```

Reads `feature_matrix.csv` and prints cross-validation results.

## Status

- [x] Sensor array and pump firmware, OLED, MQTT telemetry
- [x] Data logger, feature extraction, training script
- [ ] Real data collection across compounds
- [ ] Classifier training and evaluation
- [ ] On-device TinyML inference and threat alert
- [ ] Offline logging to flash, multi-level alarm
- [ ] Heater-profile sweep on the BME688

## Results

<!-- Fill in once measured on real data: accuracy, false positive rate, confusion matrix, inference latency -->

## Cost

Prototype is roughly Rs 4,000. Estimated production cost with extra sensors is around Rs 10,000, against Rs 8 to 10 lakh for a benchtop ion mobility spectrometer.

## Team

<!-- Team name and members -->

## License

<!-- Add a LICENSE file and name it here -->
