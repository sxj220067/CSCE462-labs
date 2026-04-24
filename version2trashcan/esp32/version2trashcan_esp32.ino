#include "BluetoothSerial.h"

BluetoothSerial SerialBT;

const int LEFT_IN1 = 25;
const int LEFT_IN2 = 26;
const int RIGHT_IN1 = 27;
const int RIGHT_IN2 = 14;
const int LEFT_ENABLE = 33;
const int RIGHT_ENABLE = 32;

const int DRIVE_PWM = 210;
const int TURN_PWM = 200;

void logState(const char *message) {
  Serial.print("[ESP32] ");
  Serial.println(message);
}

void stopMotors() {
  ledcWrite(LEFT_ENABLE, 0);
  ledcWrite(RIGHT_ENABLE, 0);
  digitalWrite(LEFT_IN1, LOW);
  digitalWrite(LEFT_IN2, LOW);
  digitalWrite(RIGHT_IN1, LOW);
  digitalWrite(RIGHT_IN2, LOW);
  logState("STOP");
}

void moveForward() {
  digitalWrite(LEFT_IN1, HIGH);
  digitalWrite(LEFT_IN2, LOW);
  digitalWrite(RIGHT_IN1, HIGH);
  digitalWrite(RIGHT_IN2, LOW);
  ledcWrite(LEFT_ENABLE, DRIVE_PWM);
  ledcWrite(RIGHT_ENABLE, DRIVE_PWM);
  logState("FORWARD");
}

void turnLeft() {
  digitalWrite(LEFT_IN1, LOW);
  digitalWrite(LEFT_IN2, HIGH);
  digitalWrite(RIGHT_IN1, HIGH);
  digitalWrite(RIGHT_IN2, LOW);
  ledcWrite(LEFT_ENABLE, TURN_PWM);
  ledcWrite(RIGHT_ENABLE, TURN_PWM);
  logState("LEFT");
}

void turnRight() {
  digitalWrite(LEFT_IN1, HIGH);
  digitalWrite(LEFT_IN2, LOW);
  digitalWrite(RIGHT_IN1, LOW);
  digitalWrite(RIGHT_IN2, HIGH);
  ledcWrite(LEFT_ENABLE, TURN_PWM);
  ledcWrite(RIGHT_ENABLE, TURN_PWM);
  logState("RIGHT");
}

void applyCommand(char command) {
  Serial.print("[ESP32] Received command: ");
  Serial.println(command);

  if (command == 'F') {
    moveForward();
  } else if (command == 'L') {
    turnLeft();
  } else if (command == 'R') {
    turnRight();
  } else {
    stopMotors();
  }
}

void setup() {
  Serial.begin(115200);
  SerialBT.begin("Version2TrashCan");

  pinMode(LEFT_IN1, OUTPUT);
  pinMode(LEFT_IN2, OUTPUT);
  pinMode(RIGHT_IN1, OUTPUT);
  pinMode(RIGHT_IN2, OUTPUT);

  ledcAttach(LEFT_ENABLE, 1000, 8);
  ledcAttach(RIGHT_ENABLE, 1000, 8);

  stopMotors();
  Serial.println("[ESP32] Version2TrashCan ESP32 ready");
  Serial.println("[ESP32] Bluetooth device name: Version2TrashCan");
}

void loop() {
  while (SerialBT.available()) {
    char command = (char) SerialBT.read();
    if (command == '\n' || command == '\r') {
      continue;
    }
    applyCommand(command);
  }
}
