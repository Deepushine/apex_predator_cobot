"""
APEX PREDATOR - COMMAND & ACKNOWLEDGE DEMO PATH
"""
import serial
import time

# Configuration
SERIAL_PORT = 'COM12'
BAUD_RATE = 115200

def connect_to_brainstem():
    print(f"Connecting to APEX_PREDATOR on {SERIAL_PORT}...")
    try:
        arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
        time.sleep(2) # Wait for Arduino to reboot
        
        # Wait for boot signal
        while True:
            msg = arduino.readline().decode('utf-8').strip()
            if msg == "APEX_READY":
                print("✓ Brainstem Online and Ready.")
                return arduino
    except Exception as e:
        print(f"Connection Failed: {e}")
        return None

def send_and_wait(arduino, command):
    """The Handshake Protocol: Sends command and blocks until 'OK' is received"""
    print(f"TX -> {command}")
    arduino.write(f"{command}\n".encode('utf-8'))
    
    while True:
        if arduino.in_waiting > 0:
            reply = arduino.readline().decode('utf-8').strip()
            if reply:
                print(f"RX <- {reply}")
            if reply == "OK":
                return True
            if "ERR" in reply:
                print("⚠ ERROR ABORTING SCRIPT")
                return False

def run_demo_sequence():
    arduino = connect_to_brainstem()
    if not arduino: return

    print("\n--- INITIATING STARTUP SEQUENCE ---")
    send_and_wait(arduino, "EN")    # Energize coils
    
    print("\n--- INITIATING DOUBLE-TAP HOMING ---")
    send_and_wait(arduino, "HOME")  # Automatically taps switches to find zero

    print("\n--- EXECUTING DEMO PATH ---")
    # Move to 'Ready Stance'
    send_and_wait(arduino, "<MOVE X0 Y45 Z-30>")
    time.sleep(1)

    # Perform a tactical sweep
    send_and_wait(arduino, "<MOVE X90 Y45 Z-30>")
    send_and_wait(arduino, "<MOVE X-90 Y45 Z-30>")
    
    # Return to home
    send_and_wait(arduino, "<MOVE X0 Y0 Z0>")
    
    print("\n--- SEQUENCE COMPLETE ---")
    send_and_wait(arduino, "DIS")   # Power down safely
    arduino.close()

if __name__ == "__main__":
    run_demo_sequence()