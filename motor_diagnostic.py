"""
Motor Diagnostic Tool - Helps identify which motor is connected to which pin
Run this to figure out the correct joint-to-motor mapping
"""

import serial
import time
import threading

PORT = 'COM12'
BAUD_RATE = 115200

def read_from_arduino(ser):
    """Background thread to constantly read replies from Arduino"""
    while True:
        try:
            if ser.in_waiting > 0:
                response = ser.readline().decode('utf-8').strip()
                if response:
                    print(f"  >> {response}")
        except:
            break

def test_pin(ser, pin_name, angle=45):
    """Test a specific pin"""
    print(f"\n{'='*60}")
    print(f"Testing PIN: {pin_name} (Moving to {angle}°)")
    print(f"{'='*60}")
    print(f"Watch which MOTOR MOVES when testing {pin_name}")
    print(f"It should be one of:")
    print(f"  - Motor 1 (connected to J1)")
    print(f"  - Motor 2 (connected to J2) - Already working?")
    print(f"  - Motor 3 (connected to J3)")
    print(f"  - Motor 4 (connected to J4)")
    print()
    
    # Send command
    command = f"{pin_name}:{angle}"
    ser.write(f"{command}\n".encode('utf-8'))
    print(f"Command sent: {command}")
    time.sleep(0.5)

def main():
    print("\n" + "="*60)
    print("  APEX_PREDATOR MOTOR DIAGNOSTIC TOOL")
    print("="*60)
    print("\nThis tool will help identify which motor is on which pin.")
    print("You need to:")
    print("  1. Watch which physical motor moves")
    print("  2. Tell me which motor moved for each test")
    print("  3. I'll create the correct mapping in config.json")
    print("\n" + "="*60 + "\n")
    
    try:
        print(f"Connecting to Arduino on {PORT}...")
        ser = serial.Serial(PORT, BAUD_RATE, timeout=0.1)
        time.sleep(2)
        print("✓ Connected!\n")
        
        # Start background reader
        reader_thread = threading.Thread(target=read_from_arduino, args=(ser,), daemon=True)
        reader_thread.start()
        time.sleep(0.5)
        
        # Step 1: Enable motors
        print("Step 1: Enabling all motors...")
        ser.write(b"EN\n")
        time.sleep(1)
        
        # Step 2: Test X-axis (J13)
        print("\n\nStep 2: Testing X-AXIS (J13)")
        test_pin(ser, "J13", 45)
        time.sleep(1)
        ser.write(b"J13:0\n")
        time.sleep(0.5)
        
        motor_j13 = input("\nWhich motor moved? (1, 2, 3, or 4): ").strip()
        
        # Step 3: Test Y-axis (J15)
        print("\n\nStep 3: Testing Y-AXIS (J15)")
        test_pin(ser, "J15", 45)
        time.sleep(1)
        ser.write(b"J15:0\n")
        time.sleep(0.5)
        
        motor_j15 = input("\nWhich motor moved? (1, 2, 3, or 4): ").strip()
        
        # Step 4: Test Z-axis (J17)
        print("\n\nStep 4: Testing Z-AXIS (J17)")
        test_pin(ser, "J17", 45)
        time.sleep(1)
        ser.write(b"J17:0\n")
        time.sleep(0.5)
        
        motor_j17 = input("\nWhich motor moved? (1, 2, 3, or 4): ").strip()
        
        # Print results
        print("\n" + "="*60)
        print("  DIAGNOSTIC RESULTS")
        print("="*60)
        print(f"\nJ13 (X-axis) → Motor {motor_j13}")
        print(f"J15 (Y-axis) → Motor {motor_j15}")
        print(f"J17 (Z-axis) → Motor {motor_j17}")
        
        # Now test GUI sliders to get full mapping
        print("\n" + "="*60)
        print("  TESTING GUI SLIDERS")
        print("="*60)
        print("\nNow we need to test the GUI sliders to see which slider")
        print("maps to which motor.")
        print("\nPlease:")
        print("  1. Start the GUI: python apex_predator_gui.py")
        print("  2. Use each slider in the 'Manual Joint Control' panel")
        print("  3. Tell me which motor moved for each slider")
        
        slider_j1 = input("\nSlider J1 moves which motor? (1, 2, 3, or 4): ").strip()
        slider_j2 = input("Slider J2 moves which motor? (1, 2, 3, or 4): ").strip()
        slider_j3 = input("Slider J3 moves which motor? (1, 2, 3, or 4): ").strip()
        slider_j4 = input("Slider J4 moves which motor? (1, 2, 3, or 4): ").strip()
        
        print("\n" + "="*60)
        print("  FINAL MAPPING")
        print("="*60)
        print(f"\nGUI Slider J1 → Motor {slider_j1}")
        print(f"GUI Slider J2 → Motor {slider_j2}")
        print(f"GUI Slider J3 → Motor {slider_j3}")
        print(f"GUI Slider J4 → Motor {slider_j4}")
        
        print(f"\nHardware Mapping:")
        print(f"Motor {motor_j13} → J13 (X-axis)")
        print(f"Motor {motor_j15} → J15 (Y-axis)")
        print(f"Motor {motor_j17} → J17 (Z-axis)")
        
        # Create mapping dictionary
        motor_to_pin = {
            motor_j13: "x_axis",
            motor_j15: "y_axis",
            motor_j17: "z_axis"
        }
        
        joint_mapping = {
            "joint1": motor_to_pin.get(slider_j1, "x_axis"),
            "joint2": motor_to_pin.get(slider_j2, "y_axis"),
            "joint3": motor_to_pin.get(slider_j3, "z_axis"),
            "joint4": motor_to_pin.get(slider_j4, "z_axis"),
        }
        
        print("\n" + "="*60)
        print("  RECOMMENDED CONFIG.JSON MAPPING")
        print("="*60)
        print("\nAdd this to config.json under 'hardware':")
        print(f"""
    "motor_pins": {{
      "x_axis": "J13",
      "y_axis": "J15",
      "z_axis": "J17"
    }},
    "joint_mapping": {{
      "joint1": "{joint_mapping['joint1']}",
      "joint2": "{joint_mapping['joint2']}",
      "joint3": "{joint_mapping['joint3']}",
      "joint4": "{joint_mapping['joint4']}"
    }}
""")
        
        print("\nWould you like me to update config.json automatically? (y/n): ", end="")
        if input().strip().lower() == 'y':
            import json
            with open('config.json', 'r') as f:
                config = json.load(f)
            
            config['hardware']['motor_pins'] = {
                "x_axis": "J13",
                "y_axis": "J15",
                "z_axis": "J17"
            }
            config['hardware']['joint_mapping'] = joint_mapping
            
            with open('config.json', 'w') as f:
                json.dump(config, f, indent=2)
            
            print("✓ config.json updated successfully!")
        
        ser.write(b"DIS\n")  # Disable motors
        ser.close()
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure:")
        print("  - Arduino is connected to COM12")
        print("  - Arduino Serial Monitor is closed")
        print("  - Motors are properly wired")

if __name__ == "__main__":
    main()
