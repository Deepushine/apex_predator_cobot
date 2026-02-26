/*
═══════════════════════════════════════════════════════════════════
                    APEX_PREDATOR v2.0 FIRMWARE
                  Master/Slave Handshake Protocol
═══════════════════════════════════════════════════════════════════

Arduino Mega 2560 + RAMPS 1.6 + DRV8825 Stepper Drivers
3x NEMA 17 RMCS-1010 motors (5.6 kg-cm torque)

HARDWARE CONFIGURATION:
- Base (X):     Motor 1 via DRV8825 (Step/Dir pins)
- Shoulder (Y): Motor 2 via DRV8825 (Step/Dir pins)
- Elbow (Z):    Motor 3 via DRV8825 (Step/Dir pins)

LIMIT SWITCHES (Normally Open, Two-Wire):
- X_MIN (Base):     Pin 3  (INPUT_PULLUP)
- Y_MIN (Shoulder): Pin 14 (INPUT_PULLUP)
- Z_MIN (Elbow):    Pin 18 (INPUT_PULLUP)

PROTOCOL:
- Python sends: <MOVE X45.0 Y90.0 Z-30.0>
- Arduino executes move and replies: OK
- Python BLOCKS until OK received
- Double-tap homing on HOME command

═══════════════════════════════════════════════════════════════════
*/

#include <AccelStepper.h>

// ═══════════════════════════════════════════════════════════════
// PIN DEFINITIONS
// ═══════════════════════════════════════════════════════════════

// RAMPS 1.6 Stepper Motor Control Pins
#define X_STEP_PIN     54
#define X_DIR_PIN      55
#define Y_STEP_PIN     60
#define Y_DIR_PIN      61
#define Z_STEP_PIN     46
#define Z_DIR_PIN      48

// Limit Switches
#define X_MIN_PIN      3   // Base rotation limit
#define Y_MIN_PIN      14  // Shoulder lift limit
#define Z_MIN_PIN      18  // Elbow extension limit

// Enable pins
#define X_ENABLE_PIN   38
#define Y_ENABLE_PIN   56
#define Z_ENABLE_PIN   62

// ═══════════════════════════════════════════════════════════════
// MOTOR CONFIGURATION
// ═══════════════════════════════════════════════════════════════

// NEMA 17 RMCS-1010 @ 1/8 microstepping
#define STEPS_PER_REV          200
#define MICROSTEPS             8
#define MICROSTEPS_PER_REV     (STEPS_PER_REV * MICROSTEPS)   // 1600

// Gear ratios
#define GEAR_RATIO_X  1.0
#define GEAR_RATIO_Y  20.0
#define GEAR_RATIO_Z  20.0

// Steps per degree for each axis
#define MICROSTEPS_PER_DEG_X  (MICROSTEPS_PER_REV * GEAR_RATIO_X / 360.0)   //  4.44
#define MICROSTEPS_PER_DEG_Y  (MICROSTEPS_PER_REV * GEAR_RATIO_Y / 360.0)   // 88.89
#define MICROSTEPS_PER_DEG_Z  (MICROSTEPS_PER_REV * GEAR_RATIO_Z / 360.0)   // 88.89

// Speed settings
#define MAX_SPEED         1000.0
#define NORMAL_ACCEL      500.0
#define HOMING_FAST_SPEED 500.0
#define HOMING_SLOW_SPEED 100.0
#define HOMING_ACCEL      300.0

// Homing parameters
#define HOMING_BACKOFF_DEGREES 5.0
#define HOMING_DEBOUNCE_MS     20

// ═══════════════════════════════════════════════════════════════
// KINEMATIC SAFETY LIMITS
// ═══════════════════════════════════════════════════════════════

#define LIMIT_X_MIN  -180.0
#define LIMIT_X_MAX   180.0
#define LIMIT_Y_MIN   -30.0
#define LIMIT_Y_MAX    90.0
#define LIMIT_Z_MIN   -90.0
#define LIMIT_Z_MAX    90.0

// ═══════════════════════════════════════════════════════════════
// GLOBAL VARIABLES
// ═══════════════════════════════════════════════════════════════

AccelStepper stepper_x(AccelStepper::DRIVER, X_STEP_PIN, X_DIR_PIN);
AccelStepper stepper_y(AccelStepper::DRIVER, Y_STEP_PIN, Y_DIR_PIN);
AccelStepper stepper_z(AccelStepper::DRIVER, Z_STEP_PIN, Z_DIR_PIN);

float current_x = 0.0;
float current_y = 0.0;
float current_z = 0.0;

// FIX: Separate flag to track whether a move command is waiting for OK
// (was shared with homing, causing premature OKs)
bool move_command_pending = false;

String serial_buffer = "";

// ═══════════════════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════════════════

void setup() {
  Serial.begin(115200);
  delay(1000);

  // Configure enable pins — start DISABLED (safe)
  pinMode(X_ENABLE_PIN, OUTPUT);
  pinMode(Y_ENABLE_PIN, OUTPUT);
  pinMode(Z_ENABLE_PIN, OUTPUT);
  digitalWrite(X_ENABLE_PIN, HIGH);
  digitalWrite(Y_ENABLE_PIN, HIGH);
  digitalWrite(Z_ENABLE_PIN, HIGH);

  // Configure limit switches (NO: resting = HIGH, hit = LOW)
  pinMode(X_MIN_PIN, INPUT_PULLUP);
  pinMode(Y_MIN_PIN, INPUT_PULLUP);
  pinMode(Z_MIN_PIN, INPUT_PULLUP);

  // Configure steppers
  setup_stepper(&stepper_x, MICROSTEPS_PER_DEG_X, "X (Base)");
  setup_stepper(&stepper_y, MICROSTEPS_PER_DEG_Y, "Y (Shoulder)");
  setup_stepper(&stepper_z, MICROSTEPS_PER_DEG_Z, "Z (Elbow)");

  // FIX: Send APEX_READY signal that apex_demo_path.py waits for
  Serial.println("APEX_READY");
}

void setup_stepper(AccelStepper *stepper, float steps_per_deg, const char *axis_name) {
  stepper->setMaxSpeed(MAX_SPEED);
  stepper->setAcceleration(NORMAL_ACCEL);
  stepper->setCurrentPosition(0);
}

// ═══════════════════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════════════════

void loop() {
  // Always service serial
  check_serial();

  // Run motors
  stepper_x.run();
  stepper_y.run();
  stepper_z.run();

  // FIX: Only send OK once all three axes have stopped,
  // and only when a move command is actually pending.
  // Previously, command_received was set true by HOME too,
  // causing the loop to spam OK as soon as motors paused.
  if (move_command_pending) {
    if (!stepper_x.isRunning() && !stepper_y.isRunning() && !stepper_z.isRunning()) {
      move_command_pending = false;
      Serial.println("OK");
      Serial.flush();
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// SERIAL COMMUNICATION
// ═══════════════════════════════════════════════════════════════

void check_serial() {
  while (Serial.available() > 0) {
    char incoming = Serial.read();
    if (incoming == '\n' || incoming == '\r') {
      if (serial_buffer.length() > 0) {
        process_command(serial_buffer);
        serial_buffer = "";
      }
    } else {
      serial_buffer += incoming;
    }
  }
}

void process_command(String cmd) {
  cmd.trim();

  if (cmd.startsWith("<MOVE ")) {
    handle_move_command(cmd);
  }
  else if (cmd == "HOME") {
    handle_home_command();
  }
  // FIX: Added EN / DIS commands used by apex_demo_path.py
  else if (cmd == "EN" || cmd == "MOTORS_EN") {
    digitalWrite(X_ENABLE_PIN, LOW);
    digitalWrite(Y_ENABLE_PIN, LOW);
    digitalWrite(Z_ENABLE_PIN, LOW);
    Serial.println("OK");
  }
  else if (cmd == "DIS" || cmd == "MOTORS_DIS") {
    digitalWrite(X_ENABLE_PIN, HIGH);
    digitalWrite(Y_ENABLE_PIN, HIGH);
    digitalWrite(Z_ENABLE_PIN, HIGH);
    Serial.println("OK");
  }
  else if (cmd == "GRIPPER_OPEN" || cmd == "GRIPPER_CLOSE") {
    Serial.println("OK");
  }
  else if (cmd == "HEATER_ON" || cmd == "HEATER_OFF") {
    Serial.println("OK");
  }
  else {
    Serial.println("ERR: Unknown command");
  }
}

// ═══════════════════════════════════════════════════════════════
// MOVE COMMAND
// ═══════════════════════════════════════════════════════════════

void handle_move_command(String cmd) {
  // Parse: <MOVE X45.0 Y90.0 Z-30.0>
  float target_x = current_x;
  float target_y = current_y;
  float target_z = current_z;

  int x_index = cmd.indexOf('X');
  if (x_index != -1) {
    int space_after = cmd.indexOf(' ', x_index);
    target_x = (space_after != -1)
      ? cmd.substring(x_index + 1, space_after).toFloat()
      : cmd.substring(x_index + 1).toFloat();
  }

  int y_index = cmd.indexOf('Y');
  if (y_index != -1) {
    int space_after = cmd.indexOf(' ', y_index);
    target_y = (space_after != -1)
      ? cmd.substring(y_index + 1, space_after).toFloat()
      : cmd.substring(y_index + 1).toFloat();
  }

  int z_index = cmd.indexOf('Z');
  if (z_index != -1) {
    int end_pos = cmd.indexOf('>', z_index);
    target_z = (end_pos != -1)
      ? cmd.substring(z_index + 1, end_pos).toFloat()
      : cmd.substring(z_index + 1).toFloat();
  }

  // Kinematic limit check
  if (target_x < LIMIT_X_MIN || target_x > LIMIT_X_MAX) { Serial.println("ERR: X out of bounds"); return; }
  if (target_y < LIMIT_Y_MIN || target_y > LIMIT_Y_MAX) { Serial.println("ERR: Y out of bounds"); return; }
  if (target_z < LIMIT_Z_MIN || target_z > LIMIT_Z_MAX) { Serial.println("ERR: Z out of bounds"); return; }

  // Queue moves
  stepper_x.moveTo((long)(target_x * MICROSTEPS_PER_DEG_X));
  stepper_y.moveTo((long)(target_y * MICROSTEPS_PER_DEG_Y));
  stepper_z.moveTo((long)(target_z * MICROSTEPS_PER_DEG_Z));

  current_x = target_x;
  current_y = target_y;
  current_z = target_z;

  // FIX: Only set move_command_pending — NOT homing flag
  move_command_pending = true;
}

// ═══════════════════════════════════════════════════════════════
// HOMING — BLOCKING (runs synchronously, sends OK when done)
// ═══════════════════════════════════════════════════════════════

// FIX: Homing is now fully synchronous/blocking and sends its own OK.
// Previously homing set command_received=true then relied on the main
// loop's motion-complete check — but homing_axis_x/y/z were never
// cleared by home_single_axis(), so handle_homing() never saw
// all_done=true and the OK was never sent.
void handle_home_command() {
  Serial.println("Homing sequence started...");

  home_single_axis(&stepper_x, X_MIN_PIN, MICROSTEPS_PER_DEG_X, "X");
  home_single_axis(&stepper_y, Y_MIN_PIN, MICROSTEPS_PER_DEG_Y, "Y");
  home_single_axis(&stepper_z, Z_MIN_PIN, MICROSTEPS_PER_DEG_Z, "Z");

  current_x = 0.0;
  current_y = 0.0;
  current_z = 0.0;

  Serial.println("Homing complete - All axes at zero");
  Serial.println("OK");
  Serial.flush();
}

void home_single_axis(AccelStepper *stepper, int limit_pin, float microsteps_per_deg, const char *axis) {
  stepper->setMaxSpeed(HOMING_FAST_SPEED);
  stepper->setAcceleration(HOMING_ACCEL);

  // Phase 1: Fast approach
  stepper->moveTo(-1000000L);
  unsigned long debounce_time = 0;
  bool switch_pressed = false;

  while (true) {
    stepper->run();
    if (digitalRead(limit_pin) == LOW) {
      if (!switch_pressed) { debounce_time = millis(); switch_pressed = true; }
      if (millis() - debounce_time > HOMING_DEBOUNCE_MS) {
        stepper->stop();
        while (stepper->isRunning()) stepper->run();
        break;
      }
    } else {
      switch_pressed = false;
    }
  }

  delay(100);

  // Phase 2: Back off
  long backoff = (long)(HOMING_BACKOFF_DEGREES * microsteps_per_deg);
  stepper->moveTo(stepper->currentPosition() + backoff);
  while (stepper->isRunning()) stepper->run();

  delay(100);

  // Phase 3: Slow approach for fine zero
  stepper->setMaxSpeed(HOMING_SLOW_SPEED);
  stepper->moveTo(-1000000L);
  debounce_time = 0;
  switch_pressed = false;

  while (true) {
    stepper->run();
    if (digitalRead(limit_pin) == LOW) {
      if (!switch_pressed) { debounce_time = millis(); switch_pressed = true; }
      if (millis() - debounce_time > HOMING_DEBOUNCE_MS) {
        stepper->stop();
        while (stepper->isRunning()) stepper->run();
        break;
      }
    } else {
      switch_pressed = false;
    }
  }

  // Zero this axis
  stepper->setCurrentPosition(0);
  stepper->setMaxSpeed(MAX_SPEED);
  stepper->setAcceleration(NORMAL_ACCEL);
}
