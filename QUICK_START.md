# APEX_PREDATOR - Quick Start Guide

## ⚡ Quick Setup (5 Minutes)

### 1. Hardware Connection (2 minutes)
```
□ Connect Arduino Mega 2560 to RAMPS 1.6
□ Install 4 stepper drivers (correct orientation!)
□ Connect 4 NEMA17 motors to X, Y, Z, E0
□ Connect 12V power supply (DON'T power on yet)
□ Connect USB cable from Arduino to PC
□ Connect webcam to PC
□ Connect emergency stop button to Pin 2
```

### 2. Software Installation (2 minutes)
```bash
# Install Python dependencies
pip install -r requirements.txt

# Upload Arduino firmware
# Open apex_predator_hardware.ino in Arduino IDE
# Select: Tools → Board → Arduino Mega 2560
# Click Upload ➡️
```

### 3. Configuration (1 minute)
Edit `apex_predator_engine.py` line 30:
```python
SERIAL_PORT = 'COM3'  # Change to your port
```

Find your port:
- Windows: Device Manager → Ports
- Linux: `ls /dev/ttyACM*`
- Mac: `ls /dev/tty.usbmodem*`

---

## 🚀 First Run

### Start the GUI:
```bash
python gui/apex_predator_gui.py
```

### Initial Test Sequence:
1. **Home the Robot**: Click "🏠 Home"
2. **Enable Motors**: Click "⚡ Enable Motors"
3. **Test Hand Detection**: Wave hand in front of camera
4. **Test Manual Control**: Move joint sliders
5. **Emergency Stop Test**: Press E-Stop button (should work!)

---

## 🎯 Basic Operations

### Manual Control Mode:
```
1. Click "👤 Manual Mode"
2. Use joint sliders to move
3. Monitor positions in real-time
```

### Auto Mode (Soldering Example):
```
1. Select "Soldering Iron" from End Effector dropdown
2. Click "🤖 Auto Mode"
3. Place PCB board in view
4. System automatically:
   - Detects PCB
   - Heats soldering iron
   - Follows your hand movements
   - Maintains safe distance
```

### Teaching Mode:
```
1. Click "📚 Teaching Mode"
2. Move robot to desired positions
3. Toggle heater as needed
4. Click "📚 Teaching Mode" again to stop
5. Use File → Save Program to save
```

---

## 🔴 Emergency Procedures

### Emergency Stop:
```
Physical Button: Press red E-Stop button
Software: Click "🛑 EMERGENCY STOP"
Keyboard: Press 'E' (when engine window active)
```

### Reset After E-Stop:
```
1. Release physical button (if used)
2. Check workspace is clear
3. Click "RESET" or send "RESET_ESTOP" command
```

---

## 📊 Status Indicators

### LED Meanings:
- 🟢 **Status LED Blinking**: System running normally
- 🔴 **Error LED ON**: Emergency stop or error
- 🟢 **Safe LED ON**: Motors enabled and safe to operate

### GUI Status Colors:
- 🟢 **Green**: Safe, normal operation
- 🟡 **Yellow**: Warning, check conditions
- 🔴 **Red**: Error or safety violation

---

## 🎓 Example Tasks

### Task 1: Simple Pick and Place
```python
# Manual mode
1. Move to position above part
2. Lower gripper
3. Close gripper
4. Lift part
5. Move to destination
6. Open gripper
```

### Task 2: Collaborative Soldering
```python
# Auto mode with soldering iron
1. Set end effector to "Soldering Iron"
2. Enable auto mode
3. Place PCB in workspace
4. Hold solder wire near joint
5. Robot follows your hand
6. Maintains safe distance automatically
```

### Task 3: Teaching Session
```python
# Record a sequence
1. Enter teaching mode
2. Manually move robot through sequence
3. Stop recording
4. Save program
5. Replay anytime
```

---

## 🛠️ Troubleshooting (Quick Fixes)

| Problem | Quick Fix |
|---------|-----------|
| Motors not moving | Check if enabled, verify power supply |
| Camera not working | Try different camera index (0, 1, 2) |
| Serial error | Check port name, reconnect USB |
| Hand detection poor | Improve lighting, clean camera |
| Arduino not responding | Press reset button, re-upload code |
| E-Stop won't reset | Verify button is released physically |

---

## 📋 Pre-Operation Checklist

Before each session:
```
□ Workspace clear of obstacles
□ Emergency stop within reach
□ Camera has clear view
□ All connections secure
□ Motors respond to commands
□ Safety systems tested
□ Backup data saved
```

---

## 🎮 Keyboard Shortcuts (Engine Mode)

```
Q - Quit
S - Set Soldering Iron
G - Set Gripper
A - Toggle Auto Mode
T - Toggle Teaching Mode
E - Emergency Stop
M - Manual Mode
H - Home Robot
```

---

## 📞 Getting Help

### Check Logs:
```
GUI: View in "Program Logs" panel
File: apex_predator_engine.log
Arduino: Serial Monitor (115200 baud)
```

### Debug Mode:
```python
# In apex_predator_engine.py, line ~15
logging.basicConfig(level=logging.DEBUG)
```

---

## 🎯 Your First 10 Minutes

**Minute 1-2**: Hardware setup and connections
**Minute 3-4**: Software installation
**Minute 5-6**: Upload firmware and start GUI
**Minute 7**: Test emergency stop
**Minute 8**: Home robot and enable motors
**Minute 9**: Test manual control
**Minute 10**: Test hand detection and safety

**You're ready to go! 🚀**

---

## 🔧 Quick Reference Commands

### Serial Commands (for debugging):
```
HB              - Heartbeat
EN              - Enable motors
DIS             - Disable motors
HOME            - Home all joints
MOV:j1,j2,j3,j4 - Move to position
HEAT_ON         - Enable heater
HEAT_OFF        - Disable heater
STATUS          - Full status report
RESET_ESTOP     - Clear emergency stop
```

### Python API Quick Examples:
```python
# Enable motors
engine.send_command("EN")

# Move to position
engine.move_to_position(1000, 500, -500, 0)

# Enable heater
engine.send_command("HEAT_ON")

# Get feedback
position = engine.hardware_feedback['j1']
temp = engine.hardware_feedback['temp']
```

---

## 🎉 Success Indicators

You know it's working when:
- ✅ Video feed shows with hand tracking
- ✅ Status shows "READY" in green
- ✅ Motors respond to commands
- ✅ Emergency stop triggers immediately
- ✅ Safety violations are detected
- ✅ Camera detects hands and objects

---

## 📚 Next Steps

1. **Learn the system**: Try all modes
2. **Create programs**: Record teaching sessions
3. **Add tasks**: Customize task recognition
4. **Optimize**: Tune speeds and accelerations
5. **Integrate**: Add your custom end effectors
6. **Expand**: Train custom object detection models

**Happy building! 🤖✨**
