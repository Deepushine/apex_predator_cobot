# APEX_PREDATOR - System Architecture & Overview

## 🎯 System Overview

APEX_PREDATOR is a three-tier architecture system combining hardware control, AI processing, and user interface in a cohesive collaborative robot platform.

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER LAYER                              │
│                                                                 │
│  ┌───────────────────────────────────────────────────────┐    │
│  │           PyQt5 GUI Control Center                    │    │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐     │    │
│  │  │ Video Feed │  │   Manual   │  │   Status   │     │    │
│  │  │  Display   │  │  Controls  │  │  Monitor   │     │    │
│  │  └────────────┘  └────────────┘  └────────────┘     │    │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐     │    │
│  │  │  Teaching  │  │   E-Stop   │  │   Logs     │     │    │
│  │  │    Mode    │  │   Button   │  │  Viewer    │     │    │
│  │  └────────────┘  └────────────┘  └────────────┘     │    │
│  └───────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                      AI ENGINE LAYER                            │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐   │
│  │         APEX_PREDATOR_ENGINE (Python)                  │   │
│  │                                                         │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │   │
│  │  │   Computer   │  │     Task     │  │   Safety    │ │   │
│  │  │    Vision    │→ │ Recognition  │→ │  Monitoring │ │   │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │   │
│  │         ↓                  ↓                  ↓        │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │   │
│  │  │     Hand     │  │  Decision    │  │  Emergency  │ │   │
│  │  │   Tracking   │→ │    Making    │← │   Handler   │ │   │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │   │
│  │                           ↓                            │   │
│  │                  ┌─────────────────┐                  │   │
│  │                  │ Command Builder │                  │   │
│  │                  └─────────────────┘                  │   │
│  └────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↕ Serial (115200 baud)
┌─────────────────────────────────────────────────────────────────┐
│                    HARDWARE CONTROL LAYER                       │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐   │
│  │      APEX_PREDATOR_HARDWARE (Arduino Mega)             │   │
│  │                                                         │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │   │
│  │  │   Serial     │→ │   Command    │→ │    Motor    │ │   │
│  │  │   Parser     │  │   Processor  │  │   Control   │ │   │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │   │
│  │                                              ↓         │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │   │
│  │  │   Sensor     │→ │    Safety    │→ │   State     │ │   │
│  │  │   Reader     │  │   Checker    │  │   Machine   │ │   │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │   │
│  │                                              ↓         │   │
│  │                    ┌──────────────────┐              │   │
│  │                    │ Feedback Builder │              │   │
│  │                    └──────────────────┘              │   │
│  └────────────────────────────────────────────────────────┘   │
│                              ↓                                 │
│  ┌────────────────────────────────────────────────────────┐   │
│  │                    RAMPS 1.6 Shield                    │   │
│  └────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     PHYSICAL HARDWARE                           │
│                                                                 │
│  Motors      Sensors       End Effector      Power Supply      │
│  ┌─────┐    ┌──────┐      ┌───────────┐    ┌───────────┐     │
│  │NEMA │    │ ToF  │      │ Soldering │    │    12V    │     │
│  │ 17  │    │      │      │   Iron    │    │    5A     │     │
│  └─────┘    └──────┘      └───────────┘    └───────────┘     │
│  ┌─────┐    ┌──────┐      ┌───────────┐                       │
│  │20:1 │    │Temp  │      │  Gripper  │                       │
│  │Gear │    │      │      │           │                       │
│  └─────┘    └──────┘      └───────────┘                       │
│  ┌─────┐    ┌──────┐                                          │
│  │ x4  │    │E-Stop│                                          │
│  │     │    │      │                                          │
│  └─────┘    └──────┘                                          │
└─────────────────────────────────────────────────────────────────┘
```

## 📊 Data Flow Diagram

```
┌────────────┐
│  Webcam    │ → Raw Video Frame (30fps)
└────┬───────┘
     ↓
┌────────────────────────┐
│  Computer Vision       │
│  - Hand Detection      │ → Hand Position (x, y, confidence)
│  - Object Detection    │ → Detected Objects [label, bbox]
│  - Pose Estimation     │ → Skeleton Points
└────┬───────────────────┘
     ↓
┌────────────────────────┐
│  Task Recognition      │
│  - Analyze context     │ → Recognized Task ("SOLDERING")
│  - Match patterns      │ → Task Parameters
│  - Generate strategy   │ → Action Sequence
└────┬───────────────────┘
     ↓
┌────────────────────────┐
│  Safety Checks         │
│  - Hand distance       │ → Safe: true/false
│  - Proximity sensor    │ → Distance: 250mm
│  - Temperature         │ → Temp: 320°C
│  - Velocity limits     │ → Within limits: true
└────┬───────────────────┘
     ↓
┌────────────────────────┐
│  Decision Making       │
│  - If safe → Execute   │ → Command: "MOV:1000,500,-500,0"
│  - If unsafe → Stop    │ → Command: "DIS"
│  - Emergency → E-Stop  │ → Command: "EMERGENCY"
└────┬───────────────────┘
     ↓
     Serial Communication (115200 baud)
     ↓
┌────────────────────────┐
│  Arduino Parser        │
│  - Receive command     │ ← "MOV:1000,500,-500,0"
│  - Validate syntax     │ → Parsed: {j1:1000, j2:500...}
│  - Queue execution     │
└────┬───────────────────┘
     ↓
┌────────────────────────┐
│  Motor Controller      │
│  - Calculate steps     │ → Steps: [1000, 500, -500, 0]
│  - Set accelerations   │ → Profile: Trapezoidal
│  - Execute movement    │ → Step pulses to drivers
└────┬───────────────────┘
     ↓
┌────────────────────────┐
│  Stepper Drivers       │
│  - A4988/DRV8825       │ → Current to motor coils
│  - Microstepping       │ → 1/16 stepping
│  - Current control     │ → Limited to 1.0A
└────┬───────────────────┘
     ↓
┌────────────────────────┐
│  NEMA17 + Gearbox      │
│  - Rotate motor        │ → Motion
│  - 20:1 reduction      │ → High torque
│  - Position feedback   │ → Encoder counts
└────────────────────────┘
```

## 🔄 Control Loop Timing

```
Every 100ms (10Hz):
┌─────────────────────────────────────┐
│ 1. Read sensors (10ms)              │
│    - ToF distance                   │
│    - Temperature                    │
│    - Endstops                       │
│    - Motor positions                │
├─────────────────────────────────────┤
│ 2. Safety check (5ms)               │
│    - Validate all readings          │
│    - Check limits                   │
│    - Emergency conditions           │
├─────────────────────────────────────┤
│ 3. Update state (5ms)               │
│    - Position tracking              │
│    - Velocity calculation           │
│    - Status update                  │
├─────────────────────────────────────┤
│ 4. Send feedback to PC (5ms)        │
│    - Format: FB:j1,j2,j3,j4,temp... │
├─────────────────────────────────────┤
│ 5. Process commands (10ms)          │
│    - Parse incoming serial          │
│    - Execute motor moves            │
│    - Update end effector            │
├─────────────────────────────────────┤
│ 6. Motor stepping (65ms)            │
│    - AccelStepper.run()             │
│    - Generate step pulses           │
│    - Handle accelerations           │
└─────────────────────────────────────┘

Every 33ms (30Hz):
┌─────────────────────────────────────┐
│ Camera frame processing             │
│ 1. Capture frame                    │
│ 2. Hand detection                   │
│ 3. Object detection                 │
│ 4. Render overlays                  │
│ 5. Display to screen                │
└─────────────────────────────────────┘

Every 500ms (2Hz):
┌─────────────────────────────────────┐
│ Heartbeat transmission              │
│ - Send "HB" to Arduino              │
│ - Reset watchdog timer              │
└─────────────────────────────────────┘
```

## 🧩 Component Interaction Matrix

| Component | Interacts With | Data Exchange | Frequency |
|-----------|----------------|---------------|-----------|
| **GUI** | AI Engine | Control commands, display data | 30Hz |
| **AI Engine** | Camera | Raw frames | 30Hz |
| **AI Engine** | Arduino | Serial commands/feedback | 10Hz |
| **Arduino** | Motors | Step pulses | 1000Hz |
| **Arduino** | Sensors | Analog/digital readings | 10Hz |
| **Arduino** | PC | Status feedback | 10Hz |
| **Vision** | Task Recognizer | Detected objects | Event-based |
| **Safety** | All systems | Emergency signals | Immediate |

## 🔐 Safety Architecture

```
Layer 1: Physical Safety
┌──────────────────────────────────────┐
│ • E-Stop button (hardware interrupt) │
│ • Endstop switches                   │
│ • Motor current limiting             │
│ • Temperature cutoff                 │
└──────────────────────────────────────┘
         ↓ (Immediate stop)
Layer 2: Firmware Safety
┌──────────────────────────────────────┐
│ • Position limit checking            │
│ • Velocity monitoring                │
│ • Sensor validation                  │
│ • Watchdog timer                     │
└──────────────────────────────────────┘
         ↓ (Fast reaction <100ms)
Layer 3: AI Safety
┌──────────────────────────────────────┐
│ • Hand proximity detection           │
│ • Collision prediction               │
│ • Task-based safety rules            │
│ • User intent analysis               │
└──────────────────────────────────────┘
         ↓ (Proactive prevention)
Layer 4: User Override
┌──────────────────────────────────────┐
│ • Manual emergency stop              │
│ • Mode switching                     │
│ • Manual control override            │
│ • Safety disable (with warnings)     │
└──────────────────────────────────────┘
```

## 🎓 Teaching Mode Architecture

```
Recording Phase:
┌────────┐    ┌──────────┐    ┌──────────┐
│ User   │ → │ Move     │ →  │ Record   │
│ Input  │    │ Robot    │    │ Position │
└────────┘    └──────────┘    └──────────┘
                                    ↓
              ┌──────────────────────────┐
              │ Teaching Buffer (500pts) │
              │ {j1, j2, j3, j4, tool,   │
              │  delay, timestamp}       │
              └──────────────────────────┘
                        ↓
              ┌──────────────────────────┐
              │ Save to Program File     │
              │ (JSON format)            │
              └──────────────────────────┘

Playback Phase:
┌──────────────────────────┐
│ Load Program File        │
└────────┬─────────────────┘
         ↓
┌──────────────────────────┐
│ For each point:          │
│ 1. Move to position      │
│ 2. Set tool state        │
│ 3. Wait delay            │
│ 4. Check safety          │
└────────┬─────────────────┘
         ↓
┌──────────────────────────┐
│ Interpolate between      │
│ points (smooth motion)   │
└──────────────────────────┘
```

## 🔌 Communication Protocol

### Command Format (PC → Arduino):
```
Command Structure: <CMD>:<PARAMS>\n

Examples:
EN                    - Enable motors
DIS                   - Disable motors
MOV:1000,500,-500,0  - Move to position
HEAT_ON               - Enable heater
SPEED:1500            - Set speed
MODE:AUTO             - Set auto mode
```

### Feedback Format (Arduino → PC):
```
Feedback Structure: <TYPE>:<DATA>\n

FB:j1,j2,j3,j4,temp,dist,mode,motors,heater
   ↑  ↑  ↑  ↑  ↑    ↑    ↑    ↑       ↑
   │  │  │  │  │    │    │    │       └─ Heater state (0/1)
   │  │  │  │  │    │    │    └───────── Motors enabled (0/1)
   │  │  │  │  │    │    └────────────── Current mode (0-6)
   │  │  │  │  │    └─────────────────── ToF distance (mm)
   │  │  │  │  └──────────────────────── Temperature (°C)
   │  │  │  └─────────────────────────── Joint 4 position
   │  │  └────────────────────────────── Joint 3 position
   │  └───────────────────────────────── Joint 2 position
   └──────────────────────────────────── Joint 1 position

STS:<STATUS_MESSAGE>     - Status update
STS:EMERGENCY_STOP       - Emergency condition
STS:HOMING_COMPLETE      - Operation complete
```

## 📈 Performance Characteristics

### Latency Budget:
```
User Input → Screen Update: <50ms
Vision → Decision: <33ms (30Hz)
Decision → Motor Command: <10ms
Command → Motor Response: <100ms
Total System Latency: ~200ms
```

### Throughput:
```
Serial Communication: 115200 baud (11.5 KB/s)
Video Processing: 30fps (1280x720)
Motor Control: 1000 steps/sec/motor max
Position Updates: 10Hz
Teaching Recording: 5Hz
```

## 🎯 Task Recognition Pipeline

```
┌─────────────┐
│ Raw Video   │
└──────┬──────┘
       ↓
┌─────────────────────┐
│ Object Detection    │
│ - YOLOv8 / Custom   │ → [PCB, Wire, Component...]
│ - Confidence > 0.7  │
└──────┬──────────────┘
       ↓
┌─────────────────────┐
│ Context Analysis    │
│ - What objects?     │ → Context: "Soldering Setup"
│ - End effector?     │
│ - Hand position?    │
└──────┬──────────────┘
       ↓
┌─────────────────────┐
│ Task Matching       │
│ - Pattern match     │ → Matched: "SOLDERING_TASK"
│ - Rule evaluation   │
└──────┬──────────────┘
       ↓
┌─────────────────────┐
│ Action Planning     │
│ - Heat iron         │ → Plan: {heat, wait, follow}
│ - Position robot    │
│ - Follow hand       │
└──────┬──────────────┘
       ↓
┌─────────────────────┐
│ Execution           │
│ - Monitor safety    │ → Active execution with
│ - Adapt to changes  │   continuous monitoring
│ - Provide feedback  │
└─────────────────────┘
```

## 🚨 Emergency Stop Sequence

```
Emergency Detected:
┌─────────────────┐
│ Trigger Source: │
│ - Button press  │
│ - Safety sensor │
│ - Software cmd  │
└────────┬────────┘
         ↓ (Immediate)
┌─────────────────────────┐
│ Hardware Interrupt ISR  │ ← Highest priority
│ Set emergencyStop flag  │
└────────┬────────────────┘
         ↓ (< 1ms)
┌─────────────────────────┐
│ Stop All Motors         │
│ - joint1.stop()         │
│ - joint2.stop()         │
│ - joint3.stop()         │
│ - joint4.stop()         │
└────────┬────────────────┘
         ↓ (< 10ms)
┌─────────────────────────┐
│ Disable Motor Power     │
│ Set enable pins HIGH    │
└────────┬────────────────┘
         ↓
┌─────────────────────────┐
│ Disable End Effector    │
│ Turn off heater/tools   │
└────────┬────────────────┘
         ↓
┌─────────────────────────┐
│ Set Error Indicators    │
│ - LED RED               │
│ - Send status to PC     │
└────────┬────────────────┘
         ↓
┌─────────────────────────┐
│ Wait for Reset Command  │
│ User must acknowledge   │
└─────────────────────────┘
```

## 🔧 Extension Points

The system is designed to be extensible at multiple points:

1. **Vision Models**: Swap MediaPipe for custom models
2. **Task Recognition**: Add new task handlers
3. **End Effectors**: Plugin architecture for tools
4. **Safety Rules**: Configurable safety parameters
5. **Communication**: Support for other protocols
6. **Kinematics**: Add IK/FK modules
7. **Planning**: Integrate motion planning

---

This architecture provides a solid foundation for a sophisticated collaborative robot system while remaining accessible for customization and extension.
