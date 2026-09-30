#pragma once

#include <Arduino.h>
#include "pinout.h"

class Actuators {
public:
    void init() {
        pinMode(PIN_PUMP_GATE, OUTPUT);
        pinMode(PIN_BUZZER, OUTPUT);

        allOff();
    }

    void setPump(bool enabled) {
        digitalWrite(PIN_PUMP_GATE, enabled ? HIGH : LOW);
    }

    void setThreatAlert(bool triggered) {
        digitalWrite(PIN_BUZZER, triggered ? HIGH : LOW);
    }

    void allOff() {
        digitalWrite(PIN_PUMP_GATE, LOW);
        digitalWrite(PIN_BUZZER, LOW);
    }
};