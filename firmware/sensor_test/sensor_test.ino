// Step 1: check the four IR sensors before anything else.
// Open the Serial Monitor at 115200 baud. Slide the car over the tape and watch the pattern change.
// 1 means the sensor sees the line. If it is the other way round, set LINE_IS_HIGH to false in linefollower.ino.
// Turn the small potentiometer on each sensor module until it switches cleanly between floor and tape.

const int SENSOR_PIN[4] = {34, 35, 32, 33};  // S1 (far left) ... S4 (far right)
const bool LINE_IS_HIGH = true;

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 4; i++) pinMode(SENSOR_PIN[i], INPUT);
}

void loop() {
  char pattern[5];
  for (int i = 0; i < 4; i++) {
    bool high = digitalRead(SENSOR_PIN[i]) == HIGH;
    pattern[i] = (LINE_IS_HIGH ? high : !high) ? '1' : '0';
  }
  pattern[4] = 0;
  Serial.println(pattern);
  delay(100);
}
