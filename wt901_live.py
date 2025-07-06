#!/usr/bin/env python3
"""
Live WT901BLE68 Vibration Monitor (Bluetooth LE)
- Streams real-time accelerometer data from WT901BLE68
- Calculates and prints Acc_total = sqrt(AccX^2 + AccY^2 + AccZ^2)
- Uses bleak (cross-platform BLE library)
"""

import asyncio
import numpy as np
from bleak import BleakScanner, BleakClient
import struct

# WT901BLE68 BLE notify characteristic UUID (usually this for WitMotion BLE)
WT901_NOTIFY_UUID = "0000ffe4-0000-1000-8000-00805f9a34fb"

# Helper: scan for BLE devices and let user pick
async def pick_device():
    print("Scanning for BLE devices (WT901)...")
    devices = await BleakScanner.discover(timeout=5.0)
    for i, d in enumerate(devices):
        print(f"[{i}] {d.name} ({d.address})")
    idx = int(input("Select device number: "))
    return devices[idx].address

# Helper: parse WT901 data frame for AccX, AccY, AccZ (see WT901 protocol)
def parse_wt901_acc(data):
    # WT901 sends 0x55 0x51 ... for acceleration frame (see manual)
    # Each frame: 11 bytes, 0x55 0x51 axL axH ayL ayH azL azH tempL tempH sum
    # Data may be streamed as a sequence of such frames
    # We'll look for 0x55 0x51 and parse the next 8 bytes
    for i in range(len(data) - 10):
        if data[i] == 0x55 and data[i+1] == 0x51:
            ax = struct.unpack('<h', data[i+2:i+4])[0] / 32768 * 16  # g
            ay = struct.unpack('<h', data[i+4:i+6])[0] / 32768 * 16
            az = struct.unpack('<h', data[i+6:i+8])[0] / 32768 * 16
            return ax, ay, az
    return None, None, None

# Notification handler
def handle_notify(sender, data):
    ax, ay, az = parse_wt901_acc(data)
    if ax is not None:
        acc_total = np.sqrt(ax**2 + ay**2 + az**2)
        print(f"AccX: {ax:.3f}g  AccY: {ay:.3f}g  AccZ: {az:.3f}g  |  Acc_total: {acc_total:.3f}g")
    # else: print("No valid acc frame in packet")

async def main():
    print("=== WT901BLE68 Live Vibration Monitor ===")
    mac = input("Enter WT901BLE68 MAC address (or leave blank to scan): ").strip()
    if not mac:
        mac = await pick_device()
    print(f"Connecting to {mac} ...")
    async with BleakClient(mac) as client:
        print("Connected! Subscribing to notifications...")
        await client.start_notify(WT901_NOTIFY_UUID, handle_notify)
        print("Streaming live data. Press Ctrl+C to stop.")
        try:
            while True:
                await asyncio.sleep(0.1)
        except KeyboardInterrupt:
            print("\nStopped.")
        await client.stop_notify(WT901_NOTIFY_UUID)

if __name__ == "__main__":
    asyncio.run(main()) 