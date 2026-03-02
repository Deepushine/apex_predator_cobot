"""
═══════════════════════════════════════════════════════════════════
                APEX_PREDATOR GUI Control Center v2.1
═══════════════════════════════════════════════════════════════════

FIX LOG v2.1:
  BUG 1: self.lbl_j4 referenced in update_status() but never created
         FIX: Added lbl_j4 to create_right_panel()

  BUG 2: btn_home AND btn_home_all both at grid(2,0) — btn_home invisible
         FIX: btn_home removed (home_all_joints covers the same function)
              btn_home_all moved to grid(2,0), btn_teach at grid(2,1)

  BUG 3: home_all_joints() blocked Qt main thread for 30s → GUI frozen
         FIX: Runs in QThread worker, GUI stays responsive

  BUG 4: set_manual_mode() called engine.send_command() → AttributeError
         FIX: engine.send_command() now exists (added to engine v2.1)

  BUG 5: test_motor() blocked main thread (time.sleep in Qt slot)
         FIX: Runs in QThread worker

  BUG 6: manual_joint_move() sent command on EVERY slider tick → serial flood
         FIX: QTimer debounce (200ms) — only sends after slider stops moving

  BUG 7: update_status() read hardware_feedback but firmware sends nothing
         FIX: Shows real data engine tracks (state, hand, ESP32-CAM)
              hardware_feedback section now shows graceful "N/A" if empty

  BUG 8: VideoThread didn't set CAP_PROP_BUFFERSIZE for ESP32-CAM
         FIX: BufferSize=1 set in engine init_camera() (already done in engine)
═══════════════════════════════════════════════════════════════════
"""

import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import time
from datetime import datetime
import threading

from apex_predator_engine import ApexPredatorEngine, SystemState, EndEffectorType

# ═══════════════════════════════════════════════════════════════
# VIDEO THREAD
# ═══════════════════════════════════════════════════════════════

class VideoThread(QThread):
    frame_signal = pyqtSignal(np.ndarray)

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._run = True

    def run(self):
        while self._run:
            if self.engine.camera is not None:
                ret, frame = self.engine.camera.read()
                if ret:
                    frame = self.engine.process_frame(frame)
                    self.engine.add_status_overlay(frame)
                    self.frame_signal.emit(frame)
            self.msleep(50)  # 20fps

    def stop(self):
        self._run = False
        self.wait()

# ═══════════════════════════════════════════════════════════════
# WORKER THREAD — for blocking engine calls (HOME, TEST, etc.)
# Prevents Qt main thread from freezing
# ═══════════════════════════════════════════════════════════════

class WorkerThread(QThread):
    done_signal = pyqtSignal(bool, str)

    def __init__(self, fn, label=""):
        super().__init__()
        self.fn    = fn
        self.label = label

    def run(self):
        try:
            result = self.fn()
            self.done_signal.emit(bool(result), self.label)
        except Exception as e:
            self.done_signal.emit(False, f"{self.label}: {e}")

# ═══════════════════════════════════════════════════════════════
# MAIN GUI
# ═══════════════════════════════════════════════════════════════

class ApexPredatorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.engine       = ApexPredatorEngine()
        self.video_thread = None
        self._workers     = []  # keep references so threads aren't GC'd

        # FIX BUG 6: slider debounce timer — sends command 200ms after last move
        self._slider_timer = QTimer()
        self._slider_timer.setSingleShot(True)
        self._slider_timer.timeout.connect(self._send_slider_move)

        self.setWindowTitle("APEX PREDATOR Control Center v2.1")
        self.setGeometry(100, 100, 1600, 900)
        self.setStyleSheet(self._stylesheet())

        self.init_ui()

        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self.update_status)
        self._status_timer.start(100)

        QTimer.singleShot(500, self._init_engine)

    # ── UI CONSTRUCTION ──────────────────────────────────────────

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout()
        central.setLayout(layout)
        layout.addWidget(self._left_panel(),  stretch=2)
        layout.addWidget(self._right_panel(), stretch=1)
        self._menu_bar()
        self.statusBar().showMessage("Initializing...")

    def _left_panel(self):
        panel  = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)

        # Video
        vg = QGroupBox("Live Camera Feed (ESP32-CAM / USB fallback)")
        vl = QVBoxLayout(); vg.setLayout(vl)
        self.video_label = QLabel("Initializing Camera...")
        self.video_label.setMinimumSize(960, 540)
        self.video_label.setStyleSheet("background:#1e1e1e; border:2px solid #3d3d3d;")
        self.video_label.setAlignment(Qt.AlignCenter)
        vl.addWidget(self.video_label)
        layout.addWidget(vg)

        # Controls
        cg = QGroupBox("System Controls")
        cl = QGridLayout(); cg.setLayout(cl)

        # E-Stop
        self.btn_estop = QPushButton("🛑 EMERGENCY STOP")
        self.btn_estop.setMinimumHeight(60)
        self.btn_estop.setStyleSheet("""
            QPushButton { background:#cc0000; color:white; font-size:18px;
                          font-weight:bold; border-radius:5px; }
            QPushButton:hover  { background:#ff0000; }
            QPushButton:pressed{ background:#990000; }
        """)
        self.btn_estop.clicked.connect(self.emergency_stop)
        cl.addWidget(self.btn_estop, 0, 0, 1, 2)

        self.btn_auto   = QPushButton("🤖 Auto Mode")
        self.btn_manual = QPushButton("👤 Manual Mode")
        self.btn_auto  .clicked.connect(self.toggle_auto_mode)
        self.btn_manual.clicked.connect(self.set_manual_mode)
        cl.addWidget(self.btn_auto,   1, 0)
        cl.addWidget(self.btn_manual, 1, 1)

        # FIX BUG 2: btn_home removed (was at grid(2,0) colliding with btn_home_all)
        #             btn_home_all at (2,0), btn_teach at (2,1) — no overlap
        self.btn_home_all = QPushButton("🏠 HOME ALL JOINTS")
        self.btn_home_all.setMinimumHeight(40)
        self.btn_home_all.setStyleSheet("""
            QPushButton { background:#4CAF50; color:white; font-weight:bold;
                          border-radius:4px; }
            QPushButton:hover  { background:#45a049; }
            QPushButton:disabled{ background:#3d3d3d; color:#666; }
        """)
        self.btn_home_all.clicked.connect(self.home_all_joints)
        cl.addWidget(self.btn_home_all, 2, 0)

        self.btn_teach = QPushButton("📚 Teaching Mode")
        self.btn_teach.clicked.connect(self.toggle_teaching_mode)
        cl.addWidget(self.btn_teach, 2, 1)

        self.btn_en  = QPushButton("⚡ Enable Motors")
        self.btn_dis = QPushButton("🔌 Disable Motors")
        self.btn_en .clicked.connect(self.enable_motors)
        self.btn_dis.clicked.connect(self.disable_motors)
        cl.addWidget(self.btn_en,  3, 0)
        cl.addWidget(self.btn_dis, 3, 1)

        # ATC controls
        self.btn_lock   = QPushButton("🔒 LOCK ATC")
        self.btn_unlock = QPushButton("🔓 UNLOCK ATC")
        self.btn_lock  .clicked.connect(self.atc_lock)
        self.btn_unlock.clicked.connect(self.atc_unlock)
        cl.addWidget(self.btn_lock,   4, 0)
        cl.addWidget(self.btn_unlock, 4, 1)

        self.btn_tj1 = QPushButton("Test J1 (X)")
        self.btn_tj2 = QPushButton("Test J2 (Y)")
        self.btn_tj3 = QPushButton("Test J3 (Z)")
        self.btn_tj1.clicked.connect(lambda: self._test_motor(1))
        self.btn_tj2.clicked.connect(lambda: self._test_motor(2))
        self.btn_tj3.clicked.connect(lambda: self._test_motor(3))
        cl.addWidget(self.btn_tj1, 5, 0)
        cl.addWidget(self.btn_tj2, 5, 1)
        cl.addWidget(self.btn_tj3, 6, 0)

        layout.addWidget(cg)

        # End effector
        eg = QGroupBox("End Effector")
        el = QHBoxLayout(); eg.setLayout(el)
        self.combo_ee = QComboBox()
        self.combo_ee.addItems(["None", "Soldering Iron", "Gripper", "Pen", "Custom"])
        self.combo_ee.currentIndexChanged.connect(self.change_end_effector)
        self.btn_heater = QPushButton("🔥 Heater ON/OFF")
        self.btn_heater.clicked.connect(self.toggle_heater)
        el.addWidget(QLabel("Type:"))
        el.addWidget(self.combo_ee)
        el.addWidget(self.btn_heater)
        layout.addWidget(eg)

        return panel

    def _right_panel(self):
        panel  = QWidget()
        layout = QVBoxLayout()
        panel.setLayout(layout)

        # Status
        sg = QGroupBox("System Status")
        sl = QFormLayout(); sg.setLayout(sl)
        self.lbl_state    = QLabel("INITIALIZING")
        self.lbl_state.setStyleSheet("color:#ffaa00; font-weight:bold;")
        self.lbl_motors   = QLabel("Disabled")
        self.lbl_heater   = QLabel("OFF")
        self.lbl_temp     = QLabel("N/A")
        self.lbl_distance = QLabel("N/A")
        self.lbl_hand     = QLabel("Not Detected")
        self.lbl_hardware = QLabel("Waiting...")
        sl.addRow("State:",      self.lbl_state)
        sl.addRow("Motors:",     self.lbl_motors)
        sl.addRow("Heater:",     self.lbl_heater)
        sl.addRow("Temp:",       self.lbl_temp)
        sl.addRow("ToF Dist:",   self.lbl_distance)
        sl.addRow("Hand:",       self.lbl_hand)
        sl.addRow("Hardware:",   self.lbl_hardware)
        layout.addWidget(sg)

        # Joint positions
        jg = QGroupBox("Joint Positions")
        jl = QFormLayout(); jg.setLayout(jl)
        self.lbl_j1 = QLabel("0.0°")
        self.lbl_j2 = QLabel("0.0°")
        self.lbl_j3 = QLabel("0.0°")
        # FIX BUG 1: lbl_j4 created here — was referenced in update_status but never created
        self.lbl_j4 = QLabel("0.0°")
        jl.addRow("J1 (X Base):",     self.lbl_j1)
        jl.addRow("J2 (Y Shoulder):", self.lbl_j2)
        jl.addRow("J3 (Z Elbow):",    self.lbl_j3)
        jl.addRow("J4 (reserved):",   self.lbl_j4)
        layout.addWidget(jg)

        # Manual sliders
        mg = QGroupBox("Manual Joint Control")
        ml = QVBoxLayout(); mg.setLayout(ml)
        limits = [(-180, 180), (-30, 90), (-90, 90)]
        for i, (mn, mx) in enumerate(limits, 1):
            row = QHBoxLayout()
            lbl = QLabel(f"J{i}:")
            lbl.setMinimumWidth(25)
            s = QSlider(Qt.Horizontal)
            s.setMinimum(mn); s.setMaximum(mx); s.setValue(0)
            s.setTickPosition(QSlider.TicksBelow)
            s.setTickInterval(30)
            val = QLabel("0°"); val.setMinimumWidth(45)
            # FIX BUG 6: valueChanged starts debounce timer instead of sending immediately
            s.valueChanged.connect(lambda v, vi=i, vl=val: self._on_slider_changed(vi, v, vl))
            row.addWidget(lbl); row.addWidget(s); row.addWidget(val)
            ml.addLayout(row)
            setattr(self, f'slider_j{i}',       s)
            setattr(self, f'slider_j{i}_label', val)
        layout.addWidget(mg)

        # Logs
        lg = QGroupBox("Program Logs")
        ll = QVBoxLayout(); lg.setLayout(ll)
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setMaximumHeight(200)
        self.logs_text.setStyleSheet("background:#1e1e1e; color:#00ff00; font-family:Consolas;")
        ll.addWidget(self.logs_text)
        btns = QHBoxLayout()
        b_clear = QPushButton("Clear"); b_clear.clicked.connect(self.clear_logs)
        b_save  = QPushButton("Save");  b_save .clicked.connect(self.save_logs)
        btns.addWidget(b_clear); btns.addWidget(b_save)
        ll.addLayout(btns)
        layout.addWidget(lg)

        return panel

    def _menu_bar(self):
        mb = self.menuBar()
        fm = mb.addMenu("File")
        for name, fn in [("Load Program", self.load_program),
                         ("Save Program", self.save_program)]:
            a = QAction(name, self); a.triggered.connect(fn); fm.addAction(a)
        fm.addSeparator()
        ex = QAction("Exit", self); ex.triggered.connect(self.close); fm.addAction(ex)

        tm = mb.addMenu("Tools")
        for name, fn in [("Camera Calibration", self._calib_dlg),
                         ("Settings", self._settings_dlg)]:
            a = QAction(name, self); a.triggered.connect(fn); tm.addAction(a)

        hm = mb.addMenu("Help")
        ab = QAction("About", self); ab.triggered.connect(self._about_dlg); hm.addAction(ab)

    # ── ENGINE INIT ──────────────────────────────────────────────

    def _init_engine(self):
        self.log("Initializing APEX_PREDATOR Engine...")

        def _run():
            ok = self.engine.initialize()
            if ok:
                self.log("✓ Engine initialized")
                self.video_thread = VideoThread(self.engine)
                self.video_thread.frame_signal.connect(self._update_frame)
                self.video_thread.start()
            else:
                self.log("✗ Engine init failed")

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    @pyqtSlot(np.ndarray)
    def _update_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qi = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        px = QPixmap.fromImage(qi).scaled(
            self.video_label.width(), self.video_label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.video_label.setPixmap(px)

    # ── STATUS UPDATE ────────────────────────────────────────────

    def update_status(self):
        # State label + colour
        state = self.engine.state.name
        colours = {
            "IDLE": "#808080", "READY": "#00ff00", "AUTO_MODE": "#00aaff",
            "MANUAL_MODE": "#ffaa00", "TEACHING_MODE": "#ff00ff",
            "EMERGENCY_STOP": "#ff0000", "ERROR": "#ff0000"
        }
        self.lbl_state.setText(state)
        self.lbl_state.setStyleSheet(
            f"color:{colours.get(state,'#fff')}; font-weight:bold;")

        # Hardware ready
        ready = self.engine.hardware_ready
        self.lbl_hardware.setText("READY ✓" if ready else "Waiting for APEX_READY...")
        self.lbl_hardware.setStyleSheet(
            "color:#00ff00;" if ready else "color:#ffaa00;")

        # FIX BUG 7: hardware_feedback is usually empty (firmware doesn't send FB:)
        # Show graceful N/A instead of crashing, use real engine attributes instead
        fb = self.engine.hardware_feedback

        motors_on = fb.get('motors_enabled', None)
        self.lbl_motors.setText("ENABLED" if motors_on else
                                "DISABLED" if motors_on is False else "Unknown")
        self.lbl_motors.setStyleSheet(
            "color:#00ff00;" if motors_on else "color:#ff6666;")

        heater_on = fb.get('heater_enabled', False)
        self.lbl_heater.setText("ON" if heater_on else "OFF")
        self.lbl_heater.setStyleSheet("color:#ff4400;" if heater_on else "color:#808080;")

        temp = fb.get('temp', None)
        self.lbl_temp.setText(f"{temp:.1f}°C" if temp is not None else "N/A")

        dist = fb.get('distance', None)
        self.lbl_distance.setText(f"{dist}mm" if dist is not None else "N/A")
        if dist is not None:
            self.lbl_distance.setStyleSheet(
                "color:#ff0000; font-weight:bold;" if dist < 150 else "color:#00ff00;")

        # FIX BUG 1: lbl_j4 now exists — safe to set
        for i, lbl in enumerate([self.lbl_j1, self.lbl_j2,
                                  self.lbl_j3, self.lbl_j4], 1):
            val = fb.get(f'j{i}', None)
            lbl.setText(f"{val}" if val is not None else "N/A")

        # Hand detection
        if self.engine.hand_detected:
            d = self.engine.hand_distance
            self.lbl_hand.setText(f"DETECTED ({d:.0f}mm)")
            self.lbl_hand.setStyleSheet(
                "color:#ff0000; font-weight:bold;" if d < 200 else "color:#00ff00;")
        else:
            self.lbl_hand.setText("Not Detected")
            self.lbl_hand.setStyleSheet("color:#808080;")

        self.statusBar().showMessage(
            f"State: {state}  |  "
            f"Hand: {'Yes' if self.engine.hand_detected else 'No'}  |  "
            f"Objects: {len(self.engine.detected_objects)}"
        )

    # ── SLIDER DEBOUNCE ──────────────────────────────────────────

    def _on_slider_changed(self, joint, value, value_label):
        """FIX BUG 6: don't send immediately — debounce 200ms."""
        value_label.setText(f"{value}°")
        self._slider_timer.start(200)  # restarts timer on each change

    def _send_slider_move(self):
        """Called 200ms after slider stops moving."""
        x = self.slider_j1.value()
        y = self.slider_j2.value()
        z = self.slider_j3.value()
        # Run in worker so GUI doesn't freeze while awaiting OK
        def _move():
            ok = self.engine.send_move_command(x, y, z)
            if not ok:
                self.log(f"Move rejected (out of limits?)")
            return ok
        w = WorkerThread(_move, "slider_move")
        w.done_signal.connect(lambda ok, msg: None)  # silent on success
        self._workers.append(w)
        w.start()

    # ── CONTROL SLOTS ────────────────────────────────────────────

    def emergency_stop(self):
        self.engine.trigger_emergency_stop()
        self.log("🛑 EMERGENCY STOP")
        QMessageBox.warning(self, "Emergency Stop",
                            "Emergency stop activated.\nRe-enable motors to continue.")

    def toggle_auto_mode(self):
        self.engine.toggle_auto_mode()
        self.log(f"Mode: {self.engine.state.name}")

    def set_manual_mode(self):
        if self.engine.state != SystemState.MANUAL_MODE:
            self.engine.state = SystemState.MANUAL_MODE
            # FIX BUG 4: engine.send_command() now exists (added in engine v2.1)
            self.engine.send_command("DIS")   # safe: just disables auto motion
            self.log("Manual mode")

    def toggle_teaching_mode(self):
        self.engine.toggle_teaching_mode()
        self.log(f"Teaching: {'STARTED' if self.engine.state == SystemState.TEACHING_MODE else 'STOPPED'}")

    def home_all_joints(self):
        """FIX BUG 3: runs in WorkerThread — Qt main thread never blocks."""
        self.btn_home_all.setEnabled(False)
        self.log("🔄 Homing all joints (double-tap, ~30s)...")

        def _home():
            return self.engine.send_home_command()

        w = WorkerThread(_home, "HOME")
        w.done_signal.connect(self._on_home_done)
        self._workers.append(w)
        w.start()

    def _on_home_done(self, ok, label):
        self.btn_home_all.setEnabled(True)
        if ok:
            self.log("✓ All joints homed")
            self.slider_j1.setValue(0)
            self.slider_j2.setValue(0)
            self.slider_j3.setValue(0)
        else:
            self.log("✗ Homing failed or timed out")

    def enable_motors(self):
        def _en():
            return self.engine.enable_motors()
        w = WorkerThread(_en, "EN")
        w.done_signal.connect(lambda ok, _: self.log("Motors enabled" if ok else "Enable failed"))
        self._workers.append(w); w.start()

    def disable_motors(self):
        def _dis():
            return self.engine.disable_motors()
        w = WorkerThread(_dis, "DIS")
        w.done_signal.connect(lambda ok, _: self.log("Motors disabled" if ok else "Disable failed"))
        self._workers.append(w); w.start()

    def atc_lock(self):
        def _lock():
            return self.engine.atc_lock()
        w = WorkerThread(_lock, "LOCK")
        w.done_signal.connect(lambda ok, _: self.log("ATC LOCKED ✓" if ok else "ATC lock failed"))
        self._workers.append(w); w.start()

    def atc_unlock(self):
        def _unlock():
            return self.engine.atc_unlock()
        w = WorkerThread(_unlock, "UNLOCK")
        w.done_signal.connect(lambda ok, _: self.log("ATC UNLOCKED ✓" if ok else "ATC unlock failed"))
        self._workers.append(w); w.start()

    def toggle_heater(self):
        on = self.engine.hardware_feedback.get('heater_enabled', False)
        def _tog():
            return self.engine.disable_heater() if on else self.engine.enable_heater()
        w = WorkerThread(_tog, "HEATER")
        w.done_signal.connect(lambda ok, _: self.log(
            ("Heater OFF" if on else "Heater ON") if ok else "Heater cmd failed"))
        self._workers.append(w); w.start()

    def change_end_effector(self, index):
        em = {0: EndEffectorType.NONE,
              1: EndEffectorType.SOLDERING_IRON,
              2: EndEffectorType.GRIPPER,
              3: EndEffectorType.PEN,
              4: EndEffectorType.CUSTOM}
        self.engine.set_end_effector(em[index])
        self.log(f"End effector: {em[index].name}")

    def _test_motor(self, joint):
        """FIX BUG 5: runs in WorkerThread — no main thread blocking."""
        self.log(f"Testing Joint {joint}...")

        def _test():
            self.engine.enable_motors()
            positions = [45.0, -45.0, 0.0]
            for ang in positions:
                args = [0.0, 0.0, 0.0]
                args[joint - 1] = ang
                ok = self.engine.send_move_command(*args)
                if not ok:
                    return False
                time.sleep(0.5)
            return True

        w = WorkerThread(_test, f"TestJ{joint}")
        w.done_signal.connect(lambda ok, _: self.log(
            f"✓ J{joint} test complete" if ok else f"✗ J{joint} test failed"))
        self._workers.append(w); w.start()

    # ── UTILITIES ────────────────────────────────────────────────

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs_text.append(f"[{ts}] {msg}")
        sb = self.logs_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear_logs(self):
        self.logs_text.clear()
        self.log("Logs cleared")

    def save_logs(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Save Logs", "", "Text Files (*.txt)")
        if fn:
            with open(fn, 'w') as f:
                f.write(self.logs_text.toPlainText())
            self.log(f"Logs saved: {fn}")

    def load_program(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Load Program", "", "JSON Files (*.json)")
        if fn:
            self.log(f"Load program: {fn} (coming soon)")

    def save_program(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Save Program", "", "JSON Files (*.json)")
        if fn:
            self.log(f"Save program: {fn} (coming soon)")

    def _calib_dlg(self):
        QMessageBox.information(self, "Calibration", "Camera calibration coming soon.")

    def _settings_dlg(self):
        QMessageBox.information(self, "Settings", "Settings dialog coming soon.")

    def _about_dlg(self):
        QMessageBox.about(self, "About APEX PREDATOR", """
<h2>APEX PREDATOR Control Center v2.1</h2>
<p><b>Protocol:</b> Master/Slave Handshake</p>
<p><b>Hardware:</b> Arduino Mega 2560 + RAMPS 1.6 + 3x NEMA17 RMCS-1010 (5.6kg-cm)</p>
<p><b>Drivers:</b> DRV8825 @ 1/8 microstep, Vref=0.73V</p>
<p><b>Switches:</b> MS-114 SPDT (NO wiring)</p>
<p><b>ATC:</b> 4x MG90S servos, 4-point latch</p>
<p><b>Camera:</b> ESP32-CAM (WiFi stream) + USB fallback</p>
<p><b>Gearboxes:</b> X=1:1, Y=20:1, Z=20:1</p>
""")

    def _stylesheet(self):
        return """
        QMainWindow,QWidget { background:#2b2b2b; color:#fff; }
        QGroupBox { border:2px solid #3d3d3d; border-radius:5px;
                    margin-top:10px; padding-top:10px; font-weight:bold; }
        QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 5px; }
        QPushButton { background:#0078d7; color:#fff; border:none; padding:8px;
                      border-radius:4px; font-size:13px; }
        QPushButton:hover   { background:#1084d8; }
        QPushButton:pressed { background:#006cbd; }
        QPushButton:disabled{ background:#3d3d3d; color:#808080; }
        QComboBox { background:#3d3d3d; border:1px solid #5d5d5d;
                    border-radius:3px; padding:5px; }
        QSlider::groove:horizontal { border:1px solid #999; height:8px;
                                     background:#3d3d3d; border-radius:4px; }
        QSlider::handle:horizontal { background:#0078d7; width:18px;
                                     margin:-5px 0; border-radius:9px; }
        QTextEdit { background:#1e1e1e; color:#00ff00; border:1px solid #3d3d3d;
                    font-family:Consolas,monospace; }
        QMenuBar { background:#2b2b2b; color:#fff; }
        QMenuBar::item:selected { background:#3d3d3d; }
        QMenu { background:#2b2b2b; color:#fff; border:1px solid #3d3d3d; }
        QMenu::item:selected { background:#0078d7; }
        """

    def closeEvent(self, event):
        reply = QMessageBox.question(self, "Quit", "Quit APEX PREDATOR?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.video_thread:
                self.video_thread.stop()
            self.engine.shutdown()
            event.accept()
        else:
            event.ignore()


# ── ENTRY POINT ──────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    win = ApexPredatorGUI()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
