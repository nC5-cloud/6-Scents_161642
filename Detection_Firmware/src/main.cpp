#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

#include "pinout.h"
#include "Actuators.hpp"
#include "SensorHub.hpp"


// ==========================================
// Network & Broker Credentials
// ==========================================

const char* WIFI_SSID =
    "BitGenix";

const char* WIFI_PASSWORD =
    "BitGenix";

const char* MQTT_SERVER =
    "172.17.6.114";

const int MQTT_PORT =
    1883;

const char* MQTT_TOPIC =
    "sniffer/telemetry";


// ==========================================
// State Machine Timing
// ==========================================

enum DeviceState {
    STATE_PURGE,
    STATE_SAMPLE
};

DeviceState currentState =
    STATE_PURGE;

unsigned long stateStartTime =
    0;

constexpr unsigned long TIME_PURGE =
    4000;

constexpr unsigned long TIME_SAMPLE =
    6000;


// ==========================================
// Threat Detection
// ==========================================
//
// IMPORTANT:
// We are NOT using an arbitrary VOC raw
// threshold for ML data collection.
//
// Threat detection will be implemented
// later using the trained model.
//

bool threatDetected = false;


// ==========================================
// Telemetry Timing
// ==========================================

constexpr unsigned long TELEMETRY_INTERVAL =
    1000;

unsigned long lastTelemetryTime =
    0;


// ==========================================
// Hardware & Network Objects
// ==========================================

WiFiClient espNetworkClient;

PubSubClient mqttClient(
    espNetworkClient
);

Actuators actuators;

SensorHub sensorHub;

TelemetrySnapshot snapshot{};


// ==========================================
// Wi-Fi Connection
// ==========================================

void connectToWiFi() {

    Serial.printf(
        "\n[NET] Connecting to Wi-Fi: %s",
        WIFI_SSID
    );

    WiFi.mode(WIFI_STA);

    WiFi.begin(
        WIFI_SSID,
        WIFI_PASSWORD
    );

    while (
        WiFi.status() != WL_CONNECTED
    ) {

        delay(500);

        Serial.print(".");
    }

    Serial.printf(
        "\n[NET] Connected! Local IP: %s\n",
        WiFi.localIP().toString().c_str()
    );
}


// ==========================================
// MQTT Connection
// ==========================================

void connectToMQTT() {

    while (
        !mqttClient.connected()
    ) {

        Serial.printf(
            "[MQTT] Connecting to broker at %s...\n",
            MQTT_SERVER
        );

        if (
            mqttClient.connect(
                "ESP32S3_Trace_Sniffer"
            )
        ) {

            Serial.println(
                "[MQTT] Broker connection established."
            );

        }
        else {

            Serial.printf(
                "[MQTT] Connection failed, rc=%d. "
                "Retrying in 2s...\n",
                mqttClient.state()
            );

            delay(2000);
        }
    }
}


// ==========================================
// State Name Helper
// ==========================================

const char* getStateName() {

    switch (currentState) {

        case STATE_PURGE:
            return "PURGE";

        case STATE_SAMPLE:
            return "SAMPLE";

        default:
            return "UNKNOWN";
    }
}


// ==========================================
// MQTT Telemetry
// ==========================================

void sendTelemetry(
    const char* stateStr,
    const TelemetrySnapshot& s,
    bool isThreat
) {

    JsonDocument doc;

    doc["device_id"] =
        "SIH-SNIFFER-01";

    doc["state"] =
        stateStr;

    doc["uptime_ms"] =
        millis();

    // BME688 environmental values
    doc["ambient_temp"] =
        s.ambientTemp;

    doc["ambient_hum"] =
        s.ambientHumidity;

    // SGP41 raw signals
    doc["voc_raw"] =
        s.rawSgpVoc;

    doc["nox_raw"] =
        s.rawSgpNox;

    // BME688 gas resistance
    doc["gas_resistance"] =
        s.bmeGasResistance;

    // Currently disabled for ML detection
    doc["threat_alert"] =
        isThreat;

    char jsonBuffer[512];

    serializeJson(
        doc,
        jsonBuffer
    );

    if (
        mqttClient.publish(
            MQTT_TOPIC,
            jsonBuffer
        )
    ) {

        Serial.printf(
            "[TELEMETRY] Sent: %s\n",
            jsonBuffer
        );

    }
    else {

        Serial.println(
            "[TELEMETRY] MQTT publish failed!"
        );
    }
}


// ==========================================
// Setup
// ==========================================

void setup() {

    Serial.begin(115200);

    delay(1000);

    Serial.println(
        "\n=== SIH 2026 Narcotics/Explosives "
        "Sniffer Booting ==="
    );


    // Hardware
    actuators.init();

    sensorHub.init();


    // Wi-Fi
    connectToWiFi();


    // MQTT
    mqttClient.setServer(
        MQTT_SERVER,
        MQTT_PORT
    );


    // Start in PURGE
    currentState =
        STATE_PURGE;

    stateStartTime =
        millis();

    lastTelemetryTime =
        millis();
}


// ==========================================
// Main Loop
// ==========================================

void loop() {

    // ======================================
    // 1. Maintain MQTT connection
    // ======================================

    if (
        !mqttClient.connected()
    ) {

        connectToMQTT();
    }

    mqttClient.loop();


    // ======================================
    // 2. Calculate elapsed time
    // ======================================

    unsigned long now =
        millis();

    unsigned long elapsed =
        now - stateStartTime;


    // ======================================
    // 3. State Machine
    // ======================================

    switch (currentState) {


        // ----------------------------------
        // PURGE
        // ----------------------------------

        case STATE_PURGE: {

            actuators.setPump(true);

            actuators.setThreatAlert(false);

            sensorHub.updateScreen(
                "PURGE",
                snapshot.ambientTemp,
                snapshot.rawSgpVoc,
                false
            );


            if (
                elapsed >= TIME_PURGE
            ) {

                currentState =
                    STATE_SAMPLE;

                stateStartTime =
                    millis();

                Serial.println(
                    "[FSM] PURGE -> SAMPLE"
                );
            }

            break;
        }


        // ----------------------------------
        // SAMPLE
        // ----------------------------------

        case STATE_SAMPLE: {

            actuators.setPump(true);

            actuators.setThreatAlert(
                threatDetected
            );

            sensorHub.updateScreen(
                "SAMPLE",
                snapshot.ambientTemp,
                snapshot.rawSgpVoc,
                threatDetected
            );


            if (
                elapsed >= TIME_SAMPLE
            ) {

                currentState =
                    STATE_PURGE;

                stateStartTime =
                    millis();

                Serial.println(
                    "[FSM] SAMPLE -> PURGE"
                );
            }

            break;
        }
    }


    // ======================================
    // 4. Sensor Reading + MQTT Telemetry
    // ======================================

    if (
        now - lastTelemetryTime
        >= TELEMETRY_INTERVAL
    ) {

        snapshot =
            sensorHub.readAll();


        // ==================================
        // IMPORTANT:
        // No raw VOC threshold detection yet.
        // ==================================

        threatDetected =
            false;


        // Send telemetry
        sendTelemetry(
            getStateName(),
            snapshot,
            threatDetected
        );


        lastTelemetryTime =
            now;
    }


    // ======================================
    // 5. Small CPU delay
    // ======================================

    delay(10);
}