# APEX_PREDATOR System - Complete Installation & Setup Guide

## 🎯 System Overview

**APEX_PREDATOR** is an AI-powered collaborative robot (cobot) system designed for safe human-robot interaction with automatic task recognition and execution.

### Key Features:
- ✅ Real-time computer vision with hand tracking
- ✅ Automatic task detection (soldering, assembly, etc.)
- ✅ Multi-layer safety system
- ✅ Teaching and playback modes
- ✅ Professional GUI control center
- ✅ Manual control override
- ✅ Emergency stop system
- ✅ Comprehensive logging

---

## 📋 Hardware Requirements

### Required Components:
1. **Arduino Mega 2560** - Main controller
2. **RAMPS 1.6 Shield** - Motor driver interface
3. **4x A4988/DRV8825 Stepper Drivers** - Motor control
4. **4x NEMA17 Stepper Motors** (ET6131 or similar, 2.6 kg-cm)
5. **4x 20:1 Cycloidal Reducers** - Torque multiplication
6. **Power Supply** - 12V, minimum 5A
7. **Webcam** - USB camera (720p or higher recommended)
8. **ToF Distance Sensor** (VL53L0X or similar) - Proximity detection
9. **Temperature Sensor** (Thermocouple with MAX31855 or similar)
10. **4x Endstop Switches** - Homing and limits
11. **Emergency Stop Button** (normally-open, latching)
12. **PC/Laptop** - Windows/Linux, Python 3.8+

### Optional Components:
- Soldering iron end effector
- Gripper end effector
- Additional sensors (force, current, etc.)
- LED status indicators

---

## 🔌 Hardware Setup

### Step 1: RAMPS 1.6 Assembly

1. **Install Stepper Drivers**:
   - Insert drivers into X, Y, Z, and E0 slots
   - **CRITICAL**: Ensure correct orientation (potentiometer towards power input)
   - Set microstepping jumpers (recommended: 1/16 microstepping)

2. **Connect Motors**:
   - **Joint 1 (Base)** → X-axis terminal
   - **Joint 2** → Y-axis terminal
   - **Joint 3** → Z-axis terminal
   - **Joint 4 (Wrist)** → E0-axis terminal

3. **Power Connection**:
   - Connect 12V power supply to RAMPS power terminals
   - Verify polarity (+ to +, - to -)
   - **DO NOT** power on yet

### Step 2: Sensor Connections

#### ToF Distance Sensor (I2C):
```
VL53L0X → Arduino Mega
VCC     → 5V
GND     → GND
SDA     → SDA (Pin 20)
SCL     → SCL (Pin 21)
```

#### Temperature Sensor:
```
MAX31855 → Arduino Mega
VCC      → 5V
GND      → GND
DO       → Pin 50
CS       → Pin 53
CLK      → Pin 52
```

#### Endstop Switches:
```
Joint 1 Endstop → Pin 3
Joint 2 Endstop → Pin 14
Joint 3 Endstop → Pin 18
Joint 4 Endstop → Pin 19
Common          → GND
```

#### Emergency Stop:
```
E-Stop Button → Pin 2 + GND
(Normally open, connects to GND when pressed)
```

#### Heater Control (for soldering iron):
```
MOSFET/Relay → Pin 8 (ON/OFF)
PWM Control  → Pin 9 (Temperature regulation)
```

### Step 3: Driver Current Adjustment

**CRITICAL FOR MOTOR HEALTH**

For NEMA17 ET6131 motors (rated ~1.0-1.5A):

1. **Measure Vref** (driver potentiometer to GND):
   - Target: **0.4-0.6V** for A4988
   - Target: **0.5-0.8V** for DRV8825

2. **Formula for A4988**: Vref = Current_Limit / 2.5
   - For 1.0A: Vref = 0.4V
   - For 1.2A: Vref = 0.48V

3. **Adjustment**:
   - Power on the system
   - Use multimeter on DC voltage mode
   - Slowly turn potentiometer clockwise to increase
   - Start low, increase gradually while testing

---

## 💻 Software Installation

### Step 1: Arduino IDE Setup

1. **Install Arduino IDE**:
   - Download from: https://www.arduino.cc/en/software
   - Install version 2.0 or higher

2. **Install AccelStepper Library**:
   ```
   Tools → Manage Libraries → Search "AccelStepper"
   Install "AccelStepper by Mike McCauley"
   ```

3. **Configure Board**:
   ```
   Tools → Board → Arduino Mega or Mega 2560
   Tools → Processor → ATmega2560
   Tools → Port → [Select your Arduino's COM port]
   ```

4. **Upload Firmware**:
   - Open `apex_predator_hardware.ino`
   - Click Upload (➡️ button)
   - Wait for "Done uploading"

### Step 2: Python Environment Setup

#### Windows:

```bash
# Install Python 3.8 or higher from python.org

# Create virtual environment
python -m venv apex_env

# Activate environment
apex_env\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### Linux/Mac:

```bash
# Install Python 3.8+ (usually pre-installed)

# Create virtual environment
python3 -m venv apex_env

# Activate environment
source apex_env/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Port Configuration

Edit `apex_predator_engine.py`:

```python
# Line ~30
SERIAL_PORT = 'COM3'  # Windows: 'COM3', 'COM4', etc.
                      # Linux: '/dev/ttyACM0', '/dev/ttyUSB0'
                      # Mac: '/dev/tty.usbmodem*'
```

To find your port:
- **Windows**: Device Manager → Ports (COM & LPT)
- **Linux**: `ls /dev/ttyACM* /dev/ttyUSB*`
- **Mac**: `ls /dev/tty.usbmodem*`

---

## 🚀 Running the System

### Option 1: GUI Mode (Recommended)

```bash
# Activate environment
apex_env\Scripts\activate  # Windows
source apex_env/bin/activate  # Linux/Mac

# Run GUI
python gui/apex_predator_gui.py
```

### Option 2: Engine Only (No GUI)

```bash
# Activate environment
apex_env\Scripts\activate  # Windows
source apex_env/bin/activate  # Linux/Mac

# Run engine
python python_engine/apex_predator_engine.py
```

**Keyboard Controls (Engine only)**:
- `Q` - Quit
- `S` - Set soldering iron end effector
- `A` - Toggle auto mode
- `T` - Toggle teaching mode
- `E` - Emergency stop

---

## 📖 Usage Guide

### First Time Setup

1. **Power On Sequence**:
   - Connect USB cable to PC
   - Power on Arduino (it will reset)
   - Wait 5 seconds for initialization
   - Power on 12V supply
   - Run the GUI application

2. **Initial Calibration**:
   - Click "🏠 Home" to home all joints
   - Verify each joint moves to endstop
   - Check motor directions (reverse wiring if needed)

3. **Camera Setup**:
   - Position camera to view workspace
   - Ensure good lighting
   - Test hand detection by waving hand

### Operating Modes

#### 1. Manual Mode
- Use joint sliders to control individual joints
- Direct control via GUI buttons
- Safety monitoring still active

#### 2. Auto Mode
- System detects tasks automatically
- Example: Detects PCB board → heats soldering iron
- Follows hand movements for collaborative work

#### 3. Teaching Mode
- Record a sequence of movements
- "📚 Teaching Mode" to start recording
- Move joints manually or via GUI
- Stop recording when done
- Replay anytime with recorded sequence

### Safety Features

**Multi-Layer Safety System**:

1. **Emergency Stop Button** - Hardware interrupt, stops everything
2. **ToF Proximity Detection** - Stops if obstacle detected < 150mm
3. **Hand Tracking** - Monitors human presence and distance
4. **Temperature Monitoring** - Prevents overheating
5. **Endstop Protection** - Prevents over-travel
6. **Heartbeat Watchdog** - Stops if PC communication lost

**To Reset E-Stop**:
1. Release physical E-Stop button
2. Click "RESET" in software or send "RESET_ESTOP" command

---

## 🔧 Configuration

### Adjusting Safety Parameters

Edit `apex_predator_engine.py`:

```python
class Config:
    MIN_HAND_DISTANCE = 200      # mm - safe distance from hand
    MAX_VELOCITY = 100           # mm/s - max speed
    SAFE_ZONE_RADIUS = 150       # mm - proximity alert
    SOLDER_PREHEAT_TIME = 30     # seconds
    SOLDER_TEMP_TARGET = 350     # °C
```

### Adjusting Motor Parameters

Edit `apex_predator_hardware.ino`:

```cpp
#define MICROSTEPS         16    // Match your jumper settings
#define MAX_SPEED          1000  // steps/second
#define ACCELERATION       500   // steps/second²
```

### Joint Limits

```cpp
#define J1_MIN            -180   // degrees
#define J1_MAX             180
#define J2_MIN            -90
#define J2_MAX             90
// ... etc
```

---

## 🎓 Dobot-Style Teaching Session

Since you have experience with Dobot Magician, here's how APEX_PREDATOR compares:

### Recording a Teaching Session:

1. **Enter Teaching Mode**:
   - Click "📚 Teaching Mode" button
   - Status shows "TEACHING"

2. **Move the Robot**:
   - Use manual joint sliders
   - Or physically move if using compliant mode
   - System records positions at 5Hz

3. **Control End Effector**:
   - Toggle heater during recording
   - States are recorded with positions

4. **Stop Recording**:
   - Click "📚 Teaching Mode" again
   - Session saved to memory

5. **Playback**:
   - Load saved session
   - Click "Play" to replay movements
   - Robot executes recorded trajectory

### Saving/Loading Programs:

```python
# Programs saved as JSON:
{
  "name": "PCB Soldering",
  "points": [
    {"j1": 0, "j2": 0, "j3": 0, "j4": 0, "tool": "on", "delay": 1000},
    {"j1": 100, "j2": 50, "j3": -30, "j4": 0, "tool": "on", "delay": 500},
    // ...
  ]
}
```

---

## 🔍 Troubleshooting

### Common Issues:

#### "Serial Port Not Found"
- Check USB connection
- Verify correct port in code
- Try different USB port
- Linux: Add user to dialout group: `sudo usermod -a -G dialout $USER`

#### "Camera Not Detected"
- Check camera is plugged in
- Try different `CAMERA_INDEX` (0, 1, 2...)
- Install camera drivers if needed
- Test camera with other software first

#### "Motors Not Moving"
- Check enable pins are LOW (motors enabled)
- Verify driver Vref adjustment
- Check motor connections
- Ensure 12V power is connected
- Look for overheating on drivers

#### "Hand Detection Not Working"
- Ensure good lighting
- Camera needs clear view of hands
- Try adjusting detection confidence
- Update MediaPipe if needed

#### "Arduino Not Responding"
- Check serial connection
- Verify baud rate (115200)
- Reset Arduino
- Re-upload firmware

### Debug Mode:

Enable debug logging in Python:

```python
logging.basicConfig(level=logging.DEBUG)  # Change from INFO
```

View Arduino serial monitor:
- Arduino IDE → Tools → Serial Monitor
- Set baud rate to 115200
- Send commands manually:
  - `STATUS` - Get full status
  - `EN` - Enable motors
  - `HB` - Send heartbeat

---

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    PC / Laptop                          │
│                                                         │
│  ┌──────────────────┐         ┌──────────────────┐    │
│  │   GUI Interface  │◄────────┤  AI Engine       │    │
│  │   (PyQt5)        │         │  - Vision        │    │
│  │                  │         │  - Task Detect   │    │
│  └────────┬─────────┘         │  - Safety        │    │
│           │                   └────────┬─────────┘    │
│           │                            │              │
│           └────────────┬───────────────┘              │
│                        │ Serial (115200 baud)         │
└────────────────────────┼──────────────────────────────┘
                         │
                    ┌────▼────┐
                    │  USB    │
                    └────┬────┘
                         │
┌────────────────────────┼──────────────────────────────┐
│                 Arduino Mega 2560                      │
│                        │                               │
│  ┌─────────────────────▼────────────────────┐         │
│  │    APEX_PREDATOR_HARDWARE Firmware       │         │
│  │  - Motor Control                         │         │
│  │  - Sensor Reading                        │         │
│  │  - Safety Monitoring                     │         │
│  │  - Teaching Recording                    │         │
│  └─────────────────┬────────────────────────┘         │
│                    │                                   │
└────────────────────┼───────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
   ┌────▼───┐   ┌───▼────┐   ┌──▼──────┐
   │ RAMPS  │   │Sensors │   │ End     │
   │  1.6   │   │- ToF   │   │Effector │
   │        │   │- Temp  │   │- Heater │
   └───┬────┘   │- E-Stop│   │- Gripper│
       │        └────────┘   └─────────┘
  ┌────▼─────┐
  │4x NEMA17 │
  │+ Gearbox │
  └──────────┘
```

---

## 🎯 Advanced Features

### Custom Task Recognition

Add new tasks by modifying `apex_predator_engine.py`:

```python
def recognize_task(self):
    # Add your custom detection
    if self.end_effector_type == EndEffectorType.CUSTOM:
        # Detect your specific objects
        for obj in self.detected_objects:
            if "YOUR_OBJECT" in obj[4]:
                return "YOUR_CUSTOM_TASK"
    return None

def handle_custom_task(self):
    # Implement your task logic
    logger.info("Executing custom task")
    # Your code here
```

### Adding YOLO Object Detection

```python
# Install: pip install ultralytics

from ultralytics import YOLO

# In __init__:
self.yolo_model = YOLO('yolov8n.pt')  # or your trained model

# In detect_objects:
results = self.yolo_model(frame)
for result in results:
    boxes = result.boxes
    for box in boxes:
        x1, y1, x2, y2 = box.xyxy[0]
        conf = box.conf[0]
        cls = int(box.cls[0])
        label = self.yolo_model.names[cls]
        # Add to detected_objects
```

### Inverse Kinematics Integration

For moving to Cartesian coordinates (x, y, z):

```python
def move_to_cartesian(self, x, y, z):
    """Move end effector to Cartesian position"""
    # Implement your IK solution
    j1, j2, j3, j4 = self.inverse_kinematics(x, y, z)
    self.move_to_position(j1, j2, j3, j4)
```

---

## 📝 Maintenance

### Regular Checks:
- ✓ Check motor temperatures during operation
- ✓ Verify all connections are secure
- ✓ Clean camera lens
- ✓ Lubricate joints if needed
- ✓ Check driver heatsinks
- ✓ Inspect cables for wear

### Calibration:
- Camera calibration: Every 6 months
- Temperature sensor: Monthly verification
- ToF sensor: Clean when readings drift

---

## 📚 Additional Resources

### Documentation:
- AccelStepper: http://www.airspayce.com/mikem/arduino/AccelStepper/
- MediaPipe: https://google.github.io/mediapipe/
- OpenCV: https://docs.opencv.org/
- PyQt5: https://www.riverbankcomputing.com/static/Docs/PyQt5/

### Support:
- Check logs: `apex_predator_engine.log`
- Arduino serial monitor for hardware debug
- Enable debug mode for detailed output

---

## ⚠️ Safety Guidelines

**ALWAYS FOLLOW THESE RULES**:

1. ✋ Keep hands clear during automatic operation
2. 🔴 Emergency stop must be within reach
3. 🔥 Never leave heated tools unattended
4. 👀 Maintain visual supervision during operation
5. 🧪 Test new programs at low speed first
6. 🔌 Power off before hardware changes
7. 🏠 Always home robot after power cycle
8. 📏 Verify joint limits before operation

---

## 🎉 You're Ready!

Your APEX_PREDATOR system is now fully configured. Start with manual mode to familiarize yourself, then progress to teaching and auto modes.

Good luck with your collaborative robot project! 🤖✨
