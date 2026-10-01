# 6-Scents ML Pipeline

This version intentionally contains **no heater-profile or heater-temperature handling** because heater control has not yet been added to the ESP32 firmware.

## Pipeline

1. `python mqtt_logger.py` — collect real ESP32 MQTT sessions.
2. `python feature_extraction.py` — convert each session into one feature row.
3. `python trainer_classifier.py` — GroupKFold evaluation, Random Forest research model, and small Decision Tree TinyML candidate.

## Features

The model uses sensor-response features from BME688 gas resistance and SGP41 VOC/NOx, including response magnitude, peak response, response timing, recovery behavior, and VOC/NOx relationship. Ambient temperature/humidity are retained as metadata/features where defined by the extractor.

`threat_alert` is retained only for debugging and is never an ML input. `session_id` is used for grouping and traceability, not as an input feature.

## Not included yet

- BME688 heater-profile sweep/control
- heater telemetry
- offline ESP32 flash logging
- ESP32 TinyML inference integration
- multi-level hardware alarm

The Python trainer can export the TinyML Decision Tree header, but firmware integration is a separate step.

Synthetic data is for pipeline validation only and must not be represented as measured narcotics/explosives data.
