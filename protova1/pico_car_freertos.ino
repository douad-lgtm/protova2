#define __FREERTOS 1
#include <Arduino.h>
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include <Wire.h>
#include <Servo.h>
#include "hardware/gpio.h"
#include "hardware/adc.h"
// #include "SparkFun_BNO08x_Arduino_Library.h"  // IMU désactivé

// ================== CONFIG ==================
#define SERVO_PIN    15
#define ESC_PIN      16
#define PIN_CLK       2
#define PIN_DT        3
#define I2C_SDA       4
#define I2C_SCL       5

#define SERVO_CENTER          83
#define SERVO_RANGE           55.0
#define VELOCITY_UPDATE_PERIOD_MS 20
// #define IMU_UPDATE_PERIOD_MS      20  // IMU désactivé

const int NEUTRAL  = 1500;   // corrige 2026-08-03 : 1400 = marche arriere sur CET ESC (neutre reel = 1500, cf. test_pico.py)
const int FULL_FWD = 2080;
const int FULL_BWD = 720;

// ================== ENCODEUR KY-040 ==================
// Comme ProtoVA2 : front MONTANT uniquement -> 20 ticks/tour
volatile int tickCount = 0;

// Filtre passe-bas
float filteredTicks = 0.0f;
const float ALPHA   = 0.3f;  // 0 = très filtré, 1 = pas filtré

void encoderISR() {
    if (digitalRead(PIN_DT))
        tickCount++;   // sens 1
    else
        tickCount--;   // sens opposé
}

// ================= IMU (désactivé) =================
// BNO08x imu;
// bool imu_ok = false;

// ================= STRUCTURES =================
typedef struct {
    int   angle;
    float throttle;
} ControlMsg;

QueueHandle_t controlQueue;
Servo servo;
Servo esc;

// ================= THROTTLE =================
void setThrottle(float x) {
    x = constrain(x, -1.0f, 1.0f);
    int pwm = NEUTRAL;
    if (x > 0)
        pwm = NEUTRAL + (int)((FULL_FWD - NEUTRAL) * x);
    else if (x < 0)
        pwm = NEUTRAL + (int)((NEUTRAL - FULL_BWD) * x);
    esc.writeMicroseconds(pwm);
}

// ================= SERIAL RX =================
void TaskSerialRX(void *) {
    String line;
    ControlMsg msg;
    for (;;) {
        while (Serial.available()) {
            line = Serial.readStringUntil('\n');
            line.trim();
            if (!line.startsWith("CTRL"))
                continue;
            int c1 = line.indexOf(',');
            int c2 = line.indexOf(',', c1 + 1);
            if (c1 < 0 || c2 < 0)
                continue;
            msg.angle    = line.substring(c1 + 1, c2).toInt();
            msg.throttle = line.substring(c2 + 1).toFloat();
            xQueueOverwrite(controlQueue, &msg);
        }
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

// ================= CONTROL =================
void TaskControl(void *) {
    ControlMsg msg;
    for (;;) {
        if (xQueueReceive(controlQueue, &msg, 0) == pdTRUE) {
            servo.write(msg.angle);
            setThrottle(msg.throttle);
        }
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

// ================= ENCODEUR TASK =================
// FIX 2 : utilise tickCount (et non tick_count) + filtre passe-bas intégré
void TaskEncoder(void *) {
    for (;;) {
        // Lecture atomique + remise à zéro
        noInterrupts();
        int delta  = tickCount;
        tickCount  = 0;
        interrupts();

        // Filtre passe-bas
        filteredTicks = ALPHA * (float)delta + (1.0f - ALPHA) * filteredTicks;
        int ticksToSend = (int)roundf(filteredTicks);

        // Format attendu par RX.py / TX.py
        Serial.print("TICKS,");
        Serial.println(ticksToSend);

        vTaskDelay(pdMS_TO_TICKS(VELOCITY_UPDATE_PERIOD_MS));
    }
}

// ================= IMU TASK (désactivé) =================
/*
void TaskIMU(void *) {
    for (;;) {
        if (!imu_ok) {
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }

        if (imu.wasReset()) {
            imu.enableRotationVector(10);
            imu.enableAccelerometer(10);
            imu.enableGyro(10);
        }

        if (imu.getSensorEvent()) {
            if (imu.getSensorEventID() == SENSOR_REPORTID_ROTATION_VECTOR) {
                float qw = imu.getQuatReal();
                float qx = imu.getQuatI();
                float qy = imu.getQuatJ();
                float qz = imu.getQuatK();

                float yaw = atan2f(
                    2.0f * (qw * qz + qx * qy),
                    1.0f - 2.0f * (qy * qy + qz * qz)
                ) * 180.0f / M_PI;

                Serial.print("IMU,");
                Serial.print(qw, 4); Serial.print(",");
                Serial.print(qx, 4); Serial.print(",");
                Serial.print(qy, 4); Serial.print(",");
                Serial.print(qz, 4); Serial.print(",");
                Serial.println(yaw, 2);
            }
        }

        vTaskDelay(pdMS_TO_TICKS(IMU_UPDATE_PERIOD_MS));
    }
}
*/

// ================= SETUP =================
// FIX 3 : un seul setup() — le setup() "exemple" du bas a été supprimé
void setup() {
    Serial.begin(115200);
    while (!Serial) delay(10);
    delay(500);

    Serial.println("=== Protova1 Boot ===");

    // I2C + IMU désactivés
    // Wire.setSDA(I2C_SDA);
    // Wire.setSCL(I2C_SCL);
    // Wire.begin();

    // Serial.println("Scan I2C...");
    // for (byte addr = 1; addr < 127; addr++) {
    //     Wire.beginTransmission(addr);
    //     byte err = Wire.endTransmission();
    //     if (err == 0) {
    //         Serial.print("Dispositif trouve a : 0x");
    //         Serial.println(addr, HEX);
    //     }
    // }
    // Serial.println("Scan termine");
    // delay(200);

    // Serial.println("Init IMU...");
    // if (imu.begin(0x4B, Wire)) {
    //     imu.enableRotationVector(10);
    //     imu.enableAccelerometer(10);
    //     imu.enableGyro(10);
    //     imu_ok = true;
    //     Serial.println("IMU OK");
    // } else {
    //     imu_ok = false;
    //     Serial.println("IMU ERREUR — verifie branchement SDA/SCL");
    // }

    // Servo + ESC
    servo.attach(SERVO_PIN);
    esc.attach(ESC_PIN, FULL_BWD, FULL_FWD);
    servo.write(SERVO_CENTER);
    esc.writeMicroseconds(NEUTRAL);
    delay(2000);

    // Encodeur KY-040
    pinMode(PIN_CLK, INPUT_PULLUP);
    pinMode(PIN_DT,  INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(PIN_CLK), encoderISR, RISING);  // comme ProtoVA2

    // Queue + Tasks FreeRTOS
    controlQueue = xQueueCreate(1, sizeof(ControlMsg));

    xTaskCreate(TaskSerialRX, "RX",   2048, NULL, 2, NULL);
    xTaskCreate(TaskControl,  "CTRL", 2048, NULL, 2, NULL);
    xTaskCreate(TaskEncoder,  "ENC",  1024, NULL, 1, NULL);
    // xTaskCreate(TaskIMU,      "IMU",  2048, NULL, 1, NULL);  // IMU désactivé

    Serial.println("System READY");
}

void loop() {}
