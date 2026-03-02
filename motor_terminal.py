"""
APEX_PREDATOR - Motor Command Terminal v2.1
Quick serial terminal for testing motors directly.

FIX LOG v2.1:
  BUG 1: J1:45 format sent raw → firmware ignores it (silent fail)
         FIX: Parser converts J1:45 → <MOVE X45.0 Y0.0 Z0.0>

  BUG 2: bare except: break in reader thread → silent disconnect
         FIX: Logs the error before breaking

  BUG 3: No stop_event → thread cannot be cleanly stopped
         FIX: stop_event added, passed to reader thread
"""

import serial
import time
import threading

# ── CONFIG ──────────────────────────────────────────────────────
PORT      = 'COM12'
BAUD_RATE = 115200
# ────────────────────────────────────────────────────────────────

# Track current angles so single-joint commands don't reset others
_current = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}

# ── READER THREAD ────────────────────────────────────────────────

def read_from_arduino(ser, stop_event):
    """Background thread — reads Arduino replies continuously."""
    while not stop_event.is_set():
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                if line:
                    print(f"\n  >> {line}")
        except Exception as e:
            # FIX BUG 2: was bare except: break — now logs before stopping
            print(f"\n  !! Reader thread error: {e}")
            break
        time.sleep(0.01)

# ── COMMAND PARSER ───────────────────────────────────────────────

def parse(raw):
    """
    Convert user input to firmware-format command.

    Input              →  Sent to Arduino
    J1:45              →  <MOVE X45.0 Y0.0 Z0.0>
    J2:-30             →  <MOVE X0.0 Y-30.0 Z0.0>
    J3:90              →  <MOVE X0.0 Y0.0 Z90.0>
    <MOVE X45 Y0 Z0>   →  sent as-is
    HOME               →  HOME
    EN / DIS           →  EN / DIS
    LOCK / UNLOCK      →  LOCK / UNLOCK
    """
    cmd = raw.strip().upper()

    # Pass-through commands
    if cmd in ('EN', 'DIS', 'HOME', 'LOCK', 'UNLOCK',
               'MOTORS_EN', 'MOTORS_DIS', 'TOOL_ID'):
        return cmd

    # Already full MOVE format
    if cmd.startswith('<MOVE'):
        return cmd

    # FIX BUG 1: J1:45 shorthand → <MOVE X Y Z> format
    if cmd.startswith('J') and ':' in cmd:
        try:
            joint_str, angle_str = cmd[1:].split(':')
            joint = int(joint_str)
            angle = float(angle_str)
            axis_map = {1: 'X', 2: 'Y', 3: 'Z'}
            if joint not in axis_map:
                print(f"  ✗ Joint {joint} invalid. Use J1, J2, or J3.")
                return None
            _current[axis_map[joint]] = angle
            return (f"<MOVE "
                    f"X{_current['X']:.1f} "
                    f"Y{_current['Y']:.1f} "
                    f"Z{_current['Z']:.1f}>")
        except ValueError:
            print("  ✗ Bad format. Example: J1:45  J2:-30")
            return None

    print(f"  ✗ Unknown command: {cmd}")
    return None

# ── MAIN ─────────────────────────────────────────────────────────

def main():
    print(f"Connecting to APEX_PREDATOR on {PORT}...")

    try:
        ser = serial.Serial(PORT, BAUD_RATE, timeout=0.1)
        time.sleep(2)
        print("Connected!\n")

        # FIX BUG 3: stop_event for clean thread shutdown
        stop_event = threading.Event()
        reader = threading.Thread(
            target=read_from_arduino,
            args=(ser, stop_event),
            daemon=True
        )
        reader.start()

        print("=" * 50)
        print("  APEX MOTOR COMMAND TERMINAL v2.1")
        print("=" * 50)
        print("  EN           - Enable motors")
        print("  DIS          - Disable motors")
        print("  J1:45        - Move Joint 1 (Base) to 45°")
        print("  J2:30        - Move Joint 2 (Shoulder) to 30°")
        print("  J3:-45       - Move Joint 3 (Elbow) to -45°")
        print("  HOME         - Home all joints (~30s, blocking)")
        print("  LOCK         - Lock ATC (4 servos)")
        print("  UNLOCK       - Unlock ATC")
        print("  <MOVE X Y Z> - Raw move command")
        print("  Q            - Quit")
        print("=" * 50)
        print("\nNote: J commands keep other joints at their current angle.\n")

        while True:
            try:
                raw = input("Command: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not raw:
                continue

            if raw.upper() == 'Q':
                print("Disabling motors...")
                ser.write(b"DIS\n")
                time.sleep(0.5)
                break

            if raw.upper() == 'HOME':
                print("  Homing started — waiting for OK (up to 60s)...")

            cmd = parse(raw)
            if cmd is None:
                continue

            ser.write(f"{cmd}\n".encode('utf-8'))
            print(f"  Sent: {cmd}")

    except serial.SerialException as e:
        print(f"\nConnection error: {e}")
        print("Check:")
        print("  1. Arduino plugged in?")
        print("  2. Correct PORT set at top of this file?")
        print("  3. Arduino Serial Monitor closed?")

    finally:
        stop_event.set()
        if 'ser' in locals() and ser.is_open:
            ser.close()
        print("Connection closed.")

if __name__ == "__main__":
    main()
