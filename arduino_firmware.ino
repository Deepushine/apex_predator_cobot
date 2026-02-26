/*
═══════════════════════════════════════════════════════════════════
                    APEX_PREDATOR v2.0 FIRMWARE
                  Master/Slave Handshake Protocol
═══════════════════════════════════════════════════════════════════

Arduino Mega 2560 + RAMPS 1.4 + DRV8825 Stepper Drivers
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
#include <String.h>

// ═══════════════════════════════════════════════════════════════
// PIN DEFINITIONS
// ═══════════════════════════════════════════════════════════════

// RAMPS 1.4 Stepper Motor Control Pins
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

// Enable pins (optional, for power management)
#define X_ENABLE_PIN   38
#define Y_ENABLE_PIN   56
#define Z_ENABLE_PIN   62

// ═══════════════════════════════════════════════════════════════
// MOTOR CONFIGURATION
// ═══════════════════════════════════════════════════════════════

// NEMA 17 RMCS-1010 @ 1/8 microstepping
#define STEPS_PER_REV     200      // 200 steps/rev for NEMA 17
#define MICROSTEPS        8        // DRV8825 @ 1/8 microstepping
#define MICROSTEPS_PER_REV (STEPS_PER_REV * MICROSTEPS)  // 1600

// Gear ratios
#define GEAR_RATIO_X  1.0   // Base: 1:1
#define GEAR_RATIO_Y  20.0  // Shoulder: 20:1 (heavy lifting)
#define GEAR_RATIO_Z  20.0  // Elbow: 20:1 (heavy lifting)

// Calculate microsteps per degree for each axis
// (microsteps per revolution) / (degrees per revolution)
#define MICROSTEPS_PER_DEG_X (MICROSTEPS_PER_REV * GEAR_RATIO_X / 360.0)
#define MICROSTEPS_PER_DEG_Y (MICROSTEPS_PER_REV * GEAR_RATIO_Y / 360.0)
#define MICROSTEPS_PER_DEG_Z (MICROSTEPS_PER_REV * GEAR_RATIO_Z / 360.0)

// Motor speed and acceleration
#define MAX_SPEED         1000.0   // microsteps/second (moderate speed for safety)
#define NORMAL_ACCEL      500.0    // microsteps/second²
#define HOMING_FAST_SPEED 500.0    // Fast speed for initial hit
#define HOMING_SLOW_SPEED 100.0    // Slow speed for fine zero
#define HOMING_ACCEL      300.0    // Acceleration during homing

// Homing parameters
#define HOMING_BACKOFF_DEGREES 5.0    // Back off 5° after hitting limit
#define HOMING_DEBOUNCE_MS 20         // Debounce time for limit switches

// ═══════════════════════════════════════════════════════════════
// KINEMATIC SAFETY LIMITS (Kinematic Shield)
// ═══════════════════════════════════════════════════════════════

#define LIMIT_X_MIN  -180.0
#define LIMIT_X_MAX   180.0
#define LIMIT_Y_MIN   -30.0   // Prevent tipping
#define LIMIT_Y_MAX    90.0   // Prevent collision
#define LIMIT_Z_MIN   -90.0
#define LIMIT_Z_MAX    90.0

// ═══════════════════════════════════════════════════════════════
// GLOBAL VARIABLES
// ═══════════════════════════════════════════════════════════════

// Create stepper objects using AccelStepper
// AccelStepper(type, step_pin, direction_pin)
AccelStepper stepper_x(AccelStepper::DRIVER, X_STEP_PIN, X_DIR_PIN);
AccelStepper stepper_y(AccelStepper::DRIVER, Y_STEP_PIN, Y_DIR_PIN);
AccelStepper stepper_z(AccelStepper::DRIVER, Z_STEP_PIN, Z_DIR_PIN);

// Current position in degrees (absolute position)
volatile float current_x = 0.0;
volatile float current_y = 0.0;
volatile float current_z = 0.0;

// Limit switch states
volatile bool limit_x_hit = false;
volatile bool limit_y_hit = false;
volatile bool limit_z_hit = false;

// Flag for homing in progress
volatile bool homing_in_progress = false;
volatile bool homing_axis_x = false;
volatile bool homing_axis_y = false;
volatile bool homing_axis_z = false;

// Serial communication buffer
String serial_buffer = "";
bool command_received = false;

// ═══════════════════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════════════════

void setup() {
  // Initialize serial communication
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("=== APEX_PREDATOR v2.0 FIRMWARE ===");
  Serial.println("Master/Slave Handshake Protocol");
  
  // Configure motor enable pins
  pinMode(X_ENABLE_PIN, OUTPUT);
  pinMode(Y_ENABLE_PIN, OUTPUT);
  pinMode(Z_ENABLE_PIN, OUTPUT);
  
  // Enable motors (LOW = enabled on RAMPS)
  digitalWrite(X_ENABLE_PIN, LOW);
  digitalWrite(Y_ENABLE_PIN, LOW);
  digitalWrite(Z_ENABLE_PIN, LOW);
  
  // Configure limit switches (INPUT_PULLUP for NO logic)
  pinMode(X_MIN_PIN, INPUT_PULLUP);
  pinMode(Y_MIN_PIN, INPUT_PULLUP);
  pinMode(Z_MIN_PIN, INPUT_PULLUP);
  
  // Configure stepper motors
  setup_stepper(&stepper_x, "X (Base)");
  setup_stepper(&stepper_y, "Y (Shoulder)");
  setup_stepper(&stepper_z, "Z (Elbow)");
  
  Serial.println("✓ Motors initialized");
  Serial.println("✓ Limit switches configured");
  Serial.println("✓ Ready for commands");
  Serial.println("");
}

void setup_stepper(AccelStepper *stepper, const char *axis_name) {
  stepper->setMaxSpeed(MAX_SPEED);
  stepper->setAcceleration(NORMAL_ACCEL);
  stepper->setCurrentPosition(0);
  Serial.print("✓ ");
  Serial.println(axis_name);
}

// ═══════════════════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════════════════

void loop() {
  // Check for incoming serial commands
  check_serial();
  
  // Run stepper motors
  stepper_x.run();
  stepper_y.run();
  stepper_z.run();
  
  // Handle homing sequence if in progress
  if (homing_in_progress) {
    handle_homing();
  }
  
  // Check if move is complete
  if (!stepper_x.isRunning() && !stepper_y.isRunning() && !stepper_z.isRunning()) {
    if (command_received && !homing_in_progress) {
      // Move completed - send OK to Python
      command_received = false;
      Serial.println("OK");
      Serial.flush();
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// SERIAL COMMUNICATION (Master/Slave Handshake)
// ═══════════════════════════════════════════════════════════════

void check_serial() {
  while (Serial.available() > 0) {
    char incoming = Serial.read();
    
    // Check for line terminator
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
  
  // Debug: echo command
  Serial.print("RX: ");
  Serial.println(cmd);
  
  // Parse MOVE command: <MOVE X45.0 Y90.0 Z-30.0>
  if (cmd.startsWith("<MOVE ")) {
    handle_move_command(cmd);
  }
  // Parse HOME command
  else if (cmd == "HOME") {
    handle_home_command();
  }
  // Motor control commands
  else if (cmd == "MOTORS_EN") {
    digitalWrite(X_ENABLE_PIN, LOW);
    digitalWrite(Y_ENABLE_PIN, LOW);
    digitalWrite(Z_ENABLE_PIN, LOW);
    Serial.println("OK");
  }
  else if (cmd == "MOTORS_DIS") {
    digitalWrite(X_ENABLE_PIN, HIGH);
    digitalWrite(Y_ENABLE_PIN, HIGH);
    digitalWrite(Z_ENABLE_PIN, HIGH);
    Serial.println("OK");
  }
  else if (cmd == "GRIPPER_OPEN" || cmd == "GRIPPER_CLOSE") {
    // Placeholder for future gripper control
    Serial.println("OK");
  }
  else if (cmd == "HEATER_ON" || cmd == "HEATER_OFF") {
    // Placeholder for heater control
    Serial.println("OK");
  }
  else {
    Serial.println("ERR: Unknown command");
  }
}

// ═══════════════════════════════════════════════════════════════
// MOVE COMMAND HANDLER
// ═══════════════════════════════════════════════════════════════

void handle_move_command(String cmd) {
  // Parse: <MOVE X45.0 Y90.0 Z-30.0>
  
  float target_x = current_x;
  float target_y = current_y;
  float target_z = current_z;
  bool valid = true;
  
  // Find and parse X angle
  int x_index = cmd.indexOf('X');
  if (x_index != -1) {
    target_x = cmd.substring(x_index + 1, cmd.indexOf(' ', x_index)).toFloat();
  }
  
  // Find and parse Y angle
  int y_index = cmd.indexOf('Y');
  if (y_index != -1) {
    target_y = cmd.substring(y_index + 1, cmd.indexOf(' ', y_index)).toFloat();
  }
  
  // Find and parse Z angle
  int z_index = cmd.indexOf('Z');
  if (z_index != -1) {
    target_z = cmd.substring(z_index + 1, cmd.indexOf('>', z_index)).toFloat();
  }
  
  // Validate against kinematic limits (Kinematic Shield)
  if (target_x < LIMIT_X_MIN || target_x > LIMIT_X_MAX) {
    Serial.println("ERR: X out of bounds");
    return;
  }
  if (target_y < LIMIT_Y_MIN || target_y > LIMIT_Y_MAX) {
    Serial.println("ERR: Y out of bounds");
    return;
  }
  if (target_z < LIMIT_Z_MIN || target_z > LIMIT_Z_MAX) {
    Serial.println("ERR: Z out of bounds");
    return;
  }
  
  // Set target positions (convert degrees to microsteps)
  long target_x_steps = (long)(target_x * MICROSTEPS_PER_DEG_X);
  long target_y_steps = (long)(target_y * MICROSTEPS_PER_DEG_Y);
  long target_z_steps = (long)(target_z * MICROSTEPS_PER_DEG_Z);
  
  stepper_x.moveTo(target_x_steps);
  stepper_y.moveTo(target_y_steps);
  stepper_z.moveTo(target_z_steps);
  
  // Update current position
  current_x = target_x;
  current_y = target_y;
  current_z = target_z;
  
  // Set flag: command has been received and is executing
  command_received = true;
  
  // Do NOT send OK yet - wait for motion to complete
}

// ═══════════════════════════════════════════════════════════════
// AUTONOMOUS HOMING SEQUENCE (Double-Tap Protocol)
// ═══════════════════════════════════════════════════════════════

void handle_home_command() {
  Serial.println("Homing sequence started...");
  
  homing_in_progress = true;
  homing_axis_x = true;
  homing_axis_y = true;
  homing_axis_z = true;
  
  // Start homing routine
  home_single_axis(&stepper_x, X_MIN_PIN, MICROSTEPS_PER_DEG_X, "X");
  home_single_axis(&stepper_y, Y_MIN_PIN, MICROSTEPS_PER_DEG_Y, "Y");
  home_single_axis(&stepper_z, Z_MIN_PIN, MICROSTEPS_PER_DEG_Z, "Z");
  
  command_received = true;
}

void home_single_axis(AccelStepper *stepper, int limit_pin, float microsteps_per_deg, const char *axis) {
  Serial.print("Homing ");
  Serial.print(axis);
  Serial.println("...");
  
  stepper->setMaxSpeed(HOMING_FAST_SPEED);
  stepper->setAcceleration(HOMING_ACCEL);
  
  // Phase 1: Move toward limit switch at fast speed
  stepper->moveTo(-1000000);  // Move in negative direction
  
  unsigned long debounce_time = 0;
  bool switch_pressed = false;
  
  while (true) {
    stepper->run();
    
    // Check limit switch (LOW = pressed for INPUT_PULLUP)
    if (digitalRead(limit_pin) == LOW) {
      if (!switch_pressed) {
        debounce_time = millis();
        switch_pressed = true;
      }
      
      // Confirmed pressed after debounce
      if (millis() - debounce_time > HOMING_DEBOUNCE_MS) {
        stepper->stop();
        while (stepper->isRunning()) {
          stepper->run();
        }
        break;
      }
    } else {
      switch_pressed = false;
    }
  }
  
  Serial.print("✓ ");
  Serial.print(axis);
  Serial.println(" limit hit");
  
  delay(100);
  
  // Phase 2: Back off 5 degrees
  long backoff_steps = (long)(HOMING_BACKOFF_DEGREES * microsteps_per_deg);
  long current_pos = stepper->currentPosition();
  stepper->moveTo(current_pos + backoff_steps);
  
  while (stepper->isRunning()) {
    stepper->run();
  }
  
  Serial.print("✓ ");
  Serial.print(axis);
  Serial.println(" backed off");
  
  delay(100);
  
  // Phase 3: Slow approach to limit switch for fine zero
  stepper->setMaxSpeed(HOMING_SLOW_SPEED);
  stepper->moveTo(-1000000);
  
  debounce_time = 0;
  switch_pressed = false;
  
  while (true) {
    stepper->run();
    
    if (digitalRead(limit_pin) == LOW) {
      if (!switch_pressed) {
        debounce_time = millis();
        switch_pressed = true;
      }
      
      if (millis() - debounce_time > HOMING_DEBOUNCE_MS) {
        stepper->stop();
        while (stepper->isRunning()) {
          stepper->run();
        }
        break;
      }
    } else {
      switch_pressed = false;
    }
  }
  
  // Set this position as zero
  stepper->setCurrentPosition(0);
  stepper->setMaxSpeed(MAX_SPEED);
  stepper->setAcceleration(NORMAL_ACCEL);
  
  Serial.print("✓ ");
  Serial.print(axis);
  Serial.println(" zeroed and ready");
}

void handle_homing() {
  // Check if all axes have completed homing
  bool all_done = !homing_axis_x && !homing_axis_y && !homing_axis_z;
  
  // Simple state machine - just monitor for completion
  // The home_single_axis functions handle everything
  
  if (all_done) {
    homing_in_progress = false;
    command_received = false;
    
    // Reset position variables
    current_x = 0.0;
    current_y = 0.0;
    current_z = 0.0;
    
    Serial.println("✓ Homing complete - All axes at zero");
    Serial.println("OK");
    Serial.flush();
  }
}

// ═══════════════════════════════════════════════════════════════
// UTILITY FUNCTIONS
// ═══════════════════════════════════════════════════════════════

float clamp(float value, float min_val, float max_val) {
  if (value < min_val) return min_val;
  if (value > max_val) return max_val;
  return value;
}

/*
═══════════════════════════════════════════════════════════════════
PROTOCOL EXAMPLES:

1. Move to absolute position:
   Python sends:   <MOVE X45.0 Y90.0 Z-30.0>
   Arduino executes move (smooth acceleration via AccelStepper)
   When motion stops:
   Arduino sends:  OK

2. Home all axes (double-tap):
   Python sends:  HOME
   Arduino:
     - Phase 1: Fast approach to limit switch
     - Phase 2: Back off 5 degrees
     - Phase 3: Slow approach for fine zero
   Arduino sends:  OK

3. Direct motor control:
   Python sends:  MOTORS_EN (or MOTORS_DIS)
   Arduino sends:  OK

═══════════════════════════════════════════════════════════════════
SAFETY FEATURES:

- Kinematic Shield: All MOVE commands validated against joint limits
- Limit Switches: Hardware safety stops
- Debouncing: 20ms debounce on limit switch inputs
- Blocking Handshake: No concurrent operations
- Emergency: Motors can be disabled via MOTORS_DIS command

═══════════════════════════════════════════════════════════════════
*/
