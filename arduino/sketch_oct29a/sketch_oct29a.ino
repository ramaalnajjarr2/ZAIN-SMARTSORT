#include <Servo.h>
Servo paperServo; Servo plasticServo; Servo metalServo;
const int CLOSED = 90; const int OPEN = 160;
void setup() { Serial.begin(9600);
paperServo.attach(9); plasticServo.attach(10); metalServo.attach(11);
paperServo.write(CLOSED); plasticServo.write(CLOSED); metalServo.write(CLOSED);
Serial.setTimeout(100); Serial.println("READY"); }
void loop() { if (Serial.available() > 0) { String command = Serial.readStringUntil('\n'); command.trim();
if (command == "PAPER") {
  openBin(paperServo);
}
else if (command == "PLASTIC") {
  openBin(plasticServo);
}
else if (command == "METAL") {
  openBin(metalServo);
}
} }
void openBin(Servo &motor) { Serial.println("BUSY");
motor.write(OPEN); delay(3000);
motor.write(CLOSED); delay(700);
Serial.println("DONE"); }