"""
═══════════════════════════════════════════════════════════════════
                APEX_PREDATOR GUI Control Center
═══════════════════════════════════════════════════════════════════

Professional GUI for cobot control and monitoring
Features:
- Real-time video feed
- Manual control override
- Emergency stop
- Program logs
- Teaching session management
- System status monitoring

═══════════════════════════════════════════════════════════════════
"""

import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import json
from datetime import datetime
import threading
import time

# Import the engine
from apex_predator_engine import ApexPredatorEngine, SystemState, EndEffectorType

# ═══════════════════════════════════════════════════════════════════
# VIDEO THREAD
# ═══════════════════════════════════════════════════════════════════

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)
    
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._run_flag = True
    
    def run(self):
        while self._run_flag and self.engine.camera:
            ret, frame = self.engine.camera.read()
            if ret:
                # Process frame
                processed_frame = self.engine.process_frame(frame)
                self.engine.add_status_overlay(processed_frame)
                self.change_pixmap_signal.emit(processed_frame)
            self.msleep(30)  # ~30 FPS
    
    def stop(self):
        self._run_flag = False
        self.wait()

# ═══════════════════════════════════════════════════════════════════
# MAIN GUI CLASS
# ═══════════════════════════════════════════════════════════════════

class ApexPredatorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize engine
        self.engine = ApexPredatorEngine()
        self.video_thread = None
        
        self.setWindowTitle("APEX PREDATOR Control Center")
        self.setGeometry(100, 100, 1600, 900)
        self.setStyleSheet(self.get_stylesheet())
        
        # Create UI
        self.init_ui()
        
        # Timers
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(100)  # Update at 10Hz
        
        # Initialize engine in separate thread
        QTimer.singleShot(500, self.initialize_engine)
    
    def init_ui(self):
        """Initialize user interface"""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Left panel - Video and controls
        left_panel = self.create_left_panel()
        main_layout.addWidget(left_panel, stretch=2)
        
        # Right panel - Status and logs
        right_panel = self.create_right_panel()
        main_layout.addWidget(right_panel, stretch=1)
        
        # Menu bar
        self.create_menu_bar()
        
        # Status bar
        self.statusBar().showMessage("Ready")
    
    def create_left_panel(self):
        """Create left panel with video feed and main controls"""
        panel = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)
        
        # Video feed
        video_group = QGroupBox("Live Camera Feed")
        video_layout = QVBoxLayout()
        video_group.setLayout(video_layout)
        
        self.video_label = QLabel()
        self.video_label.setMinimumSize(960, 540)
        self.video_label.setStyleSheet("background-color: #1e1e1e; border: 2px solid #3d3d3d;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setText("Initializing Camera...")
        video_layout.addWidget(self.video_label)
        
        layout.addWidget(video_group)
        
        # Control buttons
        controls_group = QGroupBox("System Controls")
        controls_layout = QGridLayout()
        controls_group.setLayout(controls_layout)
        
        # Emergency Stop (large, red)
        self.btn_estop = QPushButton("🛑 EMERGENCY STOP")
        self.btn_estop.setMinimumHeight(60)
        self.btn_estop.setStyleSheet("""
            QPushButton {
                background-color: #cc0000;
                color: white;
                font-size: 18px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #ff0000;
            }
            QPushButton:pressed {
                background-color: #990000;
            }
        """)
        self.btn_estop.clicked.connect(self.emergency_stop)
        controls_layout.addWidget(self.btn_estop, 0, 0, 1, 2)
        
        # Mode buttons
        self.btn_auto = QPushButton("🤖 Auto Mode")
        self.btn_auto.clicked.connect(self.toggle_auto_mode)
        controls_layout.addWidget(self.btn_auto, 1, 0)
        
        self.btn_manual = QPushButton("👤 Manual Mode")
        self.btn_manual.clicked.connect(self.set_manual_mode)
        controls_layout.addWidget(self.btn_manual, 1, 1)
        
        self.btn_teach = QPushButton("📚 Teaching Mode")
        self.btn_teach.clicked.connect(self.toggle_teaching_mode)
        controls_layout.addWidget(self.btn_teach, 2, 0)
        
        self.btn_home = QPushButton("🏠 Home")
        self.btn_home.clicked.connect(self.home_robot)
        controls_layout.addWidget(self.btn_home, 2, 0)
        
        self.btn_home_all = QPushButton("🏠 HOME ALL JOINTS")
        self.btn_home_all.setMinimumHeight(40)
        self.btn_home_all.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.btn_home_all.clicked.connect(self.home_all_joints)
        controls_layout.addWidget(self.btn_home_all, 2, 1)
        
        # Motor controls
        self.btn_enable_motors = QPushButton("⚡ Enable Motors")
        self.btn_enable_motors.clicked.connect(self.enable_motors)
        controls_layout.addWidget(self.btn_enable_motors, 3, 0)
        
        self.btn_disable_motors = QPushButton("🔌 Disable Motors")
        self.btn_disable_motors.clicked.connect(self.disable_motors)
        controls_layout.addWidget(self.btn_disable_motors, 3, 1)
        
        # Motor diagnostic buttons
        self.btn_test_j1 = QPushButton("Test J1 (X)")
        self.btn_test_j1.clicked.connect(lambda: self.test_motor(1))
        controls_layout.addWidget(self.btn_test_j1, 4, 0)
        
        self.btn_test_j2 = QPushButton("Test J2 (Y)")
        self.btn_test_j2.clicked.connect(lambda: self.test_motor(2))
        controls_layout.addWidget(self.btn_test_j2, 4, 1)
        
        self.btn_test_j3 = QPushButton("Test J3 (Z)")
        self.btn_test_j3.clicked.connect(lambda: self.test_motor(3))
        controls_layout.addWidget(self.btn_test_j3, 5, 0)
        
        layout.addWidget(controls_group)
        
        # End effector controls
        effector_group = QGroupBox("End Effector")
        effector_layout = QHBoxLayout()
        effector_group.setLayout(effector_layout)
        
        self.combo_effector = QComboBox()
        self.combo_effector.addItems(["None", "Soldering Iron", "Gripper", "Pen", "Custom"])
        self.combo_effector.currentIndexChanged.connect(self.change_end_effector)
        effector_layout.addWidget(QLabel("Type:"))
        effector_layout.addWidget(self.combo_effector)
        
        self.btn_heater = QPushButton("🔥 Heater ON/OFF")
        self.btn_heater.clicked.connect(self.toggle_heater)
        effector_layout.addWidget(self.btn_heater)
        
        layout.addWidget(effector_group)
        
        return panel
    
    def create_right_panel(self):
        """Create right panel with status and logs"""
        panel = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)
        
        # System status
        status_group = QGroupBox("System Status")
        status_layout = QFormLayout()
        status_group.setLayout(status_layout)
        
        self.lbl_state = QLabel("INITIALIZING")
        self.lbl_state.setStyleSheet("color: #ffaa00; font-weight: bold;")
        status_layout.addRow("State:", self.lbl_state)
        
        self.lbl_motors = QLabel("Disabled")
        status_layout.addRow("Motors:", self.lbl_motors)
        
        self.lbl_heater = QLabel("OFF")
        status_layout.addRow("Heater:", self.lbl_heater)
        
        self.lbl_temp = QLabel("0.0°C")
        status_layout.addRow("Temperature:", self.lbl_temp)
        
        self.lbl_distance = QLabel("---mm")
        status_layout.addRow("ToF Distance:", self.lbl_distance)
        
        self.lbl_hand = QLabel("Not Detected")
        status_layout.addRow("Hand:", self.lbl_hand)
        
        layout.addWidget(status_group)
        
        # Joint positions
        joints_group = QGroupBox("Joint Positions")
        joints_layout = QFormLayout()
        joints_group.setLayout(joints_layout)
        
        self.lbl_j1 = QLabel("0 steps (0.0°)")
        self.lbl_j2 = QLabel("0 steps (0.0°)")
        self.lbl_j3 = QLabel("0 steps (0.0°)")
        
        joints_layout.addRow("Joint 1 (X-Arm):", self.lbl_j1)
        joints_layout.addRow("Joint 2 (Y-Base):", self.lbl_j2)
        joints_layout.addRow("Joint 3 (Z-Elbow):", self.lbl_j3)
        
        layout.addWidget(joints_group)
        
        # Manual joint control
        manual_group = QGroupBox("Manual Joint Control")
        manual_layout = QVBoxLayout()
        manual_group.setLayout(manual_layout)
        
        for i in range(1, 4):
            joint_layout = QHBoxLayout()
            
            label = QLabel(f"J{i}:")
            label.setMinimumWidth(30)
            joint_layout.addWidget(label)
            
            slider = QSlider(Qt.Horizontal)
            slider.setMinimum(-180)
            slider.setMaximum(180)
            slider.setValue(0)
            slider.setTickPosition(QSlider.TicksBelow)
            slider.setTickInterval(45)
            slider.valueChanged.connect(lambda v, j=i: self.manual_joint_move(j, v))
            joint_layout.addWidget(slider)
            
            value_label = QLabel("0°")
            value_label.setMinimumWidth(50)
            joint_layout.addWidget(value_label)
            
            manual_layout.addLayout(joint_layout)
            
            # Store references
            setattr(self, f'slider_j{i}', slider)
            setattr(self, f'slider_j{i}_label', value_label)
        
        layout.addWidget(manual_group)
        
        # Program logs
        logs_group = QGroupBox("Program Logs")
        logs_layout = QVBoxLayout()
        logs_group.setLayout(logs_layout)
        
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setMaximumHeight(200)
        self.logs_text.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas;")
        logs_layout.addWidget(self.logs_text)
        
        logs_buttons = QHBoxLayout()
        
        btn_clear_logs = QPushButton("Clear Logs")
        btn_clear_logs.clicked.connect(self.clear_logs)
        logs_buttons.addWidget(btn_clear_logs)
        
        btn_save_logs = QPushButton("Save Logs")
        btn_save_logs.clicked.connect(self.save_logs)
        logs_buttons.addWidget(btn_save_logs)
        
        logs_layout.addLayout(logs_buttons)
        
        layout.addWidget(logs_group)
        
        return panel
    
    def create_menu_bar(self):
        """Create menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        load_program_action = QAction("Load Program", self)
        load_program_action.triggered.connect(self.load_program)
        file_menu.addAction(load_program_action)
        
        save_program_action = QAction("Save Program", self)
        save_program_action.triggered.connect(self.save_program)
        file_menu.addAction(save_program_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("Tools")
        
        calibrate_action = QAction("Camera Calibration", self)
        calibrate_action.triggered.connect(self.show_calibration_dialog)
        tools_menu.addAction(calibrate_action)
        
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show_settings_dialog)
        tools_menu.addAction(settings_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)
    
    # ═══════════════════════════════════════════════════════════════
    # ENGINE CONTROL
    # ═══════════════════════════════════════════════════════════════
    
    def initialize_engine(self):
        """Initialize the engine in background"""
        self.log("Initializing APEX_PREDATOR Engine...")
        
        # Run initialization in thread
        init_thread = threading.Thread(target=self._init_engine_thread, daemon=True)
        init_thread.start()
    
    def _init_engine_thread(self):
        """Engine initialization thread"""
        if self.engine.initialize():
            self.log("✓ Engine initialized successfully")
            
            # Start video thread
            self.video_thread = VideoThread(self.engine)
            self.video_thread.change_pixmap_signal.connect(self.update_video_frame)
            self.video_thread.start()
        else:
            self.log("✗ Engine initialization failed")
            QMessageBox.critical(self, "Error", "Failed to initialize APEX_PREDATOR Engine")
    
    @pyqtSlot(np.ndarray)
    def update_video_frame(self, frame):
        """Update video frame display"""
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
            self.video_label.width(), self.video_label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.video_label.setPixmap(scaled_pixmap)
    
    def update_status(self):
        """Update status displays"""
        # State
        state_text = self.engine.state.name
        state_colors = {
            "IDLE": "#808080",
            "READY": "#00ff00",
            "AUTO_MODE": "#00aaff",
            "MANUAL_MODE": "#ffaa00",
            "TEACHING_MODE": "#ff00ff",
            "EMERGENCY_STOP": "#ff0000",
            "ERROR": "#ff0000"
        }
        self.lbl_state.setText(state_text)
        self.lbl_state.setStyleSheet(f"color: {state_colors.get(state_text, '#ffffff')}; font-weight: bold;")
        
        # Hardware feedback
        fb = self.engine.hardware_feedback
        
        if fb:
            # Motors
            motors_on = fb.get('motors_enabled', False)
            self.lbl_motors.setText("ENABLED" if motors_on else "DISABLED")
            self.lbl_motors.setStyleSheet(f"color: {'#00ff00' if motors_on else '#ff0000'};")
            
            # Heater
            heater_on = fb.get('heater_enabled', False)
            self.lbl_heater.setText("ON" if heater_on else "OFF")
            self.lbl_heater.setStyleSheet(f"color: {'#ff0000' if heater_on else '#808080'};")
            
            # Temperature
            temp = fb.get('temp', 0)
            self.lbl_temp.setText(f"{temp:.1f}°C")
            if temp > 300:
                self.lbl_temp.setStyleSheet("color: #ff0000; font-weight: bold;")
            elif temp > 200:
                self.lbl_temp.setStyleSheet("color: #ffaa00;")
            else:
                self.lbl_temp.setStyleSheet("color: #00ff00;")
            
            # Distance
            dist = fb.get('distance', 0)
            self.lbl_distance.setText(f"{dist}mm")
            if dist < 150:
                self.lbl_distance.setStyleSheet("color: #ff0000; font-weight: bold;")
            else:
                self.lbl_distance.setStyleSheet("color: #00ff00;")
            
            # Joint positions
            self.lbl_j1.setText(f"{fb.get('j1', 0)} steps")
            self.lbl_j2.setText(f"{fb.get('j2', 0)} steps")
            self.lbl_j3.setText(f"{fb.get('j3', 0)} steps")
            self.lbl_j4.setText(f"{fb.get('j4', 0)} steps")
        
        # Hand detection
        if self.engine.hand_detected:
            dist = self.engine.hand_distance
            self.lbl_hand.setText(f"DETECTED ({dist:.0f}mm)")
            if dist < 200:
                self.lbl_hand.setStyleSheet("color: #ff0000; font-weight: bold;")
            else:
                self.lbl_hand.setStyleSheet("color: #00ff00;")
        else:
            self.lbl_hand.setText("Not Detected")
            self.lbl_hand.setStyleSheet("color: #808080;")
    
    # ═══════════════════════════════════════════════════════════════
    # CONTROL CALLBACKS
    # ═══════════════════════════════════════════════════════════════
    
    def emergency_stop(self):
        """Trigger emergency stop"""
        self.engine.trigger_emergency_stop()
        self.log("🛑 EMERGENCY STOP ACTIVATED")
        QMessageBox.warning(self, "Emergency Stop", "Emergency stop has been activated.\nPress RESET to continue.")
    
    def toggle_auto_mode(self):
        """Toggle auto mode"""
        self.engine.toggle_auto_mode()
        self.log(f"Mode changed to: {self.engine.state.name}")
    
    def set_manual_mode(self):
        """Set manual mode"""
        if self.engine.state != SystemState.MANUAL_MODE:
            self.engine.state = SystemState.MANUAL_MODE
            self.engine.send_command("MODE:MANUAL")
            self.log("Switched to MANUAL mode")
    
    def toggle_teaching_mode(self):
        """Toggle teaching mode"""
        self.engine.toggle_teaching_mode()
        self.log(f"Teaching mode: {'STARTED' if self.engine.state == SystemState.TEACHING_MODE else 'STOPPED'}")
    
    def home_robot(self):
        """Home a single joint (legacy - use home_all_joints instead)"""
        self.log("Warning: Use HOME ALL JOINTS button to home all axes simultaneously")
        self.home_all_joints()
    
    def home_all_joints(self):
        """Home all joints using autonomous double-tap homing"""
        self.log("🔄 Initiating autonomous homing (double-tap protocol)...")
        if self.engine.send_home_command():
            self.log("✓ All joints homed successfully")
            # Reset sliders to 0
            self.slider_j1.setValue(0)
            self.slider_j2.setValue(0)
            self.slider_j3.setValue(0)
        else:
            self.log("✗ Homing failed or timed out")
    
    def enable_motors(self):
        """Enable motors"""
        if self.engine.enable_motors():
            self.log("Motors enabled")
        else:
            self.log("Failed to enable motors")
    
    def disable_motors(self):
        """Disable motors"""
        if self.engine.disable_motors():
            self.log("Motors disabled")
        else:
            self.log("Failed to disable motors")
    
    def toggle_heater(self):
        """Toggle heater"""
        if self.engine.hardware_feedback.get('heater_enabled', False):
            if self.engine.disable_heater():
                self.log("Heater turned OFF")
            else:
                self.log("Failed to turn off heater")
        else:
            if self.engine.enable_heater():
                self.log("Heater turned ON")
            else:
                self.log("Failed to turn on heater")
    
    def change_end_effector(self, index):
        """Change end effector type"""
        effector_map = {
            0: EndEffectorType.NONE,
            1: EndEffectorType.SOLDERING_IRON,
            2: EndEffectorType.GRIPPER,
            3: EndEffectorType.PEN,
            4: EndEffectorType.CUSTOM
        }
        self.engine.set_end_effector(effector_map[index])
        self.log(f"End effector changed to: {effector_map[index].name}")
    
    def test_motor(self, joint):
        """Test individual motor movement"""
        # Enable motors first
        self.engine.enable_motors()
        time.sleep(0.2)
        
        # Test each joint at +45, -45, and 0 degrees
        test_positions = [45, -45, 0]
        
        for angle in test_positions:
            self.log(f"Testing Joint {joint}: Moving to {angle}°")
            # Build a move command - for single joint test, move that joint and keep others at 0
            self.engine.send_move_command(angle if joint == 1 else 0, 
                                         angle if joint == 2 else 0,
                                         angle if joint == 3 else 0)
            time.sleep(1)
    
    def manual_joint_move(self, joint, value):
        """Manual joint movement via sliders"""
        label = getattr(self, f'slider_j{joint}_label')
        label.setText(f"{value}°")
        
        # Get current slider values for all joints
        x_angle = self.slider_j1.value()
        y_angle = self.slider_j2.value()
        z_angle = self.slider_j3.value()
        
        # Send move command with all three joint angles
        if not self.engine.send_move_command(x_angle, y_angle, z_angle):
            self.log(f"Move command rejected (outside safe limits)")
    
    # ═══════════════════════════════════════════════════════════════
    # UTILITY FUNCTIONS
    # ═══════════════════════════════════════════════════════════════
    
    def log(self, message):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        self.logs_text.append(log_message)
        
        # Auto scroll to bottom
        scrollbar = self.logs_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear_logs(self):
        """Clear log window"""
        self.logs_text.clear()
        self.log("Logs cleared")
    
    def save_logs(self):
        """Save logs to file"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Logs", "", "Text Files (*.txt);;All Files (*)"
        )
        if filename:
            with open(filename, 'w') as f:
                f.write(self.logs_text.toPlainText())
            self.log(f"Logs saved to: {filename}")
    
    def load_program(self):
        """Load teaching program"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Program", "", "JSON Files (*.json);;All Files (*)"
        )
        if filename:
            # Load program logic
            self.log(f"Loading program: {filename}")
            QMessageBox.information(self, "Load Program", "Program loading feature coming soon!")
    
    def save_program(self):
        """Save teaching program"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Program", "", "JSON Files (*.json);;All Files (*)"
        )
        if filename:
            # Save program logic
            self.log(f"Saving program: {filename}")
            QMessageBox.information(self, "Save Program", "Program saving feature coming soon!")
    
    def show_calibration_dialog(self):
        """Show camera calibration dialog"""
        QMessageBox.information(self, "Camera Calibration", "Camera calibration wizard coming soon!")
    
    def show_settings_dialog(self):
        """Show settings dialog"""
        QMessageBox.information(self, "Settings", "Settings dialog coming soon!")
    
    def show_about_dialog(self):
        """Show about dialog"""
        about_text = """
        <h2>APEX PREDATOR Control Center</h2>
        <p><b>Version:</b> 2.0.0 (Master/Slave Handshake Protocol)</p>
        <p><b>Description:</b> Industrial Robotics Control with Double-Tap Autonomous Homing</p>
        <p><b>Features:</b></p>
        <ul>
            <li>Blocking handshake protocol for zero-fail communication</li>
            <li>Autonomous double-tap homing sequence</li>
            <li>Kinematic safety envelopes (soft limits)</li>
            <li>Real-time computer vision</li>
            <li>Hand tracking and safety monitoring</li>
            <li>Manual control override</li>
        </ul>
        <p><b>Hardware:</b> Arduino Mega 2560 + RAMPS 1.4 + 3x NEMA17 RMCS-1010 (5.6kg-cm)</p>
        <p><b>Drivers:</b> DRV8825 @ 1/8 Microstepping, Vref=0.73V</p>
        <p><b>Gearboxes:</b> Base 1:1, Shoulder 20:1, Elbow 20:1</p>
        """
        QMessageBox.about(self, "About APEX PREDATOR", about_text)
    
    def get_stylesheet(self):
        """Get application stylesheet"""
        return """
        QMainWindow {
            background-color: #2b2b2b;
        }
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QGroupBox {
            border: 2px solid #3d3d3d;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QPushButton {
            background-color: #0078d7;
            color: white;
            border: none;
            padding: 8px;
            border-radius: 4px;
            font-size: 13px;
        }
        QPushButton:hover {
            background-color: #1084d8;
        }
        QPushButton:pressed {
            background-color: #006cbd;
        }
        QPushButton:disabled {
            background-color: #3d3d3d;
            color: #808080;
        }
        QComboBox {
            background-color: #3d3d3d;
            border: 1px solid #5d5d5d;
            border-radius: 3px;
            padding: 5px;
        }
        QSlider::groove:horizontal {
            border: 1px solid #999999;
            height: 8px;
            background: #3d3d3d;
            margin: 2px 0;
            border-radius: 4px;
        }
        QSlider::handle:horizontal {
            background: #0078d7;
            border: 1px solid #5c5c5c;
            width: 18px;
            margin: -5px 0;
            border-radius: 9px;
        }
        QLabel {
            color: #ffffff;
        }
        QTextEdit {
            background-color: #1e1e1e;
            color: #00ff00;
            border: 1px solid #3d3d3d;
            border-radius: 3px;
            font-family: Consolas, monospace;
        }
        QMenuBar {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QMenuBar::item:selected {
            background-color: #3d3d3d;
        }
        QMenu {
            background-color: #2b2b2b;
            color: #ffffff;
            border: 1px solid #3d3d3d;
        }
        QMenu::item:selected {
            background-color: #0078d7;
        }
        """
    
    def closeEvent(self, event):
        """Handle window close event"""
        reply = QMessageBox.question(
            self, "Quit",
            "Are you sure you want to quit?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.video_thread:
                self.video_thread.stop()
            self.engine.shutdown()
            event.accept()
        else:
            event.ignore()

# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = ApexPredatorGUI()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
