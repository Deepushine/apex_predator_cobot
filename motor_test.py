import serial
import time
import threading

# --- SETUP YOUR PORT HERE ---
PORT = 'COM12'  
BAUD_RATE = 115200

def read_from_arduino(ser):
    """Background thread to constantly read replies from Arduino"""
    while True:
        try:
            if ser.in_waiting > 0:
                response = ser.readline().decode('utf-8').strip()
                if response:
                    print(f"\n>> {response}")
        except:
            break

def main():
    print(f"Connecting to APEX_PREDATOR on {PORT}...")
    try:
        ser = serial.Serial(PORT, BAUD_RATE, timeout=0.1)
        time.sleep(2) # Wait for Arduino to reboot
        print("Connected Successfully!\n")
        
        # Start the background reading thread
        reader_thread = threading.Thread(target=read_from_arduino, args=(ser,), daemon=True)
        reader_thread.start()
        
        print("========================================")
        print("  APEX MOTOR COMMAND TERMINAL")
        print("========================================")
        print("Commands:")
        print("  EN      - Enable and lock all motors")
        print("  DIS     - Disable motors")
        print("  J1:45   - Move Joint 1 to 45 degrees")
        print("  J2:-90  - Move Joint 2 to -90 degrees")
        print("  J3:10   - Move Joint 3 to 10 degrees")
        print("  HOME    - Return all motors to 0")
        print("  Q       - Quit program")
        print("========================================\n")

        while True:
            cmd = input("Command: ").strip().upper()
            if cmd == 'Q':
                ser.write(b"DIS\n") # Disable motors before quitting
                break
            if cmd:
                ser.write(f"{cmd}\n".encode('utf-8'))
                time.sleep(0.1) # Give Arduino a split second to reply
                
    except Exception as e:
        print(f"Error connecting: {e}")
        print("Did you put the correct COM port? Is the Arduino Serial Monitor closed?")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
        print("Connection closed.")

if __name__ == "__main__":
    main()