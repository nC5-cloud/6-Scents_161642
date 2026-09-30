"""
MQTT data logger for real e-nose experiments.

One execution can collect multiple independent sessions. Each session
gets its own CSV and session_id. The logger records raw sensor telemetry
and experimental metadata so real data can be collected across multiple
compounds/interferents.

The firmware's threat_alert is retained for debugging only and must NOT
be used as an ML feature.
"""

import csv
import json
import time
from pathlib import Path

import paho.mqtt.client as mqtt


MQTT_BROKER = "172.17.6.114"
MQTT_PORT = 1883
MQTT_TOPIC = "sniffer/telemetry"

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

DEFAULT_RUN_SECONDS = 60

BASE_FIELDS = [
    "timestamp_ms",
    "uptime_ms",
    "state",
    "ambient_temp",
    "ambient_hum",
    "voc_raw",
    "nox_raw",
    "gas_resistance",
    "threat_alert",
    "label",
    "session_id",
    "compound",
]


def ask_metadata():
    print("\n----------------------------------------")
    compound = input("Enter compound/sample name: ").strip()

    while True:
        label_text = input(
            "Enter label (1 = threat-analog, 0 = benign/interferent): "
        ).strip()
        if label_text in ("0", "1"):
            label = int(label_text)
            break
        print("Please enter only 0 or 1.")


    duration_text = input(
        f"Session duration in seconds [{DEFAULT_RUN_SECONDS}]: "
    ).strip()

    try:
        duration = float(duration_text) if duration_text else DEFAULT_RUN_SECONDS
    except ValueError:
        print("Invalid duration; using 60 seconds.")
        duration = DEFAULT_RUN_SECONDS

    if duration <= 0:
        duration = DEFAULT_RUN_SECONDS

    return compound, label, duration


class SessionLogger:
    def __init__(self, client, compound, label, run_seconds):
        self.client = client
        self.compound = compound
        self.label = label
        self.run_seconds = run_seconds

        self.session_id = (
            f"session_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time()*1000)%1000:03d}"
        )
        self.output_file = DATA_DIR / f"{self.session_id}.csv"

        self.csv_file = open(
            self.output_file,
            mode="w",
            newline="",
            encoding="utf-8",
        )
        self.writer = csv.DictWriter(
            self.csv_file,
            fieldnames=BASE_FIELDS,
            extrasaction="ignore",
        )
        self.writer.writeheader()

        self.start_time = None
        self.packet_count = 0
        self.finished = False

    def start(self):
        self.start_time = time.monotonic()
        print(f"\nLogging session : {self.session_id}")
        print(f"Sample         : {self.compound}")
        print(f"Label          : {self.label}")
        print(f"Duration       : {self.run_seconds:.1f} s")
        print(f"Saving to      : {self.output_file}")
        print("----------------------------------------")

    def handle_message(self, msg):
        if self.finished:
            return

        if self.start_time is None:
            self.start()

        elapsed = time.monotonic() - self.start_time
        if elapsed >= self.run_seconds:
            self.finish()
            return

        try:
            data = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            print(f"Skipping invalid MQTT message: {error}")
            return

        required = [
            "uptime_ms", "state", "ambient_temp", "ambient_hum",
            "voc_raw", "nox_raw", "gas_resistance",
        ]
        missing = [key for key in required if key not in data]
        if missing:
            print(f"Skipping packet; missing fields: {missing}")
            return

        row = {
            "timestamp_ms": int(time.time() * 1000),
            "uptime_ms": data["uptime_ms"],
            "state": data["state"],
            "ambient_temp": data["ambient_temp"],
            "ambient_hum": data["ambient_hum"],
            "voc_raw": data["voc_raw"],
            "nox_raw": data["nox_raw"],
            "gas_resistance": data["gas_resistance"],
            "threat_alert": data.get("threat_alert", 0),
            "label": self.label,
            "session_id": self.session_id,
            "compound": self.compound,
        }

        self.writer.writerow(row)
        self.csv_file.flush()
        self.packet_count += 1

        print(
            f"{elapsed:6.1f}s | "
            f"state={str(row['state']):7} | "
            f"VOC={str(row['voc_raw']):>6} | "
            f"NOx={str(row['nox_raw']):>6} | "
            f"BME={row['gas_resistance']}"
        )

    def finish(self):
        if self.finished:
            return

        self.finished = True
        self.csv_file.flush()
        self.csv_file.close()

        print("\n========================================")
        print("SESSION COMPLETE")
        print("========================================")
        print(f"Session : {self.session_id}")
        print(f"Packets : {self.packet_count}")
        print(f"CSV     : {self.output_file}")


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

current_logger = None
connected = False


def on_connect(client, userdata, flags, reason_code, properties=None):
    global connected
    connected = True
    print(f"\nConnected to MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"Subscribing to: {MQTT_TOPIC}")
    client.subscribe(MQTT_TOPIC)
    print("Waiting for ESP32 telemetry...\n")


def on_message(client, userdata, msg):
    global current_logger
    if current_logger is not None:
        current_logger.handle_message(msg)


client.on_connect = on_connect
client.on_message = on_message


def main():
    global current_logger

    print("========================================")
    print("      ESP32 E-NOSE MQTT DATA LOGGER")
    print("========================================")
    print(f"Broker : {MQTT_BROKER}")
    print(f"Port   : {MQTT_PORT}")
    print(f"Topic  : {MQTT_TOPIC}")

    print("\nConnecting...")

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    except Exception as error:
        print("\nCould not connect to MQTT broker.")
        print("Error:", error)
        raise SystemExit(1)

    client.loop_start()

    try:
        while True:
            compound, label, run_seconds = ask_metadata()

            current_logger = SessionLogger(
                client,
                compound,
                label,
                run_seconds,
            )

            # Wait for packets until this session is finished.
            while not current_logger.finished:
                time.sleep(0.1)

            current_logger = None

            again = input(
                "\nCollect another session? [Y/n]: "
            ).strip().lower()

            if again in ("n", "no"):
                break

    except KeyboardInterrupt:
        print("\nLogging stopped manually.")

    finally:
        if current_logger is not None:
            current_logger.finish()
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
