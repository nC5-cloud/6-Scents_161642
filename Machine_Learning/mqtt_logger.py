import csv
import json
import time
from pathlib import Path

import paho.mqtt.client as mqtt


# ============================================================
# MQTT SETTINGS
# ============================================================

MQTT_BROKER = "172.17.6.114" 
MQTT_PORT = 1883
MQTT_TOPIC = "sniffer/telemetry"


# ============================================================
# DATA SETTINGS
# ============================================================

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

RUN_SECONDS = 60


# ============================================================
# EXPERIMENT INFORMATION
# ============================================================

compound = input("Enter compound/sample name: ").strip()

while True:
    label = input("Enter label (1 = threat-analog, 0 = benign): ").strip()

    if label in ["0", "1"]:
        label = int(label)
        break

    print("Please enter only 0 or 1.")


# Create a unique session ID
session_id = f"session_{int(time.time())}"


output_file = DATA_DIR / f"{session_id}.csv"


# ============================================================
# CSV SETTINGS
# ============================================================

fieldnames = [
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
    "compound"
]


csv_file = None
csv_writer = None

start_time = None


# ============================================================
# MQTT CALLBACKS
# ============================================================

def on_connect(client, userdata, flags, reason_code, properties=None):
    """
    Called when Python successfully connects to the MQTT broker.
    """

    print(f"\nConnected to MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"Subscribing to topic: {MQTT_TOPIC}")

    client.subscribe(MQTT_TOPIC)

    print("Waiting for ESP32 telemetry...\n")


def on_message(client, userdata, msg):
    """
    Called every time an MQTT message is received.
    """

    global csv_writer
    global csv_file
    global start_time

    # Start the 60-second session when the first telemetry packet arrives
    if start_time is None:
        start_time = time.time()
        print("First telemetry received.")
        print(f"Logging session: {session_id}")
        print(f"Saving to: {output_file}")
        print("----------------------------------------")

    # Stop after RUN_SECONDS
    if time.time() - start_time >= RUN_SECONDS:
        print("\n60-second session complete.")
        client.disconnect()
        return

    # --------------------------------------------------------
    # Decode MQTT message
    # --------------------------------------------------------

    try:
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)

    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        print(f"Skipping invalid MQTT message: {error}")
        return


    # --------------------------------------------------------
    # Extract telemetry
    # --------------------------------------------------------

    try:
        row = {
            "timestamp_ms": int(time.time() * 1000),

            "uptime_ms": data["uptime_ms"],

            "state": data["state"],

            "ambient_temp": data["ambient_temp"],

            "ambient_hum": data["ambient_hum"],

            "voc_raw": data["voc_raw"],

            "nox_raw": data["nox_raw"],

            "gas_resistance": data["gas_resistance"],

            # Logged for debugging only.
            # DO NOT use this as an ML feature.
            "threat_alert": data["threat_alert"],

            "label": label,

            "session_id": session_id,

            "compound": compound
        }

    except KeyError as error:
        print(f"Missing field in MQTT message: {error}")
        print("Received:", data)
        return


    # --------------------------------------------------------
    # Write row to CSV
    # --------------------------------------------------------

    csv_writer.writerow(row)
    csv_file.flush()


    # --------------------------------------------------------
    # Display useful information in terminal
    # --------------------------------------------------------

    elapsed = time.time() - start_time

    print(
        f"{elapsed:5.1f}s | "
        f"state={row['state']:8} | "
        f"VOC={row['voc_raw']:5} | "
        f"NOx={row['nox_raw']:5} | "
        f"BME={row['gas_resistance']}"
    )


# ============================================================
# CREATE CSV FILE
# ============================================================

csv_file = open(
    output_file,
    mode="w",
    newline="",
    encoding="utf-8"
)

csv_writer = csv.DictWriter(
    csv_file,
    fieldnames=fieldnames
)

csv_writer.writeheader()


# ============================================================
# CREATE MQTT CLIENT
# ============================================================

client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2
)

client.on_connect = on_connect
client.on_message = on_message


# ============================================================
# CONNECT
# ============================================================

print("========================================")
print("   ESP32 MQTT ML DATA LOGGER")
print("========================================")

print(f"Broker : {MQTT_BROKER}")
print(f"Port   : {MQTT_PORT}")
print(f"Topic  : {MQTT_TOPIC}")

print(f"Sample : {compound}")
print(f"Label  : {label}")
print(f"Session: {session_id}")

print("\nConnecting...")


try:

    client.connect(
        MQTT_BROKER,
        MQTT_PORT,
        keepalive=60
    )

except Exception as error:

    csv_file.close()

    print("\nCould not connect to MQTT broker.")
    print("Error:", error)

    print("\nCheck:")
    print("1. MQTT broker is running.")
    print("2. Broker IP is correct.")
    print("3. Your laptop is on the same network.")
    print("4. Port 1883 is accessible.")

    raise SystemExit


# ============================================================
# START LISTENING
# ============================================================

try:

    client.loop_forever()

except KeyboardInterrupt:

    print("\nLogging stopped manually.")


finally:

    csv_file.close()

    print("\nCSV file saved:")
    print(output_file)