/*
═══════════════════════════════════════════════════════════════════
                 APEX_PREDATOR v2.1 FIRMWARE
               Master/Slave Handshake Protocol

FIX LOG v2.1:
  BUG 1 FIXED: homing flags never cleared → now fully blocking/synchronous
  BUG 2 FIXED: command_received shared flag → split into move_command_pending
  BUG 3 FIXED: APEX_READY never sent → added to end of setup()
  BUG 4 FIXED: EN/DIS not recognized → added as aliases for MOTORS_EN/DIS
  BUG 5 FIXED: handle_homing() double-execution → removed from loop()

Hardware: Arduino Mega 2560 + RAMPS 1.6
Drivers:  DRV8825 @ 1/8 microstep, Vref=0.73V
Motors:   3x NEMA17 RMCS-1010 (5.6 kg-cm)
Switches: MS-114 SPDT wired NO (COM to GND, NO to signal pin)
═══════════════════════════════════════════════════════════════════
*/

#include <AccelStepper.h>
#include <Servo.h>

// ── PINS ─────────────────────────────────────────────────────────
#define X_STEP_PIN    54
#define X_DIR_PIN     55
#define Y_STEP_PIN    60
#define Y_DIR_PIN     61
#define Z_STEP_PIN    46
#define Z_DIR_PIN     48
#define X_ENABLE_PIN  38
#define Y_ENABLE_PIN  56
#define Z_ENABLE_PIN  62
#define X_MIN_PIN     3
#define Y_MIN_PIN     14
#define Z_MIN_PIN     18
// 2x MG90S diagonal opposite — top-left + bottom-right
#define SRV1_PIN      4    // Top Left
#define SRV2_PIN      11   // Bottom Right (diagonal)
#define TOOL_ID_PIN   A0

// ── MOTOR CONFIG ─────────────────────────────────────────────────
#define STEPS_PER_REV     200
#define MICROSTEPS        8
#define GEAR_YZ           20.0
#define USTEPS_PER_REV    (STEPS_PER_REV * MICROSTEPS)
#define UDEG_X            (USTEPS_PER_REV * 1.0  / 360.0)  // 4.44
#define UDEG_YZ           (USTEPS_PER_REV * GEAR_YZ / 360.0)  // 88.89
#define MAX_SPEED         1000.0
#define NORMAL_ACCEL      500.0
#define HOMING_FAST       500.0
#define HOMING_SLOW       100.0
#define HOMING_ACCEL      300.0
#define BACKOFF_DEG       5.0
#define DEBOUNCE_MS       20
#define FAN_PIN 9 // 12V Cooling Fan on D9

// ── KINEMATIC LIMITS ─────────────────────────────────────────────
#define LIM_X_MIN  -180.0
#define LIM_X_MAX   180.0
#define LIM_Y_MIN   -30.0
#define LIM_Y_MAX    90.0
#define LIM_Z_MIN   -90.0
#define LIM_Z_MAX    90.0

// ── ATC SERVOS ───────────────────────────────────────────────────
#define ATC_OPEN    0
#define ATC_CLOSE   65
#define ATC_DELAY   4

// ── GLOBALS ──────────────────────────────────────────────────────
AccelStepper sx(AccelStepper::DRIVER, X_STEP_PIN, X_DIR_PIN);
AccelStepper sy(AccelStepper::DRIVER, Y_STEP_PIN, Y_DIR_PIN);
AccelStepper sz(AccelStepper::DRIVER, Z_STEP_PIN, Z_DIR_PIN);
Servo srv1, srv2;  // Diagonal pair: top-left + bottom-right

float cx = 0, cy = 0, cz = 0;
bool atc_locked = false;
String sbuf = "";

// FIX BUG 2: dedicated flag only for MOVE commands
bool move_command_pending = false;

// ═══════════════════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  delay(500);

  // Start the cooling fan immediately
  pinMode(FAN_PIN, OUTPUT);
  digitalWrite(FAN_PIN, HIGH);

  pinMode(X_ENABLE_PIN, OUTPUT); digitalWrite(X_ENABLE_PIN, LOW);
  pinMode(Y_ENABLE_PIN, OUTPUT); digitalWrite(Y_ENABLE_PIN, LOW);
  pinMode(Z_ENABLE_PIN, OUTPUT); digitalWrite(Z_ENABLE_PIN, LOW);

  // MS-114 NO wiring: resting=HIGH, pressed=LOW
  pinMode(X_MIN_PIN, INPUT_PULLUP);
  pinMode(Y_MIN_PIN, INPUT_PULLUP);
  pinMode(Z_MIN_PIN, INPUT_PULLUP);

  sx.setMaxSpeed(MAX_SPEED); sx.setAcceleration(NORMAL_ACCEL); sx.setCurrentPosition(0);
  sy.setMaxSpeed(MAX_SPEED); sy.setAcceleration(NORMAL_ACCEL); sy.setCurrentPosition(0);
  sz.setMaxSpeed(MAX_SPEED); sz.setAcceleration(NORMAL_ACCEL); sz.setCurrentPosition(0);

  srv1.attach(SRV1_PIN, 500, 2500);   // Top Left
  srv2.attach(SRV2_PIN, 500, 2500);   // Bottom Right (diagonal)
  atc_do_unlock();

  Serial.println("=== APEX_PREDATOR v2.1 ===");
  Serial.println("Motor: RMCS-1010 5.6kgcm @ DRV8825 1/8 microstep");
  Serial.println("Shield: RAMPS 1.6");
  Serial.println("Switches: MS-114 NO wiring");
  Serial.println("ATC: 2x MG90S diagonal pair ready (pins 4 + 11)");

  // FIX BUG 3: boot signal for apex_demo_path.py connect sequence
  Serial.println("APEX_READY");
}

// ═══════════════════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════════════════
void loop() {
  read_serial();
  sx.run();
  sy.run();
  sz.run();

  // FIX BUG 2: Only MOVE handler sets this flag — homing never does
  if (move_command_pending && !sx.isRunning() && !sy.isRunning() && !sz.isRunning()) {
    move_command_pending = false;
    Serial.println("OK");
    Serial.flush();
  }
}

// ═══════════════════════════════════════════════════════════════
// SERIAL
// ═══════════════════════════════════════════════════════════════
void read_serial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (sbuf.length()) { process_cmd(sbuf); sbuf = ""; }
    } else { sbuf += c; }
  }
}

void process_cmd(String cmd) {
  cmd.trim();
  if      (cmd.startsWith("<MOVE"))      handle_move(cmd);
  else if (cmd == "HOME")               handle_home();       // FIX BUG 1+5
  else if (cmd == "LOCK")               { atc_do_lock();   Serial.println("OK"); }
  else if (cmd == "UNLOCK")             { atc_do_unlock(); Serial.println("OK"); }
  else if (cmd == "TOOL_ID")            { Serial.print("TOOL:"); Serial.println(read_tool_id()); Serial.println("OK"); }
  // FIX BUG 4: accept both EN and MOTORS_EN, DIS and MOTORS_DIS
  else if (cmd == "EN"  || cmd == "MOTORS_EN")  { digitalWrite(X_ENABLE_PIN,LOW);  digitalWrite(Y_ENABLE_PIN,LOW);  digitalWrite(Z_ENABLE_PIN,LOW);  Serial.println("OK"); }
  else if (cmd == "DIS" || cmd == "MOTORS_DIS") { digitalWrite(X_ENABLE_PIN,HIGH); digitalWrite(Y_ENABLE_PIN,HIGH); digitalWrite(Z_ENABLE_PIN,HIGH); Serial.println("OK"); }
  else if (cmd == "GRIPPER_OPEN" || cmd == "GRIPPER_CLOSE") Serial.println("OK");
  else if (cmd == "HEATER_ON"   || cmd == "HEATER_OFF")     Serial.println("OK");
  else { Serial.print("ERR: Unknown: "); Serial.println(cmd); }
}

// ═══════════════════════════════════════════════════════════════
// MOVE HANDLER
// ═══════════════════════════════════════════════════════════════
void handle_move(String cmd) {
  float tx = cx, ty = cy, tz = cz;
  int xi = cmd.indexOf('X'), yi = cmd.indexOf('Y'), zi = cmd.indexOf('Z');
  if (xi != -1) tx = cmd.substring(xi+1, cmd.indexOf(' ', xi)).toFloat();
  if (yi != -1) ty = cmd.substring(yi+1, cmd.indexOf(' ', yi)).toFloat();
  if (zi != -1) tz = cmd.substring(zi+1, cmd.indexOf('>', zi)).toFloat();

  if (tx < LIM_X_MIN || tx > LIM_X_MAX) { Serial.println("ERR: X out of bounds"); return; }
  if (ty < LIM_Y_MIN || ty > LIM_Y_MAX) { Serial.println("ERR: Y out of bounds"); return; }
  if (tz < LIM_Z_MIN || tz > LIM_Z_MAX) { Serial.println("ERR: Z out of bounds"); return; }

  sx.moveTo((long)(tx * UDEG_X));
  sy.moveTo((long)(ty * UDEG_YZ));
  sz.moveTo((long)(tz * UDEG_YZ));
  cx = tx; cy = ty; cz = tz;

  move_command_pending = true; // loop() sends OK when motors stop
}

// ═══════════════════════════════════════════════════════════════
// HOMING — FULLY BLOCKING, SENDS OWN OK
// ═══════════════════════════════════════════════════════════════

// FIX BUG 1 + BUG 5:
// Homing is now purely sequential and blocking.
// No state machine, no flags to clear, no loop() involvement.
// Each axis completes fully before next starts.
// OK is sent here, not by loop().

void handle_home() {
  Serial.println("Homing all axes...");
  home_axis(&sx, X_MIN_PIN, UDEG_X,  "X");
  home_axis(&sy, Y_MIN_PIN, UDEG_YZ, "Y");
  home_axis(&sz, Z_MIN_PIN, UDEG_YZ, "Z");
  cx = 0; cy = 0; cz = 0;
  Serial.println("✓ All axes homed");
  Serial.println("OK");  // FIX BUG 1: home sends its own OK
  Serial.flush();
}

void home_axis(AccelStepper* s, int pin, float udeg, const char* name) {
  Serial.print("Homing "); Serial.println(name);
  s->setMaxSpeed(HOMING_FAST); s->setAcceleration(HOMING_ACCEL);
  s->moveTo(-1000000L);

  // Phase 1: Fast hit
  unsigned long t = 0; bool pressed = false;
  while (true) {
    s->run();
    if (digitalRead(pin) == LOW) {
      if (!pressed) { t = millis(); pressed = true; }
      if (millis() - t > DEBOUNCE_MS) { s->stop(); while (s->isRunning()) s->run(); break; }
    } else pressed = false;
  }
  Serial.print("✓ "); Serial.print(name); Serial.println(" hit");
  delay(100);

  // Phase 2: Back off
  s->moveTo(s->currentPosition() + (long)(BACKOFF_DEG * udeg));
  while (s->isRunning()) s->run();
  delay(100);

  // Phase 3: Slow approach
  s->setMaxSpeed(HOMING_SLOW); s->moveTo(-1000000L);
  t = 0; pressed = false;
  while (true) {
    s->run();
    if (digitalRead(pin) == LOW) {
      if (!pressed) { t = millis(); pressed = true; }
      if (millis() - t > DEBOUNCE_MS) { s->stop(); while (s->isRunning()) s->run(); break; }
    } else pressed = false;
  }

  s->setCurrentPosition(0);
  s->setMaxSpeed(MAX_SPEED); s->setAcceleration(NORMAL_ACCEL);
  Serial.print("✓ "); Serial.print(name); Serial.println(" zeroed");
}

// ═══════════════════════════════════════════════════════════════
// ATC — 4x MG90S SERVO LATCH
// ═══════════════════════════════════════════════════════════════
void atc_do_lock() {
  for (int p = ATC_OPEN; p <= ATC_CLOSE; p++) {
    srv1.write(p);   // Top Left
    srv2.write(p);   // Bottom Right (diagonal)
    delay(ATC_DELAY);
  }
  atc_locked = true;
}

void atc_do_unlock() {
  int start = atc_locked ? ATC_CLOSE : ATC_OPEN;
  for (int p = start; p >= ATC_OPEN; p--) {
    srv1.write(p);   // Top Left
    srv2.write(p);   // Bottom Right (diagonal)
    delay(ATC_DELAY);
  }
  atc_locked = false;
}

// ═══════════════════════════════════════════════════════════════
// TOOL ID — RESISTOR LADDER
// ═══════════════════════════════════════════════════════════════
int read_tool_id() {
  delay(200);
  long sum = 0;
  for (int i = 0; i < 20; i++) { sum += analogRead(TOOL_ID_PIN); delay(10); }
  int adc = sum / 20;
  Serial.print("ADC: "); Serial.println(adc);
  if (adc >= 70  && adc <= 120) return 1;  // Gripper  (1kΩ)
  if (adc >= 150 && adc <= 220) return 2;  // Suction  (2.2kΩ)
  if (adc >= 290 && adc <= 370) return 3;  // Solder   (4.7kΩ)
  return 0;
}
