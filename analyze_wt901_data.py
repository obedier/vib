#!/usr/bin/env python3
"""
Analyze WT901BLE68 raw BLE data to understand frame structure
"""

import struct
import numpy as np

def analyze_raw_data():
    """Analyze the raw BLE notifications from the WT901BLE68"""
    
    # Sample raw notifications from the console output
    raw_notifications = [
        # First few notifications
        bytes.fromhex("55 61 35 ff 59 ff 0a 08 00 00 00 00 00 00 b9 fc"),
        bytes.fromhex("55 61 31 ff 57 ff 0f 08 00 00 00 00 00 00 b9 fc"),
        bytes.fromhex("55 61 43 ff 5e ff 15 08 00 00 00 00 00 00 b9 fc"),
        
        # Later notifications with more variation
        bytes.fromhex("55 61 e4 03 eb f4 3f 00 7c 02 02 ff 33 00 52 fe"),
        bytes.fromhex("55 61 9c ff c2 ff d0 07 92 fe 7b ff 20 00 29 fe"),
        bytes.fromhex("55 61 22 ff 3a ff 5b 07 43 00 ff ff 02 00 4b fe"),
    ]
    
    print("=== WT901BLE68 Raw Data Analysis ===\n")
    
    for i, data in enumerate(raw_notifications):
        print(f"Notification {i+1}:")
        print(f"  Raw hex: {' '.join(f'{b:02x}' for b in data)}")
        print(f"  Length: {len(data)} bytes")
        print(f"  Header: 0x{data[0]:02x} 0x{data[1]:02x}")
        
        # Check if this looks like a standard WT901 frame
        if data[0] == 0x55 and data[1] == 0x51:
            print("  -> Standard WT901 IMU frame (0x55 0x51)")
            if len(data) >= 11:
                # Parse as standard 11-byte frame
                acc_x = struct.unpack('<h', data[2:4])[0] / 32768.0 * 16
                acc_y = struct.unpack('<h', data[4:6])[0] / 32768.0 * 16
                acc_z = struct.unpack('<h', data[6:8])[0] / 32768.0 * 16
                temp = struct.unpack('<h', data[8:10])[0] / 340.0 + 36.53
                print(f"    AccX: {acc_x:.3f}g, AccY: {acc_y:.3f}g, AccZ: {acc_z:.3f}g")
                print(f"    Temp: {temp:.1f}°C")
        elif data[0] == 0x55 and data[1] == 0x61:
            print("  -> Extended WT901 frame (0x55 0x61) - 160 bytes expected")
            print("  -> This appears to be a multi-frame or packed format")
            
            # Try to extract acceleration data from different positions
            print("  -> Attempting to extract acceleration data...")
            
            # Method 1: Look for 16-bit values that could be acceleration
            for pos in range(2, min(14, len(data)), 2):
                if pos + 1 < len(data):
                    val = struct.unpack('<h', data[pos:pos+2])[0]
                    acc_g = val / 32768.0 * 16  # Standard WT901 scaling
                    print(f"    Pos {pos}-{pos+1}: {val} -> {acc_g:.3f}g")
            
            # Method 2: Check if this is a packed format with multiple readings
            if len(data) == 16:  # 160 bytes would be 10 frames of 16 bytes each
                print("  -> 16-byte frame - may contain multiple sensor readings")
                
        print()
    
    print("=== Analysis Summary ===")
    print("1. Device is sending 0x55 0x61 frames (not standard 0x55 0x51)")
    print("2. Each notification appears to be 16 bytes (not 160 as initially thought)")
    print("3. This suggests the device is in a different output mode")
    print("4. Need to decode the 0x61 frame format or change device output mode")
    print("\n=== Next Steps ===")
    print("1. Check WT901BLE68 documentation for 0x61 frame format")
    print("2. Try sending configuration commands to switch to 0x51 mode")
    print("3. Or decode the 0x61 format if documented")

def check_wt901_documentation():
    """Reference information from WT901 documentation"""
    print("\n=== WT901 Frame Format Reference ===")
    print("Standard WT901 frames:")
    print("  0x55 0x51 - IMU data (11 bytes)")
    print("  0x55 0x52 - Quaternion data")
    print("  0x55 0x53 - GPS data")
    print("  0x55 0x54 - Pressure data")
    print("  0x55 0x55 - Temperature data")
    print("  0x55 0x56 - Magnetic field data")
    print("  0x55 0x57 - Angular velocity data")
    print("  0x55 0x58 - Angle data")
    print("  0x55 0x59 - GPS accuracy data")
    print("  0x55 0x5A - GPS location data")
    print("  0x55 0x5B - GPS speed data")
    print("  0x55 0x5C - GPS time data")
    print("  0x55 0x5D - GPS date data")
    print("  0x55 0x5E - GPS satellites data")
    print("  0x55 0x5F - GPS status data")
    print("  0x55 0x60 - GPS altitude data")
    print("  0x55 0x61 - Extended data format (not standard)")
    print("\nNote: 0x61 is not a standard WT901 frame type!")
    print("This suggests the device may be in a custom or extended mode.")

if __name__ == "__main__":
    analyze_raw_data()
    check_wt901_documentation() 