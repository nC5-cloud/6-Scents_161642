#pragma once

#include <Wire.h>
#include <SensirionI2CSgp41.h>
#include <Adafruit_SHT4x.h>
#include <Adafruit_BME680.h>

// ==========================================
// OLED driver
// 1.3" OLED modules = SH1106
// ==========================================

#include <Adafruit_SH110X.h>

using OledDisplay = Adafruit_SH1106G;

#define OLED_WHITE SH110X_WHITE

constexpr uint8_t OLED_ADDR = 0x3C;

#include "pinout.h"


// ==========================================
// Telemetry Structure
// ==========================================

struct TelemetrySnapshot {

    float ambientTemp =
        0.0f;

    float ambientHumidity =
        0.0f;

    uint16_t rawSgpVoc =
        0;

    uint16_t rawSgpNox =
        0;

    float bmeGasResistance =
        0.0f;
};


// ==========================================
// Sensor Hub
// ==========================================

class SensorHub {

private:

    SensirionI2CSgp41 sgp41;

    Adafruit_SHT4x sht40;

    Adafruit_BME680 bme688;

    // Working OLED implementation
    OledDisplay display;


    bool shtOk =
        false;

    bool bmeOk =
        false;

    bool oledOk =
        false;


    // ==========================================
    // Convert Humidity to SGP41 ticks
    // ==========================================

    uint16_t humidityToTicks(
        float humidity
    ) {

        humidity =
            constrain(
                humidity,
                0.0f,
                100.0f
            );

        return static_cast<uint16_t>(
            humidity *
            65535.0f /
            100.0f
        );
    }


    // ==========================================
    // Convert Temperature to SGP41 ticks
    // ==========================================

    uint16_t temperatureToTicks(
        float temperature
    ) {

        temperature =
            constrain(
                temperature,
                -45.0f,
                130.0f
            );

        return static_cast<uint16_t>(
            (temperature + 45.0f) *
            65535.0f /
            175.0f
        );
    }


    // ==========================================
    // Read SHT40
    // ==========================================

    bool readSHT40Environment(
        float &temperature,
        float &humidity
    ) {

        if (!shtOk) {
            return false;
        }

        sensors_event_t humidityEvent;
        sensors_event_t temperatureEvent;

        if (
            !sht40.getEvent(
                &humidityEvent,
                &temperatureEvent
            )
        ) {
            return false;
        }

        temperature =
            temperatureEvent.temperature;

        humidity =
            humidityEvent.relative_humidity;

        return true;
    }


    // ==========================================
    // Read BME688
    // ==========================================

    bool readBME688(
        float &temperature,
        float &humidity,
        float &gasResistance
    ) {

        if (!bmeOk) {
            return false;
        }

        if (
            !bme688.performReading()
        ) {
            return false;
        }

        temperature =
            bme688.temperature;

        humidity =
            bme688.humidity;

        gasResistance =
            bme688.gas_resistance;

        return true;
    }


    // ==========================================
    // OLED Boot Message
    // ==========================================

    void bootMessage(
        const char* line
    ) {

        if (!oledOk) {
            return;
        }

        display.clearDisplay();

        display.setCursor(
            0,
            0
        );

        display.println(
            "SIH Sniffer Booting"
        );

        display.println();

        display.println(
            line
        );

        display.display();
    }


public:

    // ==========================================
    // Constructor
    // ==========================================

    SensorHub()
        : display(
            128,
            64,
            &Wire,
            -1
        ) {}


    // ==========================================
    // INITIALIZATION
    // ==========================================

    bool init() {

        Wire.begin(
            PIN_I2C_SDA,
            PIN_I2C_SCL,
            100000
        );

        bool allOk =
            true;


        // ======================================
        // OLED FIRST
        // ======================================

        oledOk =
            display.begin(
                OLED_ADDR,
                true
            );

        if (oledOk) {

            display.clearDisplay();

            display.setTextSize(
                1
            );

            display.setTextColor(
                OLED_WHITE
            );

            display.setTextWrap(
                false
            );

            display.display();

            Serial.println(
                "[SENSOR] OLED initialized."
            );

            bootMessage(
                "Init sensors..."
            );

        }

        else {

            Serial.println(
                "[WARN] OLED not found at 0x3C!"
            );

            allOk =
                false;
        }


        // ======================================
        // SHT40
        // ======================================

        if (
            sht40.begin(
                &Wire
            )
        ) {

            shtOk =
                true;

            Serial.println(
                "[SENSOR] SHT40 found at 0x44."
            );

            sht40.setPrecision(
                SHT4X_HIGH_PRECISION
            );

            sht40.setHeater(
                SHT4X_NO_HEATER
            );

        }

        else {

            Serial.println(
                "[WARN] SHT40 not detected at 0x44!"
            );

            allOk =
                false;
        }


        // ======================================
        // BME688
        // ======================================

        if (
            bme688.begin(
                0x76
            )
        ) {

            bmeOk =
                true;

            Serial.println(
                "[SENSOR] BME688 found at 0x76."
            );

        }

        else if (
            bme688.begin(
                0x77
            )
        ) {

            bmeOk =
                true;

            Serial.println(
                "[SENSOR] BME688 found at 0x77."
            );
        }


        if (!bmeOk) {

            Serial.println(
                "[WARN] BME688 not detected!"
            );

            allOk =
                false;

        }

        else {

            bme688.setTemperatureOversampling(
                BME680_OS_8X
            );

            bme688.setHumidityOversampling(
                BME680_OS_2X
            );

            bme688.setPressureOversampling(
                BME680_OS_NONE
            );

            bme688.setGasHeater(
                320,
                150
            );

            Serial.println(
                "[SENSOR] BME688 configured."
            );
        }


        // ======================================
        // SGP41
        // ======================================

        sgp41.begin(
            Wire
        );

        Serial.println(
            "[SENSOR] SGP41 interface initialized."
        );


        // ======================================
        // SGP41 CONDITIONING
        // ======================================

        Serial.println(
            "[SENSOR] Starting SGP41 conditioning "
            "(10 s)..."
        );


        for (
            int i = 0;
            i < 10;
            i++
        ) {

            float temperature =
                25.0f;

            float humidity =
                50.0f;


            // ----------------------------------
            // Prefer SHT40
            // ----------------------------------

            if (
                readSHT40Environment(
                    temperature,
                    humidity
                )
            ) {

                Serial.printf(
                    "[SHT40] Conditioning: "
                    "Temp=%.2f C | RH=%.2f %%\n",
                    temperature,
                    humidity
                );

            }


            // ----------------------------------
            // Fallback to BME688
            // ----------------------------------

            else {

                float bmeTemp =
                    25.0f;

                float bmeHum =
                    50.0f;

                float bmeGas =
                    0.0f;


                if (
                    readBME688(
                        bmeTemp,
                        bmeHum,
                        bmeGas
                    )
                ) {

                    temperature =
                        bmeTemp;

                    humidity =
                        bmeHum;

                    Serial.printf(
                        "[BME688] Conditioning: "
                        "Temp=%.2f C | RH=%.2f %%\n",
                        temperature,
                        humidity
                    );

                }

                else {

                    Serial.println(
                        "[WARN] Env read failed. "
                        "Using 25 C / 50 % RH."
                    );
                }
            }


            // ----------------------------------
            // SGP41 conditioning
            // ----------------------------------

            uint16_t conditioningVoc =
                0;

            uint16_t sgpError =
                sgp41.executeConditioning(
                    humidityToTicks(
                        humidity
                    ),
                    temperatureToTicks(
                        temperature
                    ),
                    conditioningVoc
                );


            if (
                sgpError == 0
            ) {

                Serial.printf(
                    "[SENSOR] SGP41 conditioning "
                    "%d/10 | VOC=%u\n",
                    i + 1,
                    conditioningVoc
                );

            }

            else {

                Serial.printf(
                    "[WARN] SGP41 conditioning error: %u\n",
                    sgpError
                );
            }


            // ----------------------------------
            // OLED conditioning status
            // ----------------------------------

            char msg[22];

            snprintf(
                msg,
                sizeof(msg),
                "SGP41 cond %d/10",
                i + 1
            );

            bootMessage(
                msg
            );


            delay(1000);
        }


        Serial.println(
            "[SENSOR] SGP41 conditioning complete."
        );

        bootMessage(
            "Ready."
        );


        return allOk;
    }


    // ==========================================
    // READ ALL SENSORS
    // ==========================================

    TelemetrySnapshot readAll() {

        TelemetrySnapshot data;


        // ======================================
        // 1. SHT40
        // Primary temperature + humidity
        // ======================================

        if (
            readSHT40Environment(
                data.ambientTemp,
                data.ambientHumidity
            )
        ) {

            Serial.printf(
                "[SHT40] Temp=%.2f C | RH=%.2f %%\n",
                data.ambientTemp,
                data.ambientHumidity
            );

        }

        else {

            Serial.println(
                "[WARN] SHT40 read failed. "
                "Trying BME688."
            );


            // ----------------------------------
            // BME688 fallback
            // ----------------------------------

            float bmeTemp =
                25.0f;

            float bmeHum =
                50.0f;

            float bmeGas =
                0.0f;


            if (
                readBME688(
                    bmeTemp,
                    bmeHum,
                    bmeGas
                )
            ) {

                data.ambientTemp =
                    bmeTemp;

                data.ambientHumidity =
                    bmeHum;
            }
        }


        // ======================================
        // 2. BME688 Gas Resistance
        // ======================================

        if (bmeOk) {

            if (
                bme688.performReading()
            ) {

                data.bmeGasResistance =
                    bme688.gas_resistance;

            }

            else {

                Serial.println(
                    "[WARN] BME688 gas reading failed."
                );
            }
        }


        // ======================================
        // 3. SGP41
        // ======================================

        uint16_t compRh =
            humidityToTicks(
                data.ambientHumidity
            );

        uint16_t compT =
            temperatureToTicks(
                data.ambientTemp
            );


        uint16_t vocRaw =
            0;

        uint16_t noxRaw =
            0;


        uint16_t sgpError =
            sgp41.measureRawSignals(
                compRh,
                compT,
                vocRaw,
                noxRaw
            );


        if (
            sgpError == 0
        ) {

            data.rawSgpVoc =
                vocRaw;

            data.rawSgpNox =
                noxRaw;

        }

        else {

            Serial.printf(
                "[WARN] SGP41 measurement error: %u\n",
                sgpError
            );

            data.rawSgpVoc =
                0;

            data.rawSgpNox =
                0;
        }


        return data;
    }


    // ==========================================
    // OLED DISPLAY
    // ==========================================

    void updateScreen(
        const char* stateName,
        float temp,
        uint16_t voc,
        bool threat
    ) {

        if (!oledOk) {
            return;
        }


        display.clearDisplay();

        display.setCursor(
            0,
            0
        );


        display.printf(
            "STATE: %s\n",
            stateName
        );


        display.printf(
            "SHT40: %.1f C\n",
            temp
        );


        display.printf(
            "VOC: %u\n",
            voc
        );


        display.println();


        if (threat) {

            display.println(
                "*** THREAT DETECTED ***"
            );

        }

        else {

            display.println(
                "Status: Monitoring"
            );
        }


        display.display();
    }
};