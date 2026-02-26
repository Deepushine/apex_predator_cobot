"""
═══════════════════════════════════════════════════════════════════
                APEX_PREDATOR GUI Control Center v2.0
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
                processed_frame = self.engine.process_frame(frame)
                self.engine.add_status_overlay(processed_frame)
                self.change_pixmap_signal.emit(processed_frame)
            self.msleep(30)

    def stop(self):
        self._run_flag = False
        self.wait()

# ═══════════════════════════════════════════════════════════════════
# MAIN GUI CLASS
# ═══════════════════════════════════════════════════════════════════

class ApexPredatorGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.engine = ApexPredatorEngine()
        self.video_thread = None

        self.setWindowTitle("APEX PREDATOR Control Center v2.0")
        self.setGeometry(100, 100, 1600, 900)
        self.setStyleSheet(self.get_stylesheet())

        self.init_ui()

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(100)

        QTimer.singleShot(500, self.initialize_engine)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        left_panel = self.create_left_panel()
        main_layout.addWidget(left_panel, stretch=2)

        right_panel = self.create_right_panel()
        main_layout.addWidget(right_panel, stretch=1)

        self.create_menu_bar()
        self.statusBar().showMessage("Ready")

    def create_left_panel(self):
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

        # System controls
        controls_group = QGroupBox("System Controls")
        controls_layout = QGridLayout()
        controls_group.setLayout(controls_layout)

        # Emergency stop
        self.btn_estop = QPushButton("🛑 EMERGENCY STOP")
        self.btn_estop.setMinimumHeight(60)
        self.btn_estop.setStyleSheet("""
            QPushButton { background-color: #cc0000; color: white; font-size: 18px; font-weight: bold; border-radius: 5px; }
            QPushButton:hover { background-color: #ff0000; }
            QPushButton:pressed { background-color: #990000; }
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

        # FIX: Previously btn_home was created and placed at (2,0),
        # then btn_home_all was ALSO placed at (2,1) — but then btn_home
        # was placed at (2,0) again, overwriting btn_teach.
        # Now btn_teach stays at (2,0) and HOME ALL JOINTS is at (2,1).
        self.btn_home_all = QPushButton("🏠 HOME ALL JOINTS")
        self.btn_home_all.setMinimumHeight(40)
        self.btn_home_all.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #45a049; }
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

        # Motor test buttons
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

        self.lbl_j1 = QLabel("0.0°")
        self.lbl_j2 = QLabel("0.0°")
        self.lbl_j3 = QLabel("0.0°")
        # FIX: lbl_j4 was referenced in update_status() but never created — crash on startup
        self.lbl_j4 = QLabel("N/A")

        joints_layout.addRow("J1 (X-Base):", self.lbl_j1)
        joints_layout.addRow("J2 (Y-Shoulder):", self.lbl_j2)
        joints_layout.addRow("J3 (Z-Elbow):", self.lbl_j3)
        joints_layout.addRow("J4 (spare):", self.lbl_j4)

        layout.addWidget(joints_group)

        # Manual joint control
        manual_group = QGroupBox("Manual Joint Control")
        manual_layout = QVBoxLayout()
        manual_group.setLayout(manual_layout)

        # J2 (Shoulder) has constrained range
        joint_configs = [
            (1, -180, 180),
            (2, -30, 90),
            (3, -90, 90),
        ]
        for i, min_val, max_val in joint_configs:
            joint_layout = QHBoxLayout()

            label = QLabel(f"J{i}:")
            label.setMinimumWidth(30)
            joint_layout.addWidget(label)

            slider = QSlider(Qt.Horizontal)
            slider.setMinimum(min_val)
            slider.setMaximum(max_val)
            slider.setValue(0)
            slider.setTickPosition(QSlider.TicksBelow)
            slider.setTickInterval(45)
            slider.valueChanged.connect(lambda v, j=i: self.manual_joint_move(j, v))
            joint_layout.addWidget(slider)

            value_label = QLabel("0°")
            value_label.setMinimumWidth(50)
            joint_layout.addWidget(value_label)

            manual_layout.addLayout(joint_layout)
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
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        load_action = QAction("Load Program", self)
        load_action.triggered.connect(self.load_program)
        file_menu.addAction(load_action)

        save_action = QAction("Save Program", self)
        save_action.triggered.connect(self.save_program)
        file_menu.addAction(save_action)

        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        tools_menu = menubar.addMenu("Tools")
        calibrate_action = QAction("Camera Calibration", self)
        calibrate_action.triggered.connect(self.show_calibration_dialog)
        tools_menu.addAction(calibrate_action)

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show_settings_dialog)
        tools_menu.addAction(settings_action)

        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    # ═══════════════════════════════════════════════════════════════
    # ENGINE CONTROL
    # ═══════════════════════════════════════════════════════════════

    def initialize_engine(self):
        self.log("Initializing APEX_PREDATOR Engine...")
        init_thread = threading.Thread(target=self._init_engine_thread, daemon=True)
        init_thread.start()

    def _init_engine_thread(self):
        if self.engine.initialize():
            self.log("✓ Engine initialized successfully")
            self.video_thread = VideoThread(self.engine)
            self.video_thread.change_pixmap_signal.connect(self.update_video_frame)
            self.video_thread.start()
        else:
            self.log("✗ Engine initialization failed")

    @pyqtSlot(np.ndarray)
    def update_video_frame(self, frame):
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        qt_image = QImage(rgb_image.data, w, h, ch * w, QImage.Format_RGB888)
        scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
            self.video_label.width(), self.video_label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.video_label.setPixmap(scaled_pixmap)

    def update_status(self):
        state_text = self.engine.state.name
        state_colors = {
            "IDLE": "#808080", "READY": "#00ff00", "AUTO_MODE": "#00aaff",
            "MANUAL_MODE": "#ffaa00", "TEACHING_MODE": "#ff00ff",
            "EMERGENCY_STOP": "#ff0000", "ERROR": "#ff0000"
        }
        self.lbl_state.setText(state_text)
        self.lbl_state.setStyleSheet(f"color: {state_colors.get(state_text, '#ffffff')}; font-weight: bold;")

        fb = self.engine.hardware_feedback
        if fb:
            motors_on = fb.get('motors_enabled', False)
            self.lbl_motors.setText("ENABLED" if motors_on else "DISABLED")
            self.lbl_motors.setStyleSheet(f"color: {'#00ff00' if motors_on else '#ff0000'};")

            heater_on = fb.get('heater_enabled', False)
            self.lbl_heater.setText("ON" if heater_on else "OFF")
            self.lbl_heater.setStyleSheet(f"color: {'#ff0000' if heater_on else '#808080'};")

            temp = fb.get('temp', 0)
            self.lbl_temp.setText(f"{temp:.1f}°C")
            color = "#ff0000" if temp > 300 else ("#ffaa00" if temp > 200 else "#00ff00")
            self.lbl_temp.setStyleSheet(f"color: {color};")

            dist = fb.get('distance', 0)
            self.lbl_distance.setText(f"{dist}mm")
            self.lbl_distance.setStyleSheet(f"color: {'#ff0000' if dist < 150 else '#00ff00'};")

            # FIX: was trying to set lbl_j4 which didn't exist (AttributeError crash)
            # Now all four labels exist and are updated safely
            self.lbl_j1.setText(f"{fb.get('j1', 0)} steps")
            self.lbl_j2.setText(f"{fb.get('j2', 0)} steps")
            self.lbl_j3.setText(f"{fb.get('j3', 0)} steps")
            self.lbl_j4.setText(f"{fb.get('j4', 'N/A')} steps")

        if self.engine.hand_detected:
            dist = self.engine.hand_distance
            self.lbl_hand.setText(f"DETECTED ({dist:.0f}mm)")
            self.lbl_hand.setStyleSheet(f"color: {'#ff0000' if dist < 200 else '#00ff00'}; font-weight: bold;")
        else:
            self.lbl_hand.setText("Not Detected")
            self.lbl_hand.setStyleSheet("color: #808080;")

    # ═══════════════════════════════════════════════════════════════
    # CONTROL CALLBACKS
    # ═══════════════════════════════════════════════════════════════

    def emergency_stop(self):
        self.engine.trigger_emergency_stop()
        self.log("🛑 EMERGENCY STOP ACTIVATED")
        QMessageBox.warning(self, "Emergency Stop", "Emergency stop activated.\nRe-enable motors to continue.")

    def toggle_auto_mode(self):
        self.engine.toggle_auto_mode()
        self.log(f"Mode: {self.engine.state.name}")

    def set_manual_mode(self):
        if self.engine.state != SystemState.MANUAL_MODE:
            self.engine.state = SystemState.MANUAL_MODE
            # FIX: engine.send_command() now exists — previously caused AttributeError
            self.engine.send_command("MODE:MANUAL")
            self.log("Switched to MANUAL mode")

    def toggle_teaching_mode(self):
        self.engine.toggle_teaching_mode()
        self.log(f"Teaching mode: {'STARTED' if self.engine.state == SystemState.TEACHING_MODE else 'STOPPED'}")

    def home_all_joints(self):
        """Home all joints using autonomous double-tap homing. Runs in background thread."""
        self.log("🔄 Initiating autonomous homing (double-tap protocol)...")
        self.btn_home_all.setEnabled(False)
        self.btn_home_all.setText("Homing...")

        def _do_home():
            success = self.engine.send_home_command()
            # GUI updates must be on main thread
            QMetaObject.invokeMethod(self, "_on_home_complete",
                                     Qt.QueuedConnection,
                                     Q_ARG(bool, success))

        threading.Thread(target=_do_home, daemon=True).start()

    @pyqtSlot(bool)
    def _on_home_complete(self, success):
        self.btn_home_all.setEnabled(True)
        self.btn_home_all.setText("🏠 HOME ALL JOINTS")
        if success:
            self.log("✓ All joints homed successfully")
            self.slider_j1.setValue(0)
            self.slider_j2.setValue(0)
            self.slider_j3.setValue(0)
        else:
            self.log("✗ Homing failed or timed out")

    def enable_motors(self):
        if self.engine.enable_motors():
            self.log("✓ Motors enabled")
        else:
            self.log("✗ Failed to enable motors")

    def disable_motors(self):
        if self.engine.disable_motors():
            self.log("✓ Motors disabled")
        else:
            self.log("✗ Failed to disable motors")

    def toggle_heater(self):
        if self.engine.hardware_feedback.get('heater_enabled', False):
            self.engine.disable_heater()
            self.log("Heater OFF")
        else:
            self.engine.enable_heater()
            self.log("Heater ON")

    def change_end_effector(self, index):
        effector_map = {
            0: EndEffectorType.NONE,
            1: EndEffectorType.SOLDERING_IRON,
            2: EndEffectorType.GRIPPER,
            3: EndEffectorType.PEN,
            4: EndEffectorType.CUSTOM
        }
        self.engine.set_end_effector(effector_map[index])
        self.log(f"End effector: {effector_map[index].name}")

    def test_motor(self, joint):
        """Test individual motor — runs in background so GUI doesn't freeze."""
        self.log(f"Testing Joint {joint}...")

        def _do_test():
            self.engine.enable_motors()
            time.sleep(0.2)
            for angle in [45, -45, 0]:
                self.engine.send_move_command(
                    angle if joint == 1 else 0,
                    angle if joint == 2 else 0,
                    angle if joint == 3 else 0
                )

        threading.Thread(target=_do_test, daemon=True).start()

    def manual_joint_move(self, joint, value):
        label = getattr(self, f'slider_j{joint}_label')
        label.setText(f"{value}°")

        x_angle = self.slider_j1.value()
        y_angle = self.slider_j2.value()
        z_angle = self.slider_j3.value()

        if not self.engine.send_move_command(x_angle, y_angle, z_angle):
            self.log(f"Move rejected (outside safe limits)")

    # ═══════════════════════════════════════════════════════════════
    # UTILITY
    # ═══════════════════════════════════════════════════════════════

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs_text.append(f"[{timestamp}] {message}")
        self.logs_text.verticalScrollBar().setValue(
            self.logs_text.verticalScrollBar().maximum()
        )

    def clear_logs(self):
        self.logs_text.clear()
        self.log("Logs cleared")

    def save_logs(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Logs", "", "Text Files (*.txt)")
        if filename:
            with open(filename, 'w') as f:
                f.write(self.logs_text.toPlainText())
            self.log(f"Logs saved: {filename}")

    def load_program(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Load Program", "", "JSON Files (*.json)")
        if filename:
            self.log(f"Loading: {filename}")
            QMessageBox.information(self, "Load Program", "Program loading coming soon!")

    def save_program(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Program", "", "JSON Files (*.json)")
        if filename:
            self.log(f"Saving: {filename}")
            QMessageBox.information(self, "Save Program", "Program saving coming soon!")

    def show_calibration_dialog(self):
        QMessageBox.information(self, "Camera Calibration", "Calibration wizard coming soon!")

    def show_settings_dialog(self):
        QMessageBox.information(self, "Settings", "Settings dialog coming soon!")

    def show_about_dialog(self):
        QMessageBox.about(self, "About APEX PREDATOR", """
        <h2>APEX PREDATOR Control Center v2.0</h2>
        <p>Master/Slave Handshake Protocol</p>
        <p>Arduino Mega 2560 + RAMPS 1.6 + 3x NEMA17 RMCS-1010</p>
        <p>DRV8825 @ 1/8 Microstepping | Vref=0.73V</p>
        <p>Gearboxes: Base 1:1, Shoulder 20:1, Elbow 20:1</p>
        """)

    def get_stylesheet(self):
        return """
        QMainWindow, QWidget { background-color: #2b2b2b; color: #ffffff; }
        QGroupBox { border: 2px solid #3d3d3d; border-radius: 5px; margin-top: 10px; padding-top: 10px; font-weight: bold; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        QPushButton { background-color: #0078d7; color: white; border: none; padding: 8px; border-radius: 4px; font-size: 13px; }
        QPushButton:hover { background-color: #1084d8; }
        QPushButton:pressed { background-color: #006cbd; }
        QPushButton:disabled { background-color: #3d3d3d; color: #808080; }
        QComboBox { background-color: #3d3d3d; border: 1px solid #5d5d5d; border-radius: 3px; padding: 5px; }
        QSlider::groove:horizontal { border: 1px solid #999; height: 8px; background: #3d3d3d; margin: 2px 0; border-radius: 4px; }
        QSlider::handle:horizontal { background: #0078d7; border: 1px solid #5c5c5c; width: 18px; margin: -5px 0; border-radius: 9px; }
        QLabel { color: #ffffff; }
        QTextEdit { background-color: #1e1e1e; color: #00ff00; border: 1px solid #3d3d3d; border-radius: 3px; font-family: Consolas, monospace; }
        QMenuBar { background-color: #2b2b2b; color: #ffffff; }
        QMenuBar::item:selected { background-color: #3d3d3d; }
        QMenu { background-color: #2b2b2b; color: #ffffff; border: 1px solid #3d3d3d; }
        QMenu::item:selected { background-color: #0078d7; }
        """

    def closeEvent(self, event):
        reply = QMessageBox.question(self, "Quit", "Are you sure?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
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
