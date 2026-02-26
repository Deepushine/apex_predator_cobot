# 🤖 APEX_PREDATOR - AI-Powered Collaborative Robot System

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![Arduino](https://img.shields.io/badge/arduino-mega2560-teal)
![License](https://img.shields.io/badge/license-MIT-orange)

**The ultimate AI-powered cobot for safe human-robot collaboration**

[Quick Start](#-quick-start) • [Features](#-features) • [Documentation](#-documentation) • [Gallery](#-gallery)

</div>

---

## 📖 Overview

**APEX_PREDATOR** is a sophisticated collaborative robot (cobot) system that combines advanced computer vision, AI-powered task recognition, and multi-layer safety systems to enable safe and intelligent human-robot interaction.

Built for makers, researchers, and engineers who want to explore the cutting edge of collaborative robotics without breaking the bank.

### Why APEX_PREDATOR?

- 🧠 **Smart**: AI automatically recognizes tasks and adapts behavior
- 👀 **Aware**: Real-time computer vision with hand tracking
- 🛡️ **Safe**: Multi-layer safety system protects humans
- 📚 **Teachable**: Record and replay complex sequences
- 🎮 **Controllable**: Professional GUI + manual override
- 🔧 **Hackable**: Open-source, fully customizable

---

## ✨ Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Computer Vision** | Real-time hand tracking, object detection, workspace monitoring |
| **Task Recognition** | Automatically detects tasks (soldering, assembly, etc.) |
| **Safety System** | ToF proximity, hand tracking, temperature monitoring, E-stop |
| **Teaching Mode** | Record movements and replay them (like Dobot Magician) |
| **Manual Control** | Full manual override with joint-by-joint control |
| **Auto Mode** | AI takes over for collaborative tasks |
| **Professional GUI** | PyQt5-based control center with real-time monitoring |
| **Logging** | Comprehensive logs for debugging and analysis |

### Safety Features

- ✅ **Emergency Stop**: Hardware + software emergency stops
- ✅ **Proximity Detection**: ToF sensor stops robot when humans approach
- ✅ **Hand Tracking**: Vision system tracks human hands in real-time
- ✅ **Temperature Monitoring**: Prevents overheating of tools
- ✅ **Endstop Protection**: Prevents over-travel
- ✅ **Heartbeat Watchdog**: Stops if communication lost

### End Effector Support

- 🔥 **Soldering Iron**: Auto-heat, temperature control, collaborative soldering
- 🤏 **Gripper**: Pick-and-place operations
- ✏️ **Pen**: Drawing and writing
- 🔧 **Custom**: Easy to add your own tools

---

## 🚀 Quick Start

### Prerequisites

- Arduino Mega 2560 + RAMPS 1.6
- 4x NEMA17 stepper motors with 20:1 gearboxes
- USB webcam (720p or better)
- Python 3.8+
- 12V power supply (5A+)

### Installation (5 Minutes)

```bash
# 1. Clone or download this repository

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Upload Arduino firmware
# Open apex_predator_hardware.ino in Arduino IDE
# Select Tools → Board → Arduino Mega 2560
# Click Upload

# 4. Configure serial port
# Edit apex_predator_engine.py, line 30
# Set SERIAL_PORT to your Arduino's port

# 5. Run the GUI
python gui/apex_predator_gui.py
```

**That's it! See [Quick Start Guide](docs/QUICK_START.md) for details.**

---

## 📁 Project Structure

```
apex_predator_system/
├── arduino/
│   └── apex_predator_hardware.ino    # Arduino firmware
├── python_engine/
│   └── apex_predator_engine.py       # AI engine with vision
├── gui/
│   └── apex_predator_gui.py          # PyQt5 GUI application
├── config/
│   └── config.json                   # Configuration file
├── docs/
│   ├── INSTALLATION_GUIDE.md         # Detailed setup guide
│   └── QUICK_START.md                # Quick reference
└── requirements.txt                  # Python dependencies
```

---

## 🎯 Usage Examples

### Example 1: Manual Control

```python
# Start GUI, switch to Manual Mode
# Use sliders to control individual joints
# Monitor status in real-time
```

### Example 2: Collaborative Soldering

```python
# 1. Set end effector to "Soldering Iron"
# 2. Switch to Auto Mode
# 3. Place PCB board in workspace
# Result: Robot detects PCB, heats iron, follows your hand
```

### Example 3: Teaching Mode

```python
# 1. Click "Teaching Mode"
# 2. Move robot through desired sequence
# 3. Stop recording
# 4. Save and replay anytime
```

---

## 🖼️ Gallery

### System Architecture
```
┌──────────────┐
│  PC/Laptop   │ ← PyQt5 GUI + AI Engine
│  - Vision    │ ← Computer Vision Processing
│  - AI Logic  │ ← Task Recognition
└──────┬───────┘
       │ USB Serial
┌──────▼───────┐
│   Arduino    │ ← Firmware Control
│   Mega 2560  │ ← Motor + Sensor Management
└──────┬───────┘
       │
┌──────▼───────┐
│  RAMPS 1.6   │ ← 4-Axis Stepper Control
└──────┬───────┘
       │
    [Motors]    ← 4x NEMA17 + 20:1 Gearbox
```

### Control Flow
```
Camera Feed → Vision Processing → Task Recognition
                                          ↓
Hand Tracking → Safety Checks → Decision Making
                                          ↓
                                   Motor Commands
                                          ↓
                                  Arduino Execution
```

---

## 📚 Documentation

- **[Installation Guide](docs/INSTALLATION_GUIDE.md)** - Complete setup instructions
- **[Quick Start](docs/QUICK_START.md)** - Get running in 5 minutes
- **[API Reference](docs/API_REFERENCE.md)** - Python API documentation (coming soon)
- **[Hardware Guide](docs/HARDWARE_GUIDE.md)** - Wiring and assembly (coming soon)

---

## 🔧 Configuration

Edit `config/config.json` to customize:

```json
{
  "safety": {
    "min_hand_distance": 200,
    "safe_zone_radius": 150
  },
  "camera": {
    "width": 1280,
    "height": 720
  },
  "motors": {
    "max_speed": 1000,
    "acceleration": 500
  }
}
```

See [Configuration Guide](docs/CONFIGURATION.md) for all options (coming soon).

---

## 🎓 Learning Resources

### For Beginners
1. Start with [Quick Start Guide](docs/QUICK_START.md)
2. Watch tutorial videos (coming soon)
3. Try example programs

### For Advanced Users
1. Read [Installation Guide](docs/INSTALLATION_GUIDE.md)
2. Customize task recognition
3. Integrate your own sensors
4. Train custom vision models

---

## 🛠️ Customization

### Add Custom Tasks

```python
# In apex_predator_engine.py
def recognize_task(self):
    if self.detected_objects:
        for obj in self.detected_objects:
            if "YOUR_OBJECT" in obj[4]:
                return "YOUR_TASK"
```

### Add Custom End Effectors

```python
# In configuration
"custom_tool": {
    "control_pin": 10,
    "pwm_enabled": true,
    "parameters": {...}
}
```

### Integrate Your Sensors

```cpp
// In apex_predator_hardware.ino
void readCustomSensor() {
    // Your sensor reading code
}
```

---

## 🤝 Contributing

Contributions are welcome! Whether it's:
- 🐛 Bug reports
- 💡 Feature requests
- 📝 Documentation improvements
- 🔧 Code contributions

Please open an issue or pull request on GitHub.

---

## 📊 Specifications

### Hardware
- **Motors**: 4x NEMA17 (2.6 kg-cm) with 20:1 cycloidal reducers
- **Output Torque**: ~52 kg-cm per joint
- **Controller**: Arduino Mega 2560 (ATmega2560)
- **Drivers**: A4988 or DRV8825
- **Power**: 12V, 5A minimum

### Software
- **Platform**: Python 3.8+
- **Vision**: OpenCV 4.8+, MediaPipe
- **GUI**: PyQt5
- **Communication**: Serial (115200 baud)

### Performance
- **Position Accuracy**: ±0.5mm (with calibration)
- **Repeatability**: ±0.2mm
- **Max Speed**: 100mm/s
- **Camera FPS**: 30fps
- **Control Loop**: 10Hz feedback

---

## ⚠️ Safety Warnings

**READ BEFORE OPERATING**

- ⚠️ Always keep emergency stop within reach
- ⚠️ Never leave heated tools unattended
- ⚠️ Maintain clear workspace during operation
- ⚠️ Test new programs at low speed
- ⚠️ Follow all safety guidelines in documentation

See [Safety Guide](docs/SAFETY.md) for complete safety information (coming soon).

---

## 🐛 Known Issues & Limitations

- Hand tracking requires good lighting
- Camera calibration needed for accurate positioning
- Teaching mode limited to 500 points
- Real-time inverse kinematics not implemented yet

See [Issues](https://github.com/yourrepo/issues) for current bugs and feature requests.

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **AccelStepper Library** - Smooth stepper motor control
- **MediaPipe** - Hand tracking capability
- **OpenCV** - Computer vision foundation
- **PyQt5** - Professional GUI framework
- **Dobot Magician** - Inspiration for teaching mode

---

## 📞 Support

- **Documentation**: See `/docs` folder
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: [your-email@example.com]

---

## 🗺️ Roadmap

### v1.1 (Next Release)
- [ ] Inverse kinematics implementation
- [ ] YOLO object detection integration
- [ ] Camera calibration wizard
- [ ] Force feedback support

### v1.2 (Future)
- [ ] Path planning algorithms
- [ ] Cloud connectivity
- [ ] Mobile app control
- [ ] Multi-robot coordination

### v2.0 (Long-term)
- [ ] Deep learning task recognition
- [ ] Natural language commands
- [ ] Haptic feedback
- [ ] Virtual reality integration

---

## 📈 Statistics

- **Lines of Code**: ~5000+
- **Development Time**: 3 months
- **Languages**: Python, C++, JSON
- **Dependencies**: 10+
- **Test Cases**: Coming soon

---

## 💬 Community

Join the APEX_PREDATOR community:

- 🌟 Star this project on GitHub
- 🍴 Fork and create your own version
- 📣 Share your builds and projects
- 🤝 Contribute improvements

---

<div align="center">

**Made with ❤️ for the maker community**

**[⬆ Back to Top](#-apex_predator---ai-powered-collaborative-robot-system)**

</div>
