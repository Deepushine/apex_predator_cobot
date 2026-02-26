"""
═══════════════════════════════════════════════════════════════════
                    APEX_PREDATOR_ENGINE v1.0
═══════════════════════════════════════════════════════════════════

AI-Powered Cobot Control Engine
Features:
- Computer Vision (OpenCV + MediaPipe)
- Object Detection (YOLO / Custom models)
- Hand tracking for collaborative tasks
- Task recognition and automation
- Safety monitoring
- Real-time communication with hardware

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
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
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
    # Serial communication
    SERIAL_PORT = 'COM12'  # Change to your Arduino port (COM3, /dev/ttyACM0, etc.)
    BAUD_RATE = 115200
    HEARTBEAT_INTERVAL = 0.5  # seconds
    
    # Camera
    CAMERA_INDEX = 0
    CAMERA_WIDTH = 1280
    CAMERA_HEIGHT = 720
    CAMERA_FPS = 30
    
    # Safety
    MIN_HAND_DISTANCE = 200  # mm - minimum safe distance from end effector
    MAX_VELOCITY = 100  # mm/s - maximum end effector velocity
    SAFE_ZONE_RADIUS = 150  # mm
    
    # Task Recognition
    CONFIDENCE_THRESHOLD = 0.7
    DETECTION_COOLDOWN = 1.0  # seconds between detections
    
    # Soldering specific
    SOLDER_PREHEAT_TIME = 30  # seconds
    SOLDER_TEMP_TARGET = 350  # °C
    SOLDER_FOLLOW_DISTANCE = 50  # mm behind hand

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
        
        # Load configuration
        self.config = self.load_config()
        
        # System state
        self.state = SystemState.INITIALIZING
        self.end_effector_type = EndEffectorType.NONE
        self.is_running = False
        self.emergency_stop = False
        
        # Motor pin mapping
        self.motor_pins = self.config.get('hardware', {}).get('motor_pins', {})
        self.joint_mapping = self.config.get('hardware', {}).get('joint_mapping', {})
        
        # Serial communication
        self.serial = None
        self.serial_lock = threading.Lock()
        self.last_heartbeat = 0
        self.hardware_feedback = {}
        
        # Camera and vision
        self.camera = None
        self.mp_hands = None
        self.landmarker = None
        self.timestamp = 0
        self.mp_drawing = None
        self.hand_positions = deque(maxlen=30)  # Track hand movement
        
        # Object detection (placeholder for YOLO)
        self.detected_objects = []
        self.last_detection_time = 0
        
        # Task state
        self.current_task = None
        self.task_active = False
        self.solder_preheating = False
        self.heater_start_time = 0
        
        # Safety monitoring
        self.safety_violations = []
        self.hand_detected = False
        self.hand_distance = float('inf')
        
        # Data recording
        self.session_data = []
        self.recording_session = False
    
    def load_config(self):
        """Load configuration from config.json"""
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
        """Initialize all subsystems"""
        try:
            logger.info("Starting initialization sequence...")
            
            # Initialize serial connection
            if not self.init_serial():
                logger.warning("Serial initialization failed - running in simulation mode")
                # Continue without hardware
            
            # Initialize camera
            if not self.init_camera():
                logger.warning("Camera initialization failed - vision features disabled")
                # Continue without camera
            
            # Initialize hand tracking
            if not self.init_hand_tracking():
                logger.error("Hand tracking initialization failed")
                return False
            
            # Wait for hardware ready signal
            logger.info("Waiting for hardware ready signal...")
            timeout = time.time() + 10
            while time.time() < timeout:
                if self.check_hardware_ready():
                    break
                time.sleep(0.1)
            else:
                logger.warning("Hardware ready timeout - continuing anyway")
            
            self.state = SystemState.READY
            logger.info("✓ APEX_PREDATOR_ENGINE initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            self.state = SystemState.ERROR
            return False
    
    def init_serial(self):
        """Initialize serial communication with Arduino"""
        try:
            self.serial = serial.Serial(
                Config.SERIAL_PORT,
                Config.BAUD_RATE,
                timeout=1
            )
            time.sleep(2)  # Wait for Arduino reset
            logger.info(f"✓ Serial connection established on {Config.SERIAL_PORT}")
            
            # Start heartbeat thread
            self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
            self.heartbeat_thread.start()
            
            # Start feedback receiver thread
            self.feedback_thread = threading.Thread(target=self.receive_feedback_loop, daemon=True)
            self.feedback_thread.start()
            
            return True
        except Exception as e:
            logger.error(f"Serial initialization error: {e}")
            return False
    
    def init_camera(self):
        """Initialize camera"""
        try:
            self.camera = cv2.VideoCapture(Config.CAMERA_INDEX)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, Config.CAMERA_WIDTH)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, Config.CAMERA_HEIGHT)
            self.camera.set(cv2.CAP_PROP_FPS, Config.CAMERA_FPS)
            
            if not self.camera.isOpened():
                logger.error("Failed to open camera")
                return False
            
            # Test frame
            ret, frame = self.camera.read()
            if not ret:
                logger.error("Failed to read from camera")
                return False
            
            logger.info(f"✓ Camera initialized: {frame.shape[1]}x{frame.shape[0]}")
            return True
        except Exception as e:
            logger.error(f"Camera initialization error: {e}")
            return False
    
    def init_hand_tracking(self):
        """Initialize MediaPipe hand tracking"""
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
    # COMMUNICATION
    # ═══════════════════════════════════════════════════════════════
    
    def send_command(self, command):
        """Send command to Arduino"""
        try:
            with self.serial_lock:
                self.serial.write(f"{command}\n".encode())
                logger.debug(f"TX: {command}")
        except Exception as e:
            logger.error(f"Send command error: {e}")
    
    def send_joint_command(self, joint, value):
        """Send joint command with axis translation"""
        # Get the axis for this joint from config
        joint_key = f"joint{joint}"
        axis_name = self.joint_mapping.get(joint_key, f"joint{joint}")
        
        # Get the pin for this axis
        pin = self.motor_pins.get(axis_name, f"J{joint}")
        
        # Extract the pin number (e.g., "J13" -> "13")
        pin_num = pin.replace("J", "") if pin.startswith("J") else pin
        
        # Send command with correct pin
        command = f"{pin}:{value}"
        self.send_command(command)
        logger.info(f"Joint {joint} ({axis_name} @ {pin}) -> {value}°")
    
    def heartbeat_loop(self):
        """Send periodic heartbeat to hardware"""
        while True:
            try:
                current_time = time.time()
                if current_time - self.last_heartbeat >= Config.HEARTBEAT_INTERVAL:
                    self.send_command("HB")
                    self.last_heartbeat = current_time
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
    
    def receive_feedback_loop(self):
        """Receive and parse feedback from Arduino"""
        while True:
            try:
                if self.serial.in_waiting:
                    line = self.serial.readline().decode('utf-8').strip()
                    self.parse_feedback(line)
                time.sleep(0.01)
            except Exception as e:
                logger.error(f"Receive feedback error: {e}")
    
    def parse_feedback(self, line):
        """Parse feedback from Arduino"""
        logger.debug(f"RX: {line}")
        
        if line.startswith("FB:"):
            # Parse feedback: FB:j1,j2,j3,j4,temp,dist,mode,motors,heater
            parts = line[3:].split(',')
            if len(parts) >= 9:
                self.hardware_feedback = {
                    'j1': int(parts[0]),
                    'j2': int(parts[1]),
                    'j3': int(parts[2]),
                    'j4': int(parts[3]),
                    'temp': float(parts[4]),
                    'distance': int(parts[5]),
                    'mode': int(parts[6]),
                    'motors_enabled': int(parts[7]) == 1,
                    'heater_enabled': int(parts[8]) == 1
                }
        
        elif line.startswith("STS:"):
            status = line[4:]
            logger.info(f"Hardware Status: {status}")
            
            if "EMERGENCY_STOP" in status:
                self.emergency_stop = True
                self.state = SystemState.EMERGENCY_STOP
            elif "SYSTEM_READY" in status:
                logger.info("Hardware is ready")
    
    def check_hardware_ready(self):
        """Check if hardware is ready"""
        return len(self.hardware_feedback) > 0
    
    # ═══════════════════════════════════════════════════════════════
    # VISION PROCESSING
    # ═══════════════════════════════════════════════════════════════
    
    def process_frame(self, frame):
        """Process camera frame for vision tasks"""
        # Convert to RGB for MediaPipe
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Hand tracking
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        self.timestamp += 1
        results = self.landmarker.detect_for_video(mp_image, self.timestamp)
        
        # Reset hand detection
        self.hand_detected = False
        
        if results.hand_landmarks:
            self.hand_detected = True
            
            for hand_landmarks in results.hand_landmarks:
                # Get palm center (approximate)
                palm_x = int(hand_landmarks[9].x * frame.shape[1])
                palm_y = int(hand_landmarks[9].y * frame.shape[0])
                
                # Store position
                self.hand_positions.append((palm_x, palm_y, time.time()))
                
                # Draw position marker
                cv2.circle(frame, (palm_x, palm_y), 10, (0, 255, 0), -1)
                
                # Calculate distance to end effector (placeholder - needs calibration)
                # This would use camera calibration and robot kinematics
                self.hand_distance = self.calculate_hand_distance(palm_x, palm_y)
                
                # Display distance
                cv2.putText(frame, f"Hand Distance: {self.hand_distance:.0f}mm",
                           (palm_x + 20, palm_y), cv2.FONT_HERSHEY_SIMPLEX,
                           0.6, (0, 255, 0), 2)
        
        # Object detection (placeholder for YOLO)
        current_time = time.time()
        if current_time - self.last_detection_time > Config.DETECTION_COOLDOWN:
            self.detect_objects(frame)
            self.last_detection_time = current_time
        
        # Draw detected objects
        for obj in self.detected_objects:
            x, y, w, h, label = obj
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
            cv2.putText(frame, label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX,
                       0.6, (255, 0, 0), 2)
        
        return frame
    
    def detect_objects(self, frame):
        """Detect objects in frame (placeholder for YOLO)"""
        # This is where you would run YOLO or other object detection
        # For now, use simple template matching for common objects
        
        # Detect PCB board (using color detection as example)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Example: Detect green PCB boards
        lower_green = np.array([40, 40, 40])
        upper_green = np.array([80, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        self.detected_objects = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 5000:  # Minimum area threshold
                x, y, w, h = cv2.boundingRect(contour)
                self.detected_objects.append((x, y, w, h, "PCB Board"))
    
    def calculate_hand_distance(self, hand_x, hand_y):
        """Calculate distance between hand and end effector"""
        # This is a placeholder - requires camera calibration and robot FK
        # For now, return a mock distance based on screen position
        
        # Assume end effector is at center bottom of screen
        effector_x = self.camera.get(cv2.CAP_PROP_FRAME_WIDTH) // 2
        effector_y = self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
        
        pixel_distance = np.sqrt((hand_x - effector_x)**2 + (hand_y - effector_y)**2)
        
        # Mock conversion: 1 pixel ≈ 2mm (needs calibration)
        mm_distance = pixel_distance * 2
        
        return mm_distance
    
    # ═══════════════════════════════════════════════════════════════
    # TASK RECOGNITION & AUTOMATION
    # ═══════════════════════════════════════════════════════════════
    
    def recognize_task(self):
        """Recognize current task based on detected objects and end effector"""
        if self.end_effector_type == EndEffectorType.SOLDERING_IRON:
            # Check for PCB board
            for obj in self.detected_objects:
                if "PCB" in obj[4]:
                    return "SOLDERING_TASK"
        
        return None
    
    def handle_soldering_task(self):
        """Handle automatic soldering task"""
        if not self.task_active:
            logger.info("🔥 Soldering task detected - Preparing...")
            
            # Enable heater
            if not self.solder_preheating:
                self.send_command("HEAT_ON")
                self.solder_preheating = True
                self.heater_start_time = time.time()
                logger.info("Preheating soldering iron...")
            
            # Check if ready
            preheat_time = time.time() - self.heater_start_time
            if preheat_time >= Config.SOLDER_PREHEAT_TIME:
                temp = self.hardware_feedback.get('temp', 0)
                if temp >= Config.SOLDER_TEMP_TARGET * 0.9:  # 90% of target
                    logger.info(f"✓ Soldering iron ready at {temp}°C")
                    self.task_active = True
                    self.send_command("MODE:AUTO")
                else:
                    logger.info(f"Heating... {temp}°C / {Config.SOLDER_TEMP_TARGET}°C")
        
        # Follow hand movement when task is active
        if self.task_active and self.hand_detected:
            self.follow_hand_for_soldering()
    
    def follow_hand_for_soldering(self):
        """Follow hand movement while maintaining safe distance"""
        if len(self.hand_positions) < 2:
            return
        
        # Get recent hand positions
        current_pos = self.hand_positions[-1]
        prev_pos = self.hand_positions[-2]
        
        # Calculate hand velocity
        dx = current_pos[0] - prev_pos[0]
        dy = current_pos[1] - prev_pos[1]
        dt = current_pos[2] - prev_pos[2]
        
        if dt > 0:
            velocity = np.sqrt(dx**2 + dy**2) / dt
            
            # Only follow if hand is moving slowly (deliberate movement)
            if velocity < 100:  # pixels/second
                # Calculate target position (behind hand)
                target_x = current_pos[0] - Config.SOLDER_FOLLOW_DISTANCE * (dx / velocity) if velocity > 0 else current_pos[0]
                target_y = current_pos[1]
                
                # Convert to robot coordinates (requires calibration)
                # This is placeholder - needs proper hand-eye calibration
                logger.debug(f"Following hand to: ({target_x:.0f}, {target_y:.0f})")
                
                # Send move command (this needs inverse kinematics)
                # self.move_to_camera_position(target_x, target_y)
    
    # ═══════════════════════════════════════════════════════════════
    # SAFETY MONITORING
    # ═══════════════════════════════════════════════════════════════
    
    def check_safety(self):
        """Check safety conditions"""
        violations = []
        
        # Check hand distance
        if self.hand_detected and self.hand_distance < Config.MIN_HAND_DISTANCE:
            if self.state == SystemState.AUTO_MODE:
                violations.append(f"Hand too close: {self.hand_distance:.0f}mm")
        
        # Check ToF sensor from hardware
        tof_distance = self.hardware_feedback.get('distance', 1000)
        if tof_distance < Config.SAFE_ZONE_RADIUS:
            violations.append(f"ToF proximity alert: {tof_distance}mm")
        
        # If violations found, trigger safety stop
        if violations:
            self.safety_violations = violations
            if self.state == SystemState.AUTO_MODE:
                logger.warning(f"Safety violation: {violations}")
                self.send_command("DIS")  # Disable motors
                # Don't change state, just pause
        else:
            self.safety_violations = []
        
        return len(violations) == 0
    
    # ═══════════════════════════════════════════════════════════════
    # MAIN CONTROL LOOP
    # ═══════════════════════════════════════════════════════════════
    
    def run(self):
        """Main engine loop"""
        if not self.initialize():
            logger.error("Initialization failed, cannot start engine")
            return
        
        self.is_running = True
        logger.info("APEX_PREDATOR_ENGINE is running...")
        
        try:
            while self.is_running:
                # Capture frame
                ret, frame = self.camera.read()
                if not ret:
                    logger.error("Failed to capture frame")
                    continue
                
                # Process frame
                processed_frame = self.process_frame(frame)
                
                # Check safety
                self.check_safety()
                
                # Task recognition and handling
                if self.state == SystemState.AUTO_MODE:
                    task = self.recognize_task()
                    if task == "SOLDERING_TASK":
                        self.handle_soldering_task()
                
                # Add status overlay
                self.add_status_overlay(processed_frame)
                
                # Display frame
                cv2.imshow('APEX_PREDATOR Vision', processed_frame)
                
                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    logger.info("Quit signal received")
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
    
    def add_status_overlay(self, frame):
        """Add status information overlay to frame"""
        h, w = frame.shape[:2]
        
        # Create semi-transparent overlay
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (400, 250), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Status text
        y_offset = 40
        line_height = 25
        
        texts = [
            f"State: {self.state.name}",
            f"End Effector: {self.end_effector_type.name}",
            f"Hand Detected: {'YES' if self.hand_detected else 'NO'}",
            f"Hand Distance: {self.hand_distance:.0f}mm",
            f"Objects: {len(self.detected_objects)}",
            f"Motors: {'ON' if self.hardware_feedback.get('motors_enabled', False) else 'OFF'}",
            f"Heater: {'ON' if self.hardware_feedback.get('heater_enabled', False) else 'OFF'}",
            f"Temp: {self.hardware_feedback.get('temp', 0):.1f}°C"
        ]
        
        for i, text in enumerate(texts):
            color = (0, 255, 0) if not self.safety_violations else (0, 0, 255)
            cv2.putText(frame, text, (20, y_offset + i * line_height),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        # Safety warnings
        if self.safety_violations:
            cv2.putText(frame, "⚠ SAFETY ALERT", (20, h - 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
            cv2.putText(frame, self.safety_violations[0], (20, h - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        # Keyboard shortcuts
        cv2.putText(frame, "Q:Quit S:Solder A:Auto T:Teach E:E-Stop",
                   (w - 500, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    # ═══════════════════════════════════════════════════════════════
    # CONTROL FUNCTIONS
    # ═══════════════════════════════════════════════════════════════
    
    def set_end_effector(self, effector_type):
        """Set the current end effector type"""
        self.end_effector_type = effector_type
        logger.info(f"End effector set to: {effector_type.name}")
        
        # Reset task state
        self.task_active = False
        self.solder_preheating = False
    
    def toggle_auto_mode(self):
        """Toggle automatic mode"""
        if self.state == SystemState.AUTO_MODE:
            self.state = SystemState.READY
            self.send_command("MODE:MANUAL")
            logger.info("Switched to MANUAL mode")
        else:
            self.state = SystemState.AUTO_MODE
            self.send_command("MODE:AUTO")
            logger.info("Switched to AUTO mode")
    
    def toggle_teaching_mode(self):
        """Toggle teaching mode"""
        if self.state == SystemState.TEACHING_MODE:
            self.send_command("TEACH_STOP")
            self.state = SystemState.READY
            logger.info("Teaching mode stopped")
        else:
            self.send_command("TEACH_START")
            self.state = SystemState.TEACHING_MODE
            self.recording_session = True
            logger.info("Teaching mode started")
    
    def trigger_emergency_stop(self):
        """Trigger emergency stop"""
        self.emergency_stop = True
        self.state = SystemState.EMERGENCY_STOP
        self.send_command("DIS")
        logger.warning("EMERGENCY STOP TRIGGERED")
    
    def shutdown(self):
        """Cleanup and shutdown"""
        logger.info("Shutting down APEX_PREDATOR_ENGINE...")
        
        self.is_running = False
        
        # Disable motors and heater
        if self.serial:
            self.send_command("DIS")
            self.send_command("HEAT_OFF")
            time.sleep(0.5)
            self.serial.close()
        
        # Release camera
        if self.camera:
            self.camera.release()
        
        # Close windows
        cv2.destroyAllWindows()
        
        logger.info("✓ Shutdown complete")

# ═══════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def main():
    print("""
    ╔══════════════════════════════════════════════╗
    ║                                              ║
    ║       █████╗ ██████╗ ███████╗██╗  ██╗       ║
    ║      ██╔══██╗██╔══██╗██╔════╝╚██╗██╔╝       ║
    ║      ███████║██████╔╝█████╗   ╚███╔╝        ║
    ║      ██╔══██║██╔═══╝ ██╔══╝   ██╔██╗        ║
    ║      ██║  ██║██║     ███████╗██╔╝ ██╗       ║
    ║      ╚═╝  ╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝       ║
    ║                                              ║
    ║         PREDATOR_ENGINE v1.0                 ║
    ║     AI-Powered Vision & Control System      ║
    ║                                              ║
    ╚══════════════════════════════════════════════╝
    """)
    
    engine = ApexPredatorEngine()
    engine.run()

if __name__ == "__main__":
    main()
