/*
 ═══════════════════════════════════════════════════════════════════
                      ⚠️  DEPRECATED FIRMWARE  ⚠️
 ═══════════════════════════════════════════════════════════════════
 
 THIS FILE IS NO LONGER MAINTAINED AND SHOULD NOT BE USED.
 
 REASON FOR DEPRECATION:
 - Does NOT implement Master/Slave Handshake Protocol required by Python
 - Uses 1/16 microstepping (config.json specifies 1/8)
 - No APEX_READY boot signal (Python startup will hang)
 - 4-joint architecture incompatible with main 3-joint XYZ system
 - Different motor pin assignments vs arduino_firmware.ino
 - No handshake compliance = Python control layer WILL NOT WORK
 
 ACTION REQUIRED:
 ==> DO NOT UPLOAD THIS FIRMWARE
 ==> Use ONLY: arduino_firmware.ino (currently active/tested)
 
 If you must use this firmware:
 1. Update config.json microsteps from 8 to 16
 2. Rewrite apex_predator_engine.py handshake protocol
 3. Test manually on serial terminal only (GUI will NOT connect)
 
 For production: ALWAYS use arduino_firmware.ino
 ═══════════════════════════════════════════════════════════════════
 */

#include <AccelStepper.h>
#include <MultiStepper.h>

// ========== PIN DEFINITIONS ==========
#define X_STEP_PIN         54
#define X_DIR_PIN          55
#define X_ENABLE_PIN       38

#define Y_STEP_PIN         60
#define Y_DIR_PIN          61
#define Y_ENABLE_PIN       56

#define Z_STEP_PIN         46
#define Z_DIR_PIN          48
#define Z_ENABLE_PIN       62

#define E0_STEP_PIN        26
#define E0_DIR_PIN         28
#define E0_ENABLE_PIN      24

// Emergency stop button (optional - connect to a free digital pin)
#define ESTOP_PIN          3  // Change to your actual pin

// ========== MOTOR CONFIGURATION ==========
#define STEPS_PER_REV      200
#define MICROSTEPS         16
#define GEAR_RATIO         20
#define STEPS_PER_OUTPUT_REV  (STEPS_PER_REV * MICROSTEPS * GEAR_RATIO)

// Speed profiles
#define MAX_SPEED_FAST     1500
#define MAX_SPEED_NORMAL   1000
#define MAX_SPEED_SLOW     500
#define ACCELERATION_FAST  800
#define ACCELERATION_NORMAL 500
#define ACCELERATION_SLOW  200

// Current speed mode
int currentSpeedMode = 1; // 0=slow, 1=normal, 2=fast

// ========== POSITION LIMITS (in degrees) ==========
#define JOINT1_MIN        -180
#define JOINT1_MAX         180
#define JOINT2_MIN        -90
#define JOINT2_MAX         90
#define JOINT3_MIN        -90
#define JOINT3_MAX         90
#define JOINT4_MIN        -180
#define JOINT4_MAX         180

// ========== STEPPER OBJECTS ==========
AccelStepper joint1(AccelStepper::DRIVER, X_STEP_PIN, X_DIR_PIN);
AccelStepper joint2(AccelStepper::DRIVER, Y_STEP_PIN, Y_DIR_PIN);
AccelStepper joint3(AccelStepper::DRIVER, Z_STEP_PIN, Z_DIR_PIN);
AccelStepper joint4(AccelStepper::DRIVER, E0_STEP_PIN, E0_DIR_PIN);

MultiStepper steppers;

// ========== MEMORY POSITIONS ==========
#define MAX_SAVED_POSITIONS 5
struct Position {
  long j1, j2, j3, j4;
  bool saved;
};

Position savedPositions[MAX_SAVED_POSITIONS];

// ========== STATE VARIABLES ==========
bool motorsEnabled = true;
bool emergencyStop = false;

// ========== FUNCTION PROTOTYPES ==========
void enableMotors();
void disableMotors();
void emergencyStopHandler();
void setSpeedMode(int mode);
long degreesToSteps(float degrees);
float stepsToDegrees(long steps);
bool checkLimits(int joint, float degrees);
void moveJointSafe(int jointNum, float degrees);
void savePosition(int slot);
void loadPosition(int slot);
void listSavedPositions();
void executeGCode(String gcode);
void smoothMove(long j1, long j2, long j3, long j4);

// ========== SETUP ==========
void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  
  Serial.println("\n╔════════════════════════════════════════╗");
  Serial.println("║  RAMPS 1.6 Advanced Cobot Controller  ║");
  Serial.println("║        with Safety Features            ║");
  Serial.println("╚════════════════════════════════════════╝\n");
  
  // Configure pins
  pinMode(X_ENABLE_PIN, OUTPUT);
  pinMode(Y_ENABLE_PIN, OUTPUT);
  pinMode(Z_ENABLE_PIN, OUTPUT);
  pinMode(E0_ENABLE_PIN, OUTPUT);
  
  // Emergency stop button setup (optional)
  pinMode(ESTOP_PIN, INPUT_PULLUP);
  
  // Initialize steppers
  setSpeedMode(1); // Normal speed
  
  // Add to MultiStepper
  steppers.addStepper(joint1);
  steppers.addStepper(joint2);
  steppers.addStepper(joint3);
  steppers.addStepper(joint4);
  
  // Initialize saved positions
  for (int i = 0; i < MAX_SAVED_POSITIONS; i++) {
    savedPositions[i].saved = false;
  }
  
  enableMotors();
  printAdvancedMenu();
  
  Serial.println("✓ System Ready!\n");
}

// ========== MAIN LOOP ==========
void loop() {
  // Check emergency stop
  if (digitalRead(ESTOP_PIN) == LOW) {
    if (!emergencyStop) {
      emergencyStopHandler();
    }
  }
  
  // Run motors if not in emergency stop
  if (!emergencyStop) {
    joint1.run();
    joint2.run();
    joint3.run();
    joint4.run();
  }
  
  // Process serial commands
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    processCommand(command);
  }
}

// ========== MOTOR CONTROL ==========
void enableMotors() {
  digitalWrite(X_ENABLE_PIN, LOW);
  digitalWrite(Y_ENABLE_PIN, LOW);
  digitalWrite(Z_ENABLE_PIN, LOW);
  digitalWrite(E0_ENABLE_PIN, LOW);
  motorsEnabled = true;
  Serial.println("✓ Motors Enabled");
}

void disableMotors() {
  digitalWrite(X_ENABLE_PIN, HIGH);
  digitalWrite(Y_ENABLE_PIN, HIGH);
  digitalWrite(Z_ENABLE_PIN, HIGH);
  digitalWrite(E0_ENABLE_PIN, HIGH);
  motorsEnabled = false;
  Serial.println("✓ Motors Disabled");
}

void emergencyStopHandler() {
  emergencyStop = true;
  
  // Stop all motors immediately
  joint1.stop();
  joint2.stop();
  joint3.stop();
  joint4.stop();
  disableMotors();
  
  Serial.println("\n!!! EMERGENCY STOP ACTIVATED !!!");
  Serial.println("Send 'RESET' to clear emergency stop\n");
}

void setSpeedMode(int mode) {
  currentSpeedMode = mode;
  float maxSpeed, accel;
  
  switch(mode) {
    case 0: // Slow
      maxSpeed = MAX_SPEED_SLOW;
      accel = ACCELERATION_SLOW;
      Serial.println("Speed Mode: SLOW");
      break;
    case 1: // Normal
      maxSpeed = MAX_SPEED_NORMAL;
      accel = ACCELERATION_NORMAL;
      Serial.println("Speed Mode: NORMAL");
      break;
    case 2: // Fast
      maxSpeed = MAX_SPEED_FAST;
      accel = ACCELERATION_FAST;
      Serial.println("Speed Mode: FAST");
      break;
    default:
      maxSpeed = MAX_SPEED_NORMAL;
      accel = ACCELERATION_NORMAL;
      currentSpeedMode = 1;
  }
  
  joint1.setMaxSpeed(maxSpeed);
  joint1.setAcceleration(accel);
  joint2.setMaxSpeed(maxSpeed);
  joint2.setAcceleration(accel);
  joint3.setMaxSpeed(maxSpeed);
  joint3.setAcceleration(accel);
  joint4.setMaxSpeed(maxSpeed);
  joint4.setAcceleration(accel);
}

// ========== CONVERSION FUNCTIONS ==========
long degreesToSteps(float degrees) {
  return (long)((degrees / 360.0) * STEPS_PER_OUTPUT_REV);
}

float stepsToDegrees(long steps) {
  return (float)steps / (float)STEPS_PER_OUTPUT_REV * 360.0;
}

// ========== SAFETY FUNCTIONS ==========
bool checkLimits(int joint, float targetDegrees) {
  float currentDegrees;
  float min, max;
  
  switch(joint) {
    case 1:
      currentDegrees = stepsToDegrees(joint1.currentPosition());
      min = JOINT1_MIN;
      max = JOINT1_MAX;
      break;
    case 2:
      currentDegrees = stepsToDegrees(joint2.currentPosition());
      min = JOINT2_MIN;
      max = JOINT2_MAX;
      break;
    case 3:
      currentDegrees = stepsToDegrees(joint3.currentPosition());
      min = JOINT3_MIN;
      max = JOINT3_MAX;
      break;
    case 4:
      currentDegrees = stepsToDegrees(joint4.currentPosition());
      min = JOINT4_MIN;
      max = JOINT4_MAX;
      break;
    default:
      return false;
  }
  
  float newPosition = currentDegrees + targetDegrees;
  
  if (newPosition < min || newPosition > max) {
    Serial.print("✗ Joint ");
    Serial.print(joint);
    Serial.print(" limit exceeded! Range: ");
    Serial.print(min);
    Serial.print("° to ");
    Serial.print(max);
    Serial.println("°");
    return false;
  }
  
  return true;
}

void moveJointSafe(int jointNum, float degrees) {
  if (!checkLimits(jointNum, degrees)) {
    return;
  }
  
  long steps = degreesToSteps(degrees);
  
  switch(jointNum) {
    case 1:
      joint1.move(steps);
      break;
    case 2:
      joint2.move(steps);
      break;
    case 3:
      joint3.move(steps);
      break;
    case 4:
      joint4.move(steps);
      break;
  }
  
  Serial.print("→ Joint ");
  Serial.print(jointNum);
  Serial.print(" moving ");
  Serial.print(degrees);
  Serial.println("°");
}

// ========== POSITION MEMORY ==========
void savePosition(int slot) {
  if (slot < 0 || slot >= MAX_SAVED_POSITIONS) {
    Serial.println("✗ Invalid slot number!");
    return;
  }
  
  savedPositions[slot].j1 = joint1.currentPosition();
  savedPositions[slot].j2 = joint2.currentPosition();
  savedPositions[slot].j3 = joint3.currentPosition();
  savedPositions[slot].j4 = joint4.currentPosition();
  savedPositions[slot].saved = true;
  
  Serial.print("✓ Position saved to slot ");
  Serial.println(slot);
}

void loadPosition(int slot) {
  if (slot < 0 || slot >= MAX_SAVED_POSITIONS) {
    Serial.println("✗ Invalid slot number!");
    return;
  }
  
  if (!savedPositions[slot].saved) {
    Serial.println("✗ No position saved in this slot!");
    return;
  }
  
  long positions[4];
  positions[0] = savedPositions[slot].j1;
  positions[1] = savedPositions[slot].j2;
  positions[2] = savedPositions[slot].j3;
  positions[3] = savedPositions[slot].j4;
  
  steppers.moveTo(positions);
  steppers.runSpeedToPosition();
  
  Serial.print("✓ Moved to saved position ");
  Serial.println(slot);
}

void listSavedPositions() {
  Serial.println("\n=== Saved Positions ===");
  for (int i = 0; i < MAX_SAVED_POSITIONS; i++) {
    Serial.print("Slot ");
    Serial.print(i);
    Serial.print(": ");
    if (savedPositions[i].saved) {
      Serial.print("[");
      Serial.print(stepsToDegrees(savedPositions[i].j1), 1);
      Serial.print("°, ");
      Serial.print(stepsToDegrees(savedPositions[i].j2), 1);
      Serial.print("°, ");
      Serial.print(stepsToDegrees(savedPositions[i].j3), 1);
      Serial.print("°, ");
      Serial.print(stepsToDegrees(savedPositions[i].j4), 1);
      Serial.println("°]");
    } else {
      Serial.println("Empty");
    }
  }
  Serial.println("====================\n");
}

// ========== COMMAND PROCESSING ==========
void processCommand(String cmd) {
  cmd.toUpperCase();
  
  if (emergencyStop && cmd != "RESET") {
    Serial.println("✗ System in EMERGENCY STOP. Send RESET to continue.");
    return;
  }
  
  if (cmd == "E") {
    enableMotors();
  }
  else if (cmd == "D") {
    disableMotors();
  }
  else if (cmd == "H") {
    joint1.setCurrentPosition(0);
    joint2.setCurrentPosition(0);
    joint3.setCurrentPosition(0);
    joint4.setCurrentPosition(0);
    Serial.println("✓ All joints homed");
  }
  else if (cmd == "RESET") {
    emergencyStop = false;
    enableMotors();
    Serial.println("✓ Emergency stop cleared");
  }
  else if (cmd == "S") {
    printStatus();
  }
  else if (cmd == "M") {
    printAdvancedMenu();
  }
  else if (cmd == "SPEED0") {
    setSpeedMode(0);
  }
  else if (cmd == "SPEED1") {
    setSpeedMode(1);
  }
  else if (cmd == "SPEED2") {
    setSpeedMode(2);
  }
  else if (cmd.startsWith("SAVE")) {
    int slot = cmd.substring(4).toInt();
    savePosition(slot);
  }
  else if (cmd.startsWith("LOAD")) {
    int slot = cmd.substring(4).toInt();
    loadPosition(slot);
  }
  else if (cmd == "LIST") {
    listSavedPositions();
  }
  else if (cmd.startsWith("J")) {
    // Joint command: J1:45 (move joint 1 by 45 degrees)
    int colonPos = cmd.indexOf(':');
    if (colonPos > 0) {
      int jointNum = cmd.substring(1, colonPos).toInt();
      float angle = cmd.substring(colonPos + 1).toFloat();
      moveJointSafe(jointNum, angle);
    }
  }
  else {
    Serial.println("✗ Unknown command. Send 'M' for menu.");
  }
}

void printStatus() {
  Serial.println("\n=== SYSTEM STATUS ===");
  Serial.print("Motors: ");
  Serial.println(motorsEnabled ? "ENABLED" : "DISABLED");
  Serial.print("E-Stop: ");
  Serial.println(emergencyStop ? "ACTIVE" : "Clear");
  Serial.print("Speed Mode: ");
  if (currentSpeedMode == 0) Serial.println("SLOW");
  else if (currentSpeedMode == 1) Serial.println("NORMAL");
  else Serial.println("FAST");
  
  Serial.println("\nJoint Positions:");
  Serial.print("  J1: ");
  Serial.print(stepsToDegrees(joint1.currentPosition()), 2);
  Serial.println("°");
  Serial.print("  J2: ");
  Serial.print(stepsToDegrees(joint2.currentPosition()), 2);
  Serial.println("°");
  Serial.print("  J3: ");
  Serial.print(stepsToDegrees(joint3.currentPosition()), 2);
  Serial.println("°");
  Serial.print("  J4: ");
  Serial.print(stepsToDegrees(joint4.currentPosition()), 2);
  Serial.println("°");
  Serial.println("===================\n");
}

void printAdvancedMenu() {
  Serial.println("\n╔════════════════════════════════════╗");
  Serial.println("║       ADVANCED CONTROL MENU        ║");
  Serial.println("╠════════════════════════════════════╣");
  Serial.println("║ Basic Commands:                    ║");
  Serial.println("║   E - Enable motors                ║");
  Serial.println("║   D - Disable motors               ║");
  Serial.println("║   H - Home all joints              ║");
  Serial.println("║   S - Show status                  ║");
  Serial.println("║   M - Show this menu               ║");
  Serial.println("║                                    ║");
  Serial.println("║ Joint Control:                     ║");
  Serial.println("║   J1:45  - Move joint 1 by 45°     ║");
  Serial.println("║   J2:-30 - Move joint 2 by -30°    ║");
  Serial.println("║                                    ║");
  Serial.println("║ Speed Control:                     ║");
  Serial.println("║   SPEED0 - Slow mode               ║");
  Serial.println("║   SPEED1 - Normal mode             ║");
  Serial.println("║   SPEED2 - Fast mode               ║");
  Serial.println("║                                    ║");
  Serial.println("║ Position Memory:                   ║");
  Serial.println("║   SAVE0 - Save to slot 0           ║");
  Serial.println("║   LOAD0 - Load from slot 0         ║");
  Serial.println("║   LIST  - List saved positions     ║");
  Serial.println("║                                    ║");
  Serial.println("║ Emergency:                         ║");
  Serial.println("║   RESET - Clear emergency stop     ║");
  Serial.println("╚════════════════════════════════════╝\n");
}
