"""
═══════════════════════════════════════════════════════════════════
                    APEX_PREDATOR_ENGINE v2.0
═══════════════════════════════════════════════════════════════════

AI-Powered Cobot Control Engine
Features:
- Computer Vision (OpenCV + MediaPipe)
- Hand tracking for collaborative tasks
- Task recognition and automation
- Safety monitoring
- Real-time communication with hardware (Master/Slave Handshake)

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
import mediapipe as mp
# FIX: Removed duplicate mediapipe imports (were imported twice identically)
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('apex_predator_engine.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('APEX_ENGINE')

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

class Config:
    SERIAL_PORT = 'COM12'  # Change to your port
    BAUD_RATE = 115200
    CAMERA_INDEX = 0
    CAMERA_WIDTH = 1280
    CAMERA_HEIGHT = 720
    CAMERA_FPS = 30
    MIN_HAND_DISTANCE = 200
    MAX_VELOCITY = 100
    SAFE_ZONE_RADIUS = 150
    CONFIDENCE_THRESHOLD = 0.7
    DETECTION_COOLDOWN = 1.0
    SOLDER_PREHEAT_TIME = 30
    SOLDER_TEMP_TARGET = 350
    SOLDER_FOLLOW_DISTANCE = 50

# ═══════════════════════════════════════════════════════════════════
# SYSTEM STATES
# ═══════════════════════════════════════════════════════════════════

class SystemState(Enum):
    IDLE = 0
    INITIALIZING = 1
    READY = 2
    AUTO_MODE = 3
    MANUAL_MODE = 4
    TEACHING_MODE = 5
    EMERGENCY_STOP = 6
    ERROR = 7

class EndEffectorType(Enum):
    NONE = 0
    SOLDERING_IRON = 1
    GRIPPER = 2
    PEN = 3
    CUSTOM = 4

# ═══════════════════════════════════════════════════════════════════
# APEX PREDATOR ENGINE
# ═══════════════════════════════════════════════════════════════════

class ApexPredatorEngine:
    def __init__(self):
        logger.info("Initializing APEX_PREDATOR_ENGINE...")

        self.config = self.load_config()
        self.state = SystemState.INITIALIZING
        self.end_effector_type = EndEffectorType.NONE
        self.is_running = False
        self.emergency_stop = False

        self.serial = None
        self.serial_lock = threading.Lock()
        self.hardware_feedback = {}

        self.camera = None
        self.landmarker = None
        self.timestamp = 0
        self.hand_positions = deque(maxlen=30)

        self.detected_objects = []
        self.last_detection_time = 0

        self.current_task = None
        self.task_active = False
        self.solder_preheating = False
        self.heater_start_time = 0

        self.safety_violations = []
        self.hand_detected = False
        self.hand_distance = float('inf')

        self.session_data = []
        self.recording_session = False

    def load_config(self):
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                logger.info("Configuration loaded successfully")
                return config
        except Exception as e:
            logger.warning(f"Failed to load config.json: {e}. Using defaults.")
            return {}

    # ═══════════════════════════════════════════════════════════════
    # INITIALIZATION
    # ═══════════════════════════════════════════════════════════════

    def initialize(self):
        try:
            logger.info("Starting initialization sequence...")

            if not self.init_serial():
                logger.warning("Serial initialization failed - running in simulation mode")

            if not self.init_camera():
                logger.warning("Camera initialization failed - vision features disabled")

            if not self.init_hand_tracking():
                logger.error("Hand tracking initialization failed")
                return False

            self.state = SystemState.READY
            logger.info("✓ APEX_PREDATOR_ENGINE initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            self.state = SystemState.ERROR
            return False

    def init_serial(self):
        try:
            port = self.config.get('hardware', {}).get('arduino', {}).get('serial_port', Config.SERIAL_PORT)
            self.serial = serial.Serial(port, Config.BAUD_RATE, timeout=2)
            time.sleep(2)

            # Wait for APEX_READY boot signal
            logger.info("Waiting for APEX_READY signal from firmware...")
            timeout = time.time() + 10
            while time.time() < timeout:
                if self.serial.in_waiting:
                    line = self.serial.readline().decode('utf-8').strip()
                    if line == "APEX_READY":
                        logger.info(f"✓ Serial connected on {port}, firmware ready")
                        return True
                time.sleep(0.1)

            logger.warning("APEX_READY timeout — firmware may be an older version, continuing")
            return True

        except Exception as e:
            logger.error(f"Serial initialization error: {e}")
            return False

    def init_camera(self):
        try:
            self.camera = cv2.VideoCapture(Config.CAMERA_INDEX)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, Config.CAMERA_WIDTH)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.CAMERA_HEIGHT)
            self.camera.set(cv2.CAP_PROP_FPS, Config.CAMERA_FPS)

            if not self.camera.isOpened():
                return False

            ret, frame = self.camera.read()
            if not ret:
                return False

            logger.info(f"✓ Camera initialized: {frame.shape[1]}x{frame.shape[0]}")
            return True
        except Exception as e:
            logger.error(f"Camera initialization error: {e}")
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
            logger.info("✓ Hand tracking initialized")
            return True
        except Exception as e:
            logger.error(f"Hand tracking initialization error: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════
    # COMMUNICATION — MASTER/SLAVE HANDSHAKE
    # ═══════════════════════════════════════════════════════════════

    def send_and_wait(self, command, timeout=None):
        """
        BLOCKING HANDSHAKE: Send command, wait for OK or ERR.
        Returns True on OK, False on ERR or timeout.
        """
        if timeout is None:
            timeout = self.config.get('communication', {}).get('handshake_timeout', 5.0)

        if not self.serial:
            logger.warning(f"Serial not connected — simulating OK for: {command}")
            return True  # Simulation mode

        try:
            with self.serial_lock:
                self.serial.reset_input_buffer()
                self.serial.write(f"{command}\n".encode())
                logger.debug(f"TX: {command}")

                start_time = time.time()
                while time.time() - start_time < timeout:
                    if self.serial.in_waiting:
                        line = self.serial.readline().decode('utf-8').strip()
                        if line:
                            logger.debug(f"RX: {line}")
                        if line == "OK":
                            logger.info(f"✓ Command executed: {command}")
                            return True
                        elif line.startswith("ERR"):
                            logger.error(f"✗ Command rejected: {line}")
                            return False
                    time.sleep(0.01)

                logger.error(f"✗ Handshake timeout ({timeout}s) for: {command}")
                return False

        except Exception as e:
            logger.error(f"Handshake error: {e}")
            return False

    # FIX: Added send_command() method — was called from the GUI's
    # set_manual_mode() but didn't exist, causing AttributeError crash
    def send_command(self, command):
        """Generic command send — wraps send_and_wait for simple fire-and-wait usage."""
        return self.send_and_wait(command)

    def send_move_command(self, x_angle, y_angle, z_angle):
        """Send a MOVE command with kinematic limit validation."""
        limits = self.config.get('kinematic_limits', {})
        x_min = limits.get('joint_x_base', {}).get('min_angle', -180)
        x_max = limits.get('joint_x_base', {}).get('max_angle', 180)
        y_min = limits.get('joint_y_shoulder', {}).get('min_angle', -30)
        y_max = limits.get('joint_y_shoulder', {}).get('max_angle', 90)
        z_min = limits.get('joint_z_elbow', {}).get('min_angle', -90)
        z_max = limits.get('joint_z_elbow', {}).get('max_angle', 90)

        if not (x_min <= x_angle <= x_max):
            logger.warning(f"X {x_angle}° out of bounds [{x_min}, {x_max}]")
            return False
        if not (y_min <= y_angle <= y_max):
            logger.warning(f"Y {y_angle}° out of bounds [{y_min}, {y_max}]")
            return False
        if not (z_min <= z_angle <= z_max):
            logger.warning(f"Z {z_angle}° out of bounds [{z_min}, {z_max}]")
            return False

        command = f"<MOVE X{x_angle:.1f} Y{y_angle:.1f} Z{z_angle:.1f}>"
        return self.send_and_wait(command)

    def send_home_command(self):
        """Trigger double-tap homing sequence."""
        logger.info("Initiating autonomous homing sequence...")
        return self.send_and_wait("HOME", timeout=60.0)

    def open_gripper(self):   return self.send_and_wait("GRIPPER_OPEN")
    def close_gripper(self):  return self.send_and_wait("GRIPPER_CLOSE")
    def enable_heater(self):  return self.send_and_wait("HEATER_ON")
    def disable_heater(self): return self.send_and_wait("HEATER_OFF")

    # FIX: EN/DIS commands now match firmware (previously sent MOTORS_EN/DIS
    # but demo script sends EN/DIS — firmware now accepts both, engine uses EN/DIS)
    def enable_motors(self):  return self.send_and_wait("EN")
    def disable_motors(self): return self.send_and_wait("DIS")

    # ═══════════════════════════════════════════════════════════════
    # VISION PROCESSING
    # ═══════════════════════════════════════════════════════════════

    def process_frame(self, frame):
        """Process camera frame for vision tasks."""
        if self.landmarker is None:
            return frame

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        self.timestamp += 1
        results = self.landmarker.detect_for_video(mp_image, self.timestamp)

        self.hand_detected = False

        if results.hand_landmarks:
            self.hand_detected = True
            for hand_landmarks in results.hand_landmarks:
                palm_x = int(hand_landmarks[9].x * frame.shape[1])
                palm_y = int(hand_landmarks[9].y * frame.shape[0])
                self.hand_positions.append((palm_x, palm_y, time.time()))
                cv2.circle(frame, (palm_x, palm_y), 10, (0, 255, 0), -1)
                self.hand_distance = self.calculate_hand_distance(palm_x, palm_y)
                cv2.putText(frame, f"Hand: {self.hand_distance:.0f}mm",
                            (palm_x + 20, palm_y), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (0, 255, 0), 2)

        current_time = time.time()
        if current_time - self.last_detection_time > Config.DETECTION_COOLDOWN:
            self.detect_objects(frame)
            self.last_detection_time = current_time

        for obj in self.detected_objects:
            x, y, w, h, label = obj
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
            cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

        return frame

    def detect_objects(self, frame):
        """Detect objects in frame (PCB color detection placeholder)."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_green = np.array([40, 40, 40])
        upper_green = np.array([80, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        self.detected_objects = []
        for contour in contours:
            if cv2.contourArea(contour) > 5000:
                x, y, w, h = cv2.boundingRect(contour)
                self.detected_objects.append((x, y, w, h, "PCB Board"))

    def calculate_hand_distance(self, hand_x, hand_y):
        """Estimate hand distance from end effector (placeholder, needs calibration)."""
        if self.camera is None:
            return float('inf')
        effector_x = self.camera.get(cv2.CAP_PROP_FRAME_WIDTH) // 2
        effector_y = self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
        pixel_distance = np.sqrt((hand_x - effector_x) ** 2 + (hand_y - effector_y) ** 2)
        return pixel_distance * 2  # 1 pixel ≈ 2mm (needs calibration)

    # ═══════════════════════════════════════════════════════════════
    # TASK RECOGNITION
    # ═══════════════════════════════════════════════════════════════

    def recognize_task(self):
        if self.end_effector_type == EndEffectorType.SOLDERING_IRON:
            for obj in self.detected_objects:
                if "PCB" in obj[4]:
                    return "SOLDERING_TASK"
        return None

    def handle_soldering_task(self):
        if not self.task_active:
            if not self.solder_preheating:
                self.enable_heater()
                self.solder_preheating = True
                self.heater_start_time = time.time()
                logger.info("Preheating soldering iron...")

            preheat_time = time.time() - self.heater_start_time
            if preheat_time >= Config.SOLDER_PREHEAT_TIME:
                temp = self.hardware_feedback.get('temp', 0)
                if temp >= Config.SOLDER_TEMP_TARGET * 0.9:
                    logger.info(f"✓ Soldering iron ready at {temp}°C")
                    self.task_active = True
                    self.state = SystemState.AUTO_MODE

        if self.task_active and self.hand_detected:
            self.follow_hand_for_soldering()

    def follow_hand_for_soldering(self):
        if len(self.hand_positions) < 2:
            return
        current_pos = self.hand_positions[-1]
        prev_pos = self.hand_positions[-2]
        dx = current_pos[0] - prev_pos[0]
        dy = current_pos[1] - prev_pos[1]
        dt = current_pos[2] - prev_pos[2]
        if dt > 0:
            velocity = np.sqrt(dx ** 2 + dy ** 2) / dt
            if velocity < 100:
                logger.debug(f"Following hand at velocity {velocity:.1f}px/s")

    # ═══════════════════════════════════════════════════════════════
    # SAFETY
    # ═══════════════════════════════════════════════════════════════

    def check_safety(self):
        violations = []
        if self.hand_detected and self.hand_distance < Config.MIN_HAND_DISTANCE:
            if self.state == SystemState.AUTO_MODE:
                violations.append(f"Hand too close: {self.hand_distance:.0f}mm")

        tof_distance = self.hardware_feedback.get('distance', 1000)
        if tof_distance < Config.SAFE_ZONE_RADIUS:
            violations.append(f"ToF proximity: {tof_distance}mm")

        if violations:
            self.safety_violations = violations
            if self.state == SystemState.AUTO_MODE:
                logger.warning(f"Safety violation: {violations}")
                self.disable_motors()
        else:
            self.safety_violations = []

        return len(violations) == 0

    # ═══════════════════════════════════════════════════════════════
    # STATUS OVERLAY
    # ═══════════════════════════════════════════════════════════════

    def add_status_overlay(self, frame):
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (400, 230), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        texts = [
            f"State: {self.state.name}",
            f"End Effector: {self.end_effector_type.name}",
            f"Hand: {'YES' if self.hand_detected else 'NO'} ({self.hand_distance:.0f}mm)",
            f"Objects: {len(self.detected_objects)}",
            f"Motors: {'ON' if self.hardware_feedback.get('motors_enabled', False) else 'OFF'}",
            f"Heater: {'ON' if self.hardware_feedback.get('heater_enabled', False) else 'OFF'}",
            f"Temp: {self.hardware_feedback.get('temp', 0):.1f}°C",
        ]
        color = (0, 255, 0) if not self.safety_violations else (0, 0, 255)
        for i, text in enumerate(texts):
            cv2.putText(frame, text, (20, 40 + i * 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)

        if self.safety_violations:
            cv2.putText(frame, "SAFETY ALERT", (20, h - 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
            cv2.putText(frame, self.safety_violations[0], (20, h - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        cv2.putText(frame, "Q:Quit S:Solder A:Auto T:Teach E:E-Stop",
                    (w - 490, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # ═══════════════════════════════════════════════════════════════
    # MAIN LOOP
    # ═══════════════════════════════════════════════════════════════

    def run(self):
        if not self.initialize():
            logger.error("Initialization failed, cannot start engine")
            return

        self.is_running = True
        logger.info("APEX_PREDATOR_ENGINE is running...")

        try:
            while self.is_running:
                if self.camera is None:
                    time.sleep(0.033)
                    continue

                ret, frame = self.camera.read()
                if not ret:
                    logger.error("Failed to capture frame")
                    continue

                processed_frame = self.process_frame(frame)
                self.check_safety()

                if self.state == SystemState.AUTO_MODE:
                    task = self.recognize_task()
                    if task == "SOLDERING_TASK":
                        self.handle_soldering_task()

                self.add_status_overlay(processed_frame)
                cv2.imshow('APEX_PREDATOR Vision', processed_frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('s'):
                    self.set_end_effector(EndEffectorType.SOLDERING_IRON)
                elif key == ord('a'):
                    self.toggle_auto_mode()
                elif key == ord('t'):
                    self.toggle_teaching_mode()
                elif key == ord('e'):
                    self.trigger_emergency_stop()

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.shutdown()

    # ═══════════════════════════════════════════════════════════════
    # CONTROL FUNCTIONS
    # ═══════════════════════════════════════════════════════════════

    def set_end_effector(self, effector_type):
        self.end_effector_type = effector_type
        self.task_active = False
        self.solder_preheating = False
        logger.info(f"End effector: {effector_type.name}")

    def toggle_auto_mode(self):
        if self.state == SystemState.AUTO_MODE:
            self.state = SystemState.READY
        else:
            self.state = SystemState.AUTO_MODE
        logger.info(f"State: {self.state.name}")

    def toggle_teaching_mode(self):
        if self.state == SystemState.TEACHING_MODE:
            self.state = SystemState.READY
            self.recording_session = False
        else:
            self.state = SystemState.TEACHING_MODE
            self.recording_session = True
        logger.info(f"Teaching mode: {'ON' if self.state == SystemState.TEACHING_MODE else 'OFF'}")

    def trigger_emergency_stop(self):
        self.emergency_stop = True
        self.state = SystemState.EMERGENCY_STOP
        self.disable_motors()
        logger.warning("EMERGENCY STOP TRIGGERED")

    def shutdown(self):
        logger.info("Shutting down APEX_PREDATOR_ENGINE...")
        self.is_running = False

        if self.serial:
            self.disable_motors()
            self.disable_heater()
            time.sleep(0.5)
            self.serial.close()

        if self.camera:
            self.camera.release()

        cv2.destroyAllWindows()
        logger.info("✓ Shutdown complete")

# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    print("""
    ╔══════════════════════════════════════════════╗
    ║       APEX_PREDATOR ENGINE v2.0              ║
    ║     AI-Powered Vision & Control System       ║
    ╚══════════════════════════════════════════════╝
    """)
    engine = ApexPredatorEngine()
    engine.run()

if __name__ == "__main__":
    main()
