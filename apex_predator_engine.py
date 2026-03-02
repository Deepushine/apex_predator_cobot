"""
═══════════════════════════════════════════════════════════════════
                APEX_PREDATOR_ENGINE v2.1
═══════════════════════════════════════════════════════════════════

FIX LOG v2.1:
  BUG 1: mediapipe imported twice (lines 24-27)
         FIX: Removed duplicate import block

  BUG 2: send_command() method missing — GUI calls it → AttributeError
         FIX: Added send_command() as alias for send_and_wait()

  BUG 3: enable_motors() sent MOTORS_EN, terminal/demo used EN — mismatch
         FIX: Firmware now accepts both EN and MOTORS_EN (fixed in firmware)
              Engine uses EN for consistency with motor_terminal

  BUG 4: SERIAL_PORT hardcoded as COM12 — ignored config.json COM3
         FIX: init_serial() now reads from config.json first

  BUG 5: Camera opened as cv2.VideoCapture(0) — not ESP32-CAM URL
         FIX: init_camera() reads esp32_stream_url from config.json
              Falls back to USB index if URL fails

  BUG 6: init_serial() used only Config.SERIAL_PORT, ignored config.json
         FIX: merged — reads config.json, falls back to Config.SERIAL_PORT

  BUG 7: check_hardware_ready() always returned True
         FIX: Now reads serial buffer for APEX_READY signal from Arduino

  BUG 8: send_and_wait() timeout from wrong config key
         FIX: reads config['hardware']['arduino']['handshake_timeout']
═══════════════════════════════════════════════════════════════════
"""

import cv2
import numpy as np
import serial
import threading
import time
import json
import logging
from datetime import datetime
from collections import deque
from enum import Enum

# FIX BUG 1: removed duplicate mediapipe import block — only one here
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ── LOGGING ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('apex_predator_engine.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('APEX_ENGINE')

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

class Config:
    """Fallback defaults — real values loaded from config.json"""
    SERIAL_PORT       = 'COM12'
    BAUD_RATE         = 115200
    ESP32_STREAM_URL  = 'http://192.168.1.47/stream'
    CAMERA_WIDTH      = 640
    CAMERA_HEIGHT     = 480
    CAMERA_FPS        = 20
    MIN_HAND_DISTANCE = 200
    MAX_VELOCITY      = 100
    SAFE_ZONE_RADIUS  = 150
    HANDSHAKE_TIMEOUT = 5.0
    HOME_TIMEOUT      = 60.0
    CONFIDENCE_THRESHOLD = 0.7

class SystemState(Enum):
    IDLE           = 0
    INITIALIZING   = 1
    READY          = 2
    AUTO_MODE      = 3
    MANUAL_MODE    = 4
    TEACHING_MODE  = 5
    EMERGENCY_STOP = 6
    ERROR          = 7

class EndEffectorType(Enum):
    NONE          = 0
    SOLDERING_IRON = 1
    GRIPPER       = 2
    PEN           = 3
    CUSTOM        = 4

# ═══════════════════════════════════════════════════════════════
# ENGINE
# ═══════════════════════════════════════════════════════════════

class ApexPredatorEngine:
    def __init__(self):
        logger.info("Initializing APEX_PREDATOR_ENGINE v2.1...")

        self.config         = self.load_config()
        self.state          = SystemState.INITIALIZING
        self.end_effector_type = EndEffectorType.NONE
        self.is_running     = False
        self.emergency_stop = False

        self.serial         = None
        self.serial_lock    = threading.Lock()
        self.hardware_feedback = {}
        self.hardware_ready = False

        self.camera         = None
        self.landmarker     = None
        self.timestamp      = 0
        self.hand_positions = deque(maxlen=30)
        self.detected_objects = []
        self.last_detection_time = 0

        self.current_task   = None
        self.task_active    = False
        self.safety_violations = []
        self.hand_detected  = False
        self.hand_distance  = float('inf')
        self.session_data   = []
        self.recording_session = False

    def load_config(self):
        try:
            with open('config.json', 'r') as f:
                cfg = json.load(f)
                logger.info("config.json loaded ✓")
                return cfg
        except Exception as e:
            logger.warning(f"config.json load failed: {e}. Using defaults.")
            return {}

    # ── INIT ─────────────────────────────────────────────────────

    def initialize(self):
        try:
            logger.info("Starting initialization sequence...")
            if not self.init_serial():
                logger.warning("Serial failed — running in simulation mode")
            if not self.init_camera():
                logger.warning("Camera failed — vision disabled")
            if not self.init_hand_tracking():
                logger.error("Hand tracking failed")
                return False

            # FIX BUG 7: actually wait for APEX_READY signal
            logger.info("Waiting for APEX_READY signal from Arduino...")
            timeout = time.time() + 10
            while time.time() < timeout:
                if self.hardware_ready:
                    break
                if self.serial and self.serial.in_waiting:
                    line = self.serial.readline().decode('utf-8').strip()
                    if line == "APEX_READY":
                        self.hardware_ready = True
                        logger.info("✓ Hardware APEX_READY received")
                        break
                    logger.debug(f"Init RX: {line}")
                time.sleep(0.1)
            else:
                logger.warning("APEX_READY timeout — hardware may not be ready")

            self.state = SystemState.READY
            logger.info("✓ APEX_PREDATOR_ENGINE v2.1 ready")
            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            self.state = SystemState.ERROR
            return False

    def init_serial(self):
        # FIX BUG 4 + BUG 6: read port from config.json first
        port = (self.config
                .get('hardware', {})
                .get('arduino', {})
                .get('serial_port', Config.SERIAL_PORT))
        baud = (self.config
                .get('hardware', {})
                .get('arduino', {})
                .get('baud_rate', Config.BAUD_RATE))
        try:
            self.serial = serial.Serial(port, baud, timeout=1)
            time.sleep(2)
            logger.info(f"✓ Serial on {port} @ {baud}")
            return True
        except Exception as e:
            logger.error(f"Serial error: {e}")
            return False

    def init_camera(self):
        # FIX BUG 5: use ESP32-CAM stream URL from config, not cv2.VideoCapture(0)
        stream_url = (self.config
                      .get('camera', {})
                      .get('esp32_stream_url', Config.ESP32_STREAM_URL))
        fallback_idx = (self.config
                        .get('camera', {})
                        .get('fallback_usb_index', 0))

        # Try ESP32-CAM stream first
        logger.info(f"Trying ESP32-CAM stream: {stream_url}")
        cam = cv2.VideoCapture(stream_url)
        cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # Low latency for WiFi stream
        cam.set(cv2.CAP_PROP_FPS, Config.CAMERA_FPS)

        ret, frame = cam.read()
        if ret:
            self.camera = cam
            logger.info(f"✓ ESP32-CAM stream: {frame.shape[1]}x{frame.shape[0]}")
            return True
        else:
            logger.warning(f"ESP32-CAM stream failed ({stream_url})")
            logger.info(f"Falling back to USB camera index {fallback_idx}")
            cam.release()

        # Fallback to USB
        cam = cv2.VideoCapture(fallback_idx)
        cam.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        ret, frame = cam.read()
        if ret:
            self.camera = cam
            logger.info(f"✓ USB camera index {fallback_idx}: {frame.shape[1]}x{frame.shape[0]}")
            return True

        logger.error("All camera sources failed")
        return False

    def init_hand_tracking(self):
        try:
            base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.VIDEO,
                num_hands=2,
                min_hand_detection_confidence=0.7,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5
            )
            self.landmarker = vision.HandLandmarker.create_from_options(options)
            logger.info("✓ Hand tracking ready")
            return True
        except Exception as e:
            logger.error(f"Hand tracking error: {e}")
            return False

    # ── COMMUNICATION ────────────────────────────────────────────

    def send_and_wait(self, command, timeout=None):
        """
        BLOCKING HANDSHAKE: Send command, wait for OK.
        Python blocks until Arduino confirms with "OK".

        Args:
            command: e.g. "<MOVE X45.0 Y0.0 Z0.0>" or "HOME" or "LOCK"
            timeout: seconds (reads from config if None)

        Returns:
            bool: True = OK received, False = timeout/error
        """
        if timeout is None:
            # FIX BUG 8: correct config path — was reading wrong key
            timeout = (self.config
                       .get('hardware', {})
                       .get('arduino', {})
                       .get('handshake_timeout', Config.HANDSHAKE_TIMEOUT))

        if not self.serial:
            logger.error("Serial not initialized")
            return False

        try:
            with self.serial_lock:
                self.serial.reset_input_buffer()
                self.serial.write(f"{command}\n".encode())
                logger.debug(f"TX: {command}")

                start = time.time()
                while time.time() - start < timeout:
                    if self.serial.in_waiting:
                        line = self.serial.readline().decode('utf-8').strip()
                        logger.debug(f"RX: {line}")
                        if line == "OK":
                            logger.info(f"✓ {command}")
                            return True
                        elif line.startswith("ERR"):
                            logger.error(f"✗ Rejected: {line}")
                            return False
                    time.sleep(0.01)

                logger.error(f"✗ Timeout ({timeout}s): {command}")
                return False

        except Exception as e:
            logger.error(f"Handshake error: {e}")
            return False

    def send_command(self, command, timeout=None):
        """
        FIX BUG 2: send_command() was missing — GUI called it → AttributeError
        Now it's an alias for send_and_wait() for compatibility.
        """
        return self.send_and_wait(command, timeout)

    def send_move_command(self, x_angle, y_angle, z_angle):
        """Send a MOVE command with soft-limit validation."""
        limits = self.config.get('kinematic_limits', {})
        x_min = limits.get('joint_x_base',     {}).get('min_angle', -180)
        x_max = limits.get('joint_x_base',     {}).get('max_angle',  180)
        y_min = limits.get('joint_y_shoulder', {}).get('min_angle',  -30)
        y_max = limits.get('joint_y_shoulder', {}).get('max_angle',   90)
        z_min = limits.get('joint_z_elbow',    {}).get('min_angle',  -90)
        z_max = limits.get('joint_z_elbow',    {}).get('max_angle',   90)

        if not (x_min <= x_angle <= x_max):
            logger.warning(f"X={x_angle}° out of [{x_min},{x_max}]")
            return False
        if not (y_min <= y_angle <= y_max):
            logger.warning(f"Y={y_angle}° out of [{y_min},{y_max}]")
            return False
        if not (z_min <= z_angle <= z_max):
            logger.warning(f"Z={z_angle}° out of [{z_min},{z_max}]")
            return False

        cmd = f"<MOVE X{x_angle:.1f} Y{y_angle:.1f} Z{z_angle:.1f}>"
        return self.send_and_wait(cmd)

    def send_home_command(self):
        home_timeout = (self.config
                        .get('hardware', {})
                        .get('arduino', {})
                        .get('home_timeout', Config.HOME_TIMEOUT))
        logger.info("Initiating homing sequence...")
        return self.send_and_wait("HOME", timeout=home_timeout)

    def enable_motors(self):
        return self.send_and_wait("EN")

    def disable_motors(self):
        return self.send_and_wait("DIS")

    def open_gripper(self):
        return self.send_and_wait("GRIPPER_OPEN")

    def close_gripper(self):
        return self.send_and_wait("GRIPPER_CLOSE")

    def enable_heater(self):
        return self.send_and_wait("HEATER_ON")

    def disable_heater(self):
        return self.send_and_wait("HEATER_OFF")

    def atc_lock(self):
        return self.send_and_wait("LOCK")

    def atc_unlock(self):
        return self.send_and_wait("UNLOCK")

    def check_hardware_ready(self):
        return self.hardware_ready

    # ── VISION ───────────────────────────────────────────────────

    def process_frame(self, frame):
        """Process camera frame for hand tracking and object detection."""
        if self.landmarker is None:
            return frame

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image  = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        self.timestamp += 1
        results = self.landmarker.detect_for_video(mp_image, self.timestamp)

        self.hand_detected = False

        if results.hand_landmarks:
            self.hand_detected = True
            for hand_landmarks in results.hand_landmarks:
                px = int(hand_landmarks[9].x * frame.shape[1])
                py = int(hand_landmarks[9].y * frame.shape[0])
                self.hand_positions.append((px, py, time.time()))
                self.hand_distance = self.calculate_hand_distance(px, py)
                cv2.circle(frame, (px, py), 10, (0, 255, 0), -1)
                cv2.putText(frame, f"{self.hand_distance:.0f}mm",
                            (px + 15, py), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (0, 255, 0), 2)

        # Object detection
        now = time.time()
        if now - self.last_detection_time > 1.0:
            self.detect_objects(frame)
            self.last_detection_time = now

        for obj in self.detected_objects:
            x, y, w, h, label = obj
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
            cv2.putText(frame, label, (x, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        return frame

    def detect_objects(self, frame):
        """Placeholder object detection (green PCB color detection)."""
        hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([40, 40, 40]), np.array([80, 255, 255]))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self.detected_objects = []
        for c in contours:
            if cv2.contourArea(c) > 5000:
                x, y, w, h = cv2.boundingRect(c)
                self.detected_objects.append((x, y, w, h, "PCB Board"))

    def calculate_hand_distance(self, hx, hy):
        """Pixel-based distance estimate (needs proper camera calibration)."""
        if self.camera is None:
            return float('inf')
        ex = self.camera.get(cv2.CAP_PROP_FRAME_WIDTH) / 2
        ey = self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
        return np.sqrt((hx - ex)**2 + (hy - ey)**2) * 2.0

    # ── SAFETY ───────────────────────────────────────────────────

    def check_safety(self):
        violations = []
        if self.hand_detected and self.hand_distance < Config.MIN_HAND_DISTANCE:
            if self.state == SystemState.AUTO_MODE:
                violations.append(f"Hand too close: {self.hand_distance:.0f}mm")
        if violations:
            self.safety_violations = violations
            if self.state == SystemState.AUTO_MODE:
                logger.warning(f"Safety: {violations}")
                self.disable_motors()
        else:
            self.safety_violations = []
        return len(violations) == 0

    # ── CONTROL ──────────────────────────────────────────────────

    def set_end_effector(self, effector_type):
        self.end_effector_type = effector_type
        self.task_active = False
        logger.info(f"End effector: {effector_type.name}")

    def toggle_auto_mode(self):
        if self.state == SystemState.AUTO_MODE:
            self.state = SystemState.READY
            logger.info("→ MANUAL mode")
        else:
            self.state = SystemState.AUTO_MODE
            logger.info("→ AUTO mode")

    def toggle_teaching_mode(self):
        if self.state == SystemState.TEACHING_MODE:
            self.state = SystemState.READY
            self.recording_session = False
            logger.info("Teaching stopped")
        else:
            self.state = SystemState.TEACHING_MODE
            self.recording_session = True
            logger.info("Teaching started")

    def trigger_emergency_stop(self):
        self.emergency_stop = True
        self.state = SystemState.EMERGENCY_STOP
        self.disable_motors()
        logger.warning("EMERGENCY STOP")

    # ── STATUS OVERLAY ───────────────────────────────────────────

    def add_status_overlay(self, frame):
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (380, 220), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        color = (0, 255, 0) if not self.safety_violations else (0, 0, 255)
        lines = [
            f"State: {self.state.name}",
            f"EE: {self.end_effector_type.name}",
            f"Hand: {'YES' if self.hand_detected else 'NO'}  Dist: {self.hand_distance:.0f}mm",
            f"Objects: {len(self.detected_objects)}",
            f"Hardware: {'READY' if self.hardware_ready else 'WAITING'}",
        ]
        for i, text in enumerate(lines):
            cv2.putText(frame, text, (20, 40 + i * 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        if self.safety_violations:
            cv2.putText(frame, "SAFETY ALERT", (20, h - 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

        cv2.putText(frame, "Q:Quit A:Auto T:Teach E:EStop",
                    (w - 420, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # ── RUN / SHUTDOWN ───────────────────────────────────────────

    def run(self):
        if not self.initialize():
            logger.error("Init failed")
            return

        self.is_running = True
        logger.info("Engine running. Press Q to quit.")

        try:
            while self.is_running:
                if self.camera is None:
                    time.sleep(0.1)
                    continue

                ret, frame = self.camera.read()
                if not ret:
                    logger.warning("Frame capture failed")
                    continue

                frame = self.process_frame(frame)
                self.check_safety()
                self.add_status_overlay(frame)

                cv2.imshow('APEX_PREDATOR Vision', frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('a'):
                    self.toggle_auto_mode()
                elif key == ord('t'):
                    self.toggle_teaching_mode()
                elif key == ord('e'):
                    self.trigger_emergency_stop()

        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def shutdown(self):
        logger.info("Shutting down...")
        self.is_running = False
        if self.serial:
            try:
                self.disable_motors()
                self.disable_heater()
                time.sleep(0.3)
                self.serial.close()
            except Exception:
                pass
        if self.camera:
            self.camera.release()
        cv2.destroyAllWindows()
        logger.info("✓ Shutdown complete")


# ── ENTRY POINT ──────────────────────────────────────────────────

def main():
    print("""
    ╔══════════════════════════════════════════════╗
    ║   APEX_PREDATOR_ENGINE v2.1                  ║
    ║   AI-Powered Vision & Control System         ║
    ╚══════════════════════════════════════════════╝
    """)
    engine = ApexPredatorEngine()
    engine.run()

if __name__ == "__main__":
    main()
