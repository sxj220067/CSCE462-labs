#include "BluetoothSerial.h"

BluetoothSerial SerialBT;

const int LEFT_IN1 = 25;
const int LEFT_IN2 = 26;
const int RIGHT_IN1 = 27;
const int RIGHT_IN2 = 14;
const int LEFT_ENABLE = 33;
const int RIGHT_ENABLE = 32;

const int DRIVE_PWM = 255;
const int TURN_MIN_PWM = 150;
const int TURN_MAX_PWM = 255;
const int TURN_MIN_STRENGTH = 20;
const bool SWAP_TURN_DIRECTIONS = false;

String commandBuffer = "";

void logState(const char *message) {
  Serial.print("[ESP32] ");
  Serial.println(message);
}

void logPins(int leftPwm, int rightPwm) {
  Serial.print("[ESP32] pins L_IN1=");
  Serial.print(digitalRead(LEFT_IN1));
  Serial.print(" L_IN2=");
  Serial.print(digitalRead(LEFT_IN2));
  Serial.print(" R_IN1=");
  Serial.print(digitalRead(RIGHT_IN1));
  Serial.print(" R_IN2=");
  Serial.print(digitalRead(RIGHT_IN2));
  Serial.print(" L_PWM=");
  Serial.print(leftPwm);
  Serial.print(" R_PWM=");
  Serial.println(rightPwm);
}

void stopMotors() {
  ledcWrite(LEFT_ENABLE, 0);
  ledcWrite(RIGHT_ENABLE, 0);
  digitalWrite(LEFT_IN1, LOW);
  digitalWrite(LEFT_IN2, LOW);
  digitalWrite(RIGHT_IN1, LOW);
  digitalWrite(RIGHT_IN2, LOW);
  logState("STOP");
  logPins(0, 0);
}

void moveForward() {
  digitalWrite(LEFT_IN1, HIGH);
  digitalWrite(LEFT_IN2, LOW);
  digitalWrite(RIGHT_IN1, HIGH);
  digitalWrite(RIGHT_IN2, LOW);
  ledcWrite(LEFT_ENABLE, DRIVE_PWM);
  ledcWrite(RIGHT_ENABLE, DRIVE_PWM);
  logState("FORWARD");
  logPins(DRIVE_PWM, DRIVE_PWM);
}

int strengthToTurnPwm(int strength) {
  strength = constrain(strength, TURN_MIN_STRENGTH, 100);
  return map(strength, TURN_MIN_STRENGTH, 100, TURN_MIN_PWM, TURN_MAX_PWM);
}

void curveLeft(int strength = 100) {
  int turnPwm = strengthToTurnPwm(strength);
  digitalWrite(LEFT_IN1, LOW);
  digitalWrite(LEFT_IN2, LOW);
  digitalWrite(RIGHT_IN1, HIGH);
  digitalWrite(RIGHT_IN2, LOW);
  ledcWrite(LEFT_ENABLE, 0);
  ledcWrite(RIGHT_ENABLE, turnPwm);
  logState("LEFT CURVE");
  logPins(0, turnPwm);
}

void curveRight(int strength = 100) {
  int turnPwm = strengthToTurnPwm(strength);
  digitalWrite(LEFT_IN1, HIGH);
  digitalWrite(LEFT_IN2, LOW);
  digitalWrite(RIGHT_IN1, LOW);
  digitalWrite(RIGHT_IN2, LOW);
  ledcWrite(LEFT_ENABLE, turnPwm);
  ledcWrite(RIGHT_ENABLE, 0);
  logState("RIGHT CURVE");
  logPins(turnPwm, 0);
}

void runMotorSelfTest() {
  logState("SELF TEST START");
  moveForward();
  delay(1500);
  curveLeft();
  delay(1500);
  curveRight();
  delay(1500);
  stopMotors();
  logState("SELF TEST END");
}

void applyCommand(char command, int strength = 100) {
  Serial.print("[ESP32] Received command: ");
  Serial.println(command);
  Serial.print("[ESP32] Turn strength: ");
  Serial.println(strength);

  if (command == 'F') {
    moveForward();
  } else if (command == 'L') {
    if (SWAP_TURN_DIRECTIONS) {
      curveRight(strength);
    } else {
      curveLeft(strength);
    }
  } else if (command == 'R') {
    if (SWAP_TURN_DIRECTIONS) {
      curveLeft(strength);
    } else {
      curveRight(strength);
    }
  } else if (command == 'T') {
    runMotorSelfTest();
  } else {
    stopMotors();
  }
}

void applyCommandLine(String line) {
  line.trim();
  if (line.length() == 0) {
    return;
  }

  char command = line.charAt(0);
  int strength = 100;
  int separatorIndex = line.indexOf(':');
  if (separatorIndex >= 0 && separatorIndex < line.length() - 1) {
    strength = line.substring(separatorIndex + 1).toInt();
  }
  applyCommand(command, strength);
}

void setup() {
  Serial.begin(115200);
  SerialBT.begin("Version2TrashCan");

  pinMode(LEFT_IN1, OUTPUT);
  pinMode(LEFT_IN2, OUTPUT);
  pinMode(RIGHT_IN1, OUTPUT);
  pinMode(RIGHT_IN2, OUTPUT);
  pinMode(LEFT_ENABLE, OUTPUT);
  pinMode(RIGHT_ENABLE, OUTPUT);

  ledcAttach(LEFT_ENABLE, 1000, 8);
  ledcAttach(RIGHT_ENABLE, 1000, 8);

  stopMotors();
  Serial.println("[ESP32] Version2TrashCan ESP32 ready");
  Serial.println("[ESP32] Bluetooth device name: Version2TrashCan");
}

void loop() {
  while (SerialBT.available()) {
    char nextChar = (char) SerialBT.read();
    if (nextChar == '\n' || nextChar == '\r') {
      applyCommandLine(commandBuffer);
      commandBuffer = "";
      continue;
    }
    commandBuffer += nextChar;
  }
}
