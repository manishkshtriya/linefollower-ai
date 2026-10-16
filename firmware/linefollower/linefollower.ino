// AI line follower car: 4 IR sensors -> small neural network -> 2 motors.
// Board: ESP32 DevKit (Arduino core 3.x). Motor driver: TB6612FNG.
// Not yet tested on a real car. Start with the wheels off the ground and tune the values below.
// Mount the four sensors about 20 mm apart (centre to centre) for 19 mm tape. The simulator in sim/ shows why.

#include "nn.h"

// ---- Pins ----
const int SENSOR_PIN[4] = {34, 35, 32, 33};  // S1 (far left) ... S4 (far right), looking forward
const int PWMA = 25, AIN1 = 26, AIN2 = 27;   // left motor
const int PWMB = 4,  BIN1 = 16, BIN2 = 17;   // right motor
const int STBY = 23;                         // driver standby, must be HIGH to run

// ---- Settings to tune ----
const bool LINE_IS_HIGH = true;     // true if the sensor module outputs HIGH over the line. Check with sensor_test.
const bool LEFT_REVERSED = false;   // set true if the left wheel turns backwards
const bool RIGHT_REVERSED = false;  // set true if the right wheel turns backwards
const int  MIN_DUTY = 70;           // lowest PWM (0-255) that makes your motors turn
const int  MAX_DUTY = 255;
const unsigned long LOST_STOP_MS = 3000;  // stop if no sensor sees the line for this long
const unsigned long LOOP_MS = 5;          // 200 control steps per second
const bool DEBUG = true;

const int PWM_FREQ = 20000, PWM_BITS = 8;
unsigned long lastSeenMs = 0, lastPrintMs = 0, lastLoopMs = 0;

void setMotor(int pwmPin, int in1, int in2, float speed, bool reversed) {
  bool fwd = !reversed;
  digitalWrite(in1, fwd ? HIGH : LOW);
  digitalWrite(in2, fwd ? LOW : HIGH);
  int duty = 0;
  if (speed >= 0.05f) duty = MIN_DUTY + (int)(speed * (MAX_DUTY - MIN_DUTY));
  ledcWrite(pwmPin, duty);
}

void stopMotors() {
  ledcWrite(PWMA, 0);
  ledcWrite(PWMB, 0);
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 4; i++) pinMode(SENSOR_PIN[i], INPUT);
  pinMode(AIN1, OUTPUT); pinMode(AIN2, OUTPUT);
  pinMode(BIN1, OUTPUT); pinMode(BIN2, OUTPUT);
  pinMode(STBY, OUTPUT); digitalWrite(STBY, HIGH);
  ledcAttach(PWMA, PWM_FREQ, PWM_BITS);  // Arduino-ESP32 core 3.x. On core 2.x use ledcSetup and ledcAttachPin.
  ledcAttach(PWMB, PWM_FREQ, PWM_BITS);
  stopMotors();
  lastSeenMs = millis();
  delay(1000);  // time to put the car on the line
}

void loop() {
  unsigned long now = millis();
  if (now - lastLoopMs < LOOP_MS) return;
  lastLoopMs = now;

  float in[NN_IN];
  int any = 0;
  for (int i = 0; i < 4; i++) {
    bool high = digitalRead(SENSOR_PIN[i]) == HIGH;
    bool onLine = LINE_IS_HIGH ? high : !high;
    in[i] = onLine ? 1.0f : 0.0f;
    any |= onLine;
  }
  if (any) lastSeenMs = now;

  if (now - lastSeenMs > LOST_STOP_MS) {  // lost the line for too long: stop until it is found again
    stopMotors();
    return;
  }

  float out[NN_OUT];
  nn_forward(in, out);  // out[0] = left motor 0..1, out[1] = right motor 0..1
  setMotor(PWMA, AIN1, AIN2, out[0], LEFT_REVERSED);
  setMotor(PWMB, BIN1, BIN2, out[1], RIGHT_REVERSED);

  if (DEBUG && now - lastPrintMs > 200) {
    lastPrintMs = now;
    Serial.printf("%d%d%d%d  L=%.2f R=%.2f\n", (int)in[0], (int)in[1], (int)in[2], (int)in[3], out[0], out[1]);
  }
}
