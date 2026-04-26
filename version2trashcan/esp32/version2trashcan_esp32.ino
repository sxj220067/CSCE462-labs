#include "BluetoothSerial.h"

BluetoothSerial SerialBT;

const int LEFT_IN1 = 25;
const int LEFT_IN2 = 26;
const int RIGHT_IN1 = 27;
const int RIGHT_IN2 = 14;
const int LEFT_ENABLE = 33;
const int RIGHT_ENABLE = 32;

const int DRIVE_PWM = 255;
const int TURN_PWM = 255;

void logState(const char *message) {
  Serial.print("[ESP32] ");
  Serial.println(message);
}

void logPins() {
  Serial.print("[ESP32] pins L_IN1=");
  Serial.print(digitalRead(LEFT_IN1));
  Serial.print(" L_IN2=");
  Serial.print(digitalRead(LEFT_IN2));
  Serial.print(" R_IN1=");
  Serial.print(digitalRead(RIGHT_IN1));
  Serial.print(" R_IN2=");
  Serial.print(digitalRead(RIGHT_IN2));
  Serial.print(" L_PWM=");
  Serial.print(DRIVE_PWM);
  Serial.print(" R_PWM=");
  Serial.println(DRIVE_PWM);
}

void stopMotors() {
  ledcWrite(LEFT_ENABLE, 0);
  ledcWrite(RIGHT_ENABLE, 0);
  digitalWrite(LEFT_IN1, LOW);
  digitalWrite(LEFT_IN2, LOW);
  digitalWrite(RIGHT_IN1, LOW);
  digitalWrite(RIGHT_IN2, LOW);
  logState("STOP");
  logPins();
}

void moveForward() {
  digitalWrite(LEFT_IN1, HIGH);
  digitalWrite(LEFT_IN2, LOW);
  digitalWrite(RIGHT_IN1, HIGH);
  digitalWrite(RIGHT_IN2, LOW);
  ledcWrite(LEFT_ENABLE, DRIVE_PWM);
  ledcWrite(RIGHT_ENABLE, DRIVE_PWM);
  logState("FORWARD");
  logPins();
}

void turnLeft() {
  digitalWrite(LEFT_IN1, LOW);
  digitalWrite(LEFT_IN2, HIGH);
  digitalWrite(RIGHT_IN1, HIGH);
  digitalWrite(RIGHT_IN2, LOW);
  ledcWrite(LEFT_ENABLE, TURN_PWM);
  ledcWrite(RIGHT_ENABLE, TURN_PWM);
  logState("LEFT");
  logPins();
}

void turnRight() {
  digitalWrite(LEFT_IN1, HIGH);
  digitalWrite(LEFT_IN2, LOW);
  digitalWrite(RIGHT_IN1, LOW);
  digitalWrite(RIGHT_IN2, HIGH);
  ledcWrite(LEFT_ENABLE, TURN_PWM);
  ledcWrite(RIGHT_ENABLE, TURN_PWM);
  logState("RIGHT");
  logPins();
}

void runMotorSelfTest() {
  logState("SELF TEST START");
  moveForward();
  delay(1500);
  turnLeft();
  delay(1500);
  turnRight();
  delay(1500);
  stopMotors();
  logState("SELF TEST END");
}

void applyCommand(char command) {
  Serial.print("[ESP32] Received command: ");
  Serial.println(command);

  if (command == 'F') {
    moveForward();
  } else if (command == 'L') {
    turnRight();
  } else if (command == 'R') {
    turnLeft();
  } else if (command == 'T') {
    runMotorSelfTest();
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
    char command = (char) SerialBT.read();
    if (command == '\n' || command == '\r') {
      continue;
    }
    applyCommand(command);
  }
}
