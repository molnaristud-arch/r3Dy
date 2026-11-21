// Turntable driver: 28BYJ-48 stepper + ULN2003 board on an Arduino Uno/Nano.
//
// Two modes:
//   STEP (default): rotate 360/N degrees, wait until the platform is still, print "FOTO k/N" and beep,
//                   hold still for DWELL ms (the photo is taken by hand meanwhile), repeat N times.
//                   The beep is optional: with no buzzer on D7 it does nothing.
//   CONT:           continuous rotation at RPM (for video mode; ~1 RPM recommended).
//
// Controls: push button on pin 2 (to GND) = start STEP / stop.  Serial monitor at 115200 baud:
//   s = start STEP   c = start CONT   x = stop   ? = status
//   n36 = stops per turn   d2500 = dwell ms   r1.0 = RPM in CONT   b0 / b1 = beep off / on
//
// Wiring: ULN2003 IN1..IN4 → D8..D11, board + → 5V, - → GND (USB power is enough for one 28BYJ-48).
//         Optional piezo buzzer + → D7, - → GND (not used by us).  Button: D2 ↔ GND (optional).
// See README.md next to this file.

const uint8_t COIL_PINS[4] = {8, 9, 10, 11};
const uint8_t BUTTON_PIN = 2;
const uint8_t BUZZER_PIN = 7;

// 28BYJ-48 in half-step mode: 64 half-steps per motor turn x 63.68 gearbox ≈ 4076 per output turn.
// (The often quoted 4096 is 0.5 % off: 1.8° per turn; it would not break photogrammetry either.)
const float STEPS_PER_REV = 4075.77f;
const uint8_t HALF_STEP[8][4] = {
  {1, 0, 0, 0}, {1, 1, 0, 0}, {0, 1, 0, 0}, {0, 1, 1, 0},
  {0, 0, 1, 0}, {0, 0, 1, 1}, {0, 0, 0, 1}, {1, 0, 0, 1},
};

const unsigned long MOVE_STEP_US = 2000;   // half-step period while moving between stops (~7 RPM, gentle)
const unsigned long RAMP_STEP_US = 4000;   // start/end of each move are slower so the object doesn't jerk
const uint8_t RAMP_STEPS = 20;
const unsigned long SETTLE_MS = 600;       // wait for the platform/object to stop wobbling
const unsigned long BEEP_MS = 150;

// Settings (changeable over serial)
int stops = 36;
unsigned long dwellMs = 2500;
float rpm = 1.0f;
bool beepOn = true;

enum Mode { IDLE, STEP_MOVE, STEP_SETTLE, STEP_DWELL, CONT };
Mode mode = IDLE;

long position = 0;          // half-steps since start
long target = 0;
long moveStart = 0;
int stopIndex = 0;          // photo number in the current turn (0 = first)
uint8_t phase = 0;
unsigned long lastStepUs = 0;
unsigned long stateStartMs = 0;
unsigned long contStepUs = 0;
bool lastButton = HIGH;
unsigned long lastButtonMs = 0;
char line[16];
uint8_t lineLen = 0;

void coils(bool on) {
  for (uint8_t i = 0; i < 4; i++) digitalWrite(COIL_PINS[i], on ? HALF_STEP[phase][i] : LOW);
}

void stepOnce() {
  phase = (phase + 1) & 7;
  coils(true);
  position++;
}

void beep() {
  if (!beepOn) return;
  tone(BUZZER_PIN, 3000, BEEP_MS);  // passive buzzer: 3 kHz; an active buzzer just sounds
  digitalWrite(LED_BUILTIN, HIGH);
}

long stopPosition(int k) {
  return (long)(k * STEPS_PER_REV / stops + 0.5f);
}

void startStep() {
  position = 0;
  stopIndex = 0;
  mode = STEP_SETTLE;  // first photo at the starting position
  stateStartMs = millis();
  Serial.print(F("START: lepteto mod, "));
  Serial.print(stops);
  Serial.print(F(" megallas, "));
  Serial.print(360.0f / stops, 1);
  Serial.println(F(" fokonkent"));
}

void startCont() {
  contStepUs = (unsigned long)(60.0e6f / (rpm * STEPS_PER_REV));
  mode = CONT;
  lastStepUs = micros();
  Serial.print(F("START: folyamatos, "));
  Serial.print(rpm, 2);
  Serial.println(F(" RPM"));
}

void stopAll(const __FlashStringHelper *why) {
  mode = IDLE;
  coils(false);  // the gearbox holds the platform; unpowered coils don't heat up
  noTone(BUZZER_PIN);
  digitalWrite(LED_BUILTIN, LOW);
  Serial.println(why);
}

void status() {
  Serial.print(F("mod="));
  const char *names[] = {"IDLE", "STEP_MOVE", "STEP_SETTLE", "STEP_DWELL", "CONT"};
  Serial.print(names[mode]);
  Serial.print(F(" n="));
  Serial.print(stops);
  Serial.print(F(" d="));
  Serial.print(dwellMs);
  Serial.print(F(" r="));
  Serial.print(rpm, 2);
  Serial.print(F(" b="));
  Serial.print(beepOn ? 1 : 0);
  Serial.print(F(" foto="));
  Serial.println(stopIndex);
}

void command(const char *c) {
  float v = atof(c + 1);
  switch (c[0]) {
    case 's': startStep(); break;
    case 'c': startCont(); break;
    case 'x': stopAll(F("STOP")); break;
    case '?': status(); break;
    case 'n': if (v >= 4 && v <= 360) stops = (int)v; status(); break;
    case 'd': if (v >= 300 && v <= 60000) dwellMs = (unsigned long)v; status(); break;
    case 'r': if (v > 0.05f && v <= 10) rpm = v; if (mode == CONT) startCont(); status(); break;
    case 'b': beepOn = v != 0; status(); break;
    default: Serial.println(F("? parancsok: s c x ? n36 d2500 r1.0 b0/b1"));
  }
}

void readSerial() {
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n' || ch == '\r') {
      if (lineLen) { line[lineLen] = 0; command(line); lineLen = 0; }
    } else if (lineLen < sizeof(line) - 1) {
      line[lineLen++] = ch;
    }
  }
}

void readButton() {
  bool b = digitalRead(BUTTON_PIN);
  if (b != lastButton && millis() - lastButtonMs > 50) {
    lastButtonMs = millis();
    lastButton = b;
    if (b == LOW) {
      if (mode == IDLE) startStep(); else stopAll(F("STOP (gomb)"));
    }
  }
}

void setup() {
  for (uint8_t i = 0; i < 4; i++) pinMode(COIL_PINS[i], OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  coils(false);
  Serial.begin(115200);
  Serial.println(F("Forgoasztal kesz. Gomb vagy 's' = lepteto mod, 'c' = folyamatos, 'x' = stop, '?' = allapot"));
}

void loop() {
  readSerial();
  readButton();
  unsigned long nowUs = micros();
  unsigned long nowMs = millis();

  switch (mode) {
    case IDLE:
      break;

    case STEP_MOVE: {
      long done = position - moveStart, left = target - position;
      unsigned long period = (done < RAMP_STEPS || left <= RAMP_STEPS) ? RAMP_STEP_US : MOVE_STEP_US;
      if (nowUs - lastStepUs >= period) {
        lastStepUs = nowUs;
        stepOnce();
        if (position >= target) {
          coils(false);
          mode = STEP_SETTLE;
          stateStartMs = nowMs;
        }
      }
      break;
    }

    case STEP_SETTLE:
      if (nowMs - stateStartMs >= SETTLE_MS) {
        beep();
        Serial.print(F("FOTO "));
        Serial.print(stopIndex + 1);
        Serial.print('/');
        Serial.println(stops);
        mode = STEP_DWELL;
        stateStartMs = nowMs;
      }
      break;

    case STEP_DWELL:
      if (nowMs - stateStartMs >= BEEP_MS) digitalWrite(LED_BUILTIN, LOW);
      if (nowMs - stateStartMs >= dwellMs) {
        stopIndex++;
        if (stopIndex >= stops) {
          stopAll(F("KESZ: egy teljes kor. Emeld meg a telefont, es nyomd meg ujra a gombot."));
          break;
        }
        moveStart = position;
        target = stopPosition(stopIndex);
        mode = STEP_MOVE;
        lastStepUs = nowUs;
      }
      break;

    case CONT:
      if (nowUs - lastStepUs >= contStepUs) {
        lastStepUs += contStepUs;  // keeps the average speed exact
        stepOnce();
      }
      break;
  }
}
