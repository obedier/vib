#!/usr/bin/env python3
"""
WT901BLE68 Live Vibration Monitor with Real-time Graphing
Connects to WT901BLE68 sensor and displays live vibration data with baseline comparison
"""

import asyncio
import struct
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from bleak import BleakScanner, BleakClient
import warnings
from matplotlib.widgets import Button
import tkinter as tk
from tkinter import simpledialog
import argparse
import sys
import os
from collections import deque
import queue
warnings.filterwarnings('ignore')

# WT901BLE68 BLE characteristics
WT901_SERVICE_UUID = "0000ffe5-0000-1000-8000-00805f9a34fb"
WT901_CHAR_UUID = "0000ffe4-0000-1000-8000-00805f9a34fb"
WT901_WRITE_CHAR_UUID = "0000ffe9-0000-1000-8000-00805f9a34fb"

# Default device MAC address for Allora yacht
DEFAULT_DEVICE_MAC = "CC726E53-F6B5-6245-D962-948F091FCBFA"

# Baseline values from Allora yacht
IDLE_BASELINE = 1.01  # g
CRUISE_BASELINE = 1.03  # g
WARNING_THRESHOLD = 0.2  # g increase from baseline

class LiveVibrationMonitor:
    def __init__(self):
        self.acc_data = deque(maxlen=1000)  # Thread-safe with max length
        self.timestamps = deque(maxlen=1000)
        self.acc_total = deque(maxlen=1000)
        self.data_queue = queue.Queue()  # Thread-safe queue for new data
        self.baseline_data = None
        self.fig, self.axes = None, None
        self.lines = {}
        self.client = None
        self.is_connected = False
        self.device_name = None
        self.device_mac = None
        self.disconnect_flag = False
        self.change_device_button = None
        self.ani = None
        self.root = None
        self.packet_count = 0
        
    def load_baseline_data(self):
        """Load historical vibration data for comparison"""
        try:
            if pd.io.common.file_exists('cmd/vibration_log.csv'):
                df = pd.read_csv('cmd/vibration_log.csv')
                df['timestamp'] = pd.to_datetime(df['Timestamp'])
                df['mean_acc'] = df['Mean Acc (g)']
                self.baseline_data = df
                print(f"Loaded {len(df)} historical readings", flush=True)
            else:
                print("No historical data found - using default baselines", flush=True)
                self.baseline_data = None
        except Exception as e:
            print(f"Error loading baseline data: {e}", flush=True)
            self.baseline_data = None
    
    def setup_plot(self):
        """Setup the real-time plotting dashboard"""
        plt.style.use('dark_background')
        self.fig, self.axes = plt.subplots(2, 2, figsize=(15, 10))
        self.fig.suptitle('Allora Yacht - Live Vibration Monitor (WT901BLE68)', 
                         fontsize=16, fontweight='bold')
        
        # Plot 1: Real-time acceleration
        ax1 = self.axes[0, 0]
        ax1.set_title('Live Total Acceleration (g)', fontweight='bold')
        ax1.set_ylabel('Acceleration (g)')
        ax1.grid(True, alpha=0.3)
        self.lines['acc'] = ax1.plot([], [], 'g-', linewidth=2, label='Live Acc')[0]
        ax1.axhline(y=IDLE_BASELINE, color='blue', linestyle='--', alpha=0.7, label=f'Idle Baseline ({IDLE_BASELINE}g)')
        ax1.axhline(y=CRUISE_BASELINE, color='orange', linestyle='--', alpha=0.7, label=f'Cruise Baseline ({CRUISE_BASELINE}g)')
        ax1.axhline(y=CRUISE_BASELINE + WARNING_THRESHOLD, color='red', linestyle='--', alpha=0.7, label=f'Warning Threshold ({CRUISE_BASELINE + WARNING_THRESHOLD}g)')
        ax1.legend()
        ax1.set_ylim(0.8, 1.5)
        
        # Plot 2: Rolling statistics
        ax2 = self.axes[0, 1]
        ax2.set_title('Rolling Statistics (Last 50 samples)', fontweight='bold')
        ax2.set_ylabel('Acceleration (g)')
        ax2.grid(True, alpha=0.3)
        self.lines['mean'] = ax2.plot([], [], 'b-', linewidth=2, label='Mean')[0]
        self.lines['std'] = ax2.plot([], [], 'r-', linewidth=2, label='Std Dev')[0]
        self.lines['peak'] = ax2.plot([], [], 'y-', linewidth=2, label='Peak')[0]
        ax2.legend()
        ax2.set_ylim(0.8, 1.5)
        
        # Plot 3: Historical comparison
        ax3 = self.axes[1, 0]
        ax3.set_title('Historical Comparison', fontweight='bold')
        ax3.set_ylabel('Mean Acceleration (g)')
        ax3.set_xlabel('Time')
        ax3.grid(True, alpha=0.3)
        if self.baseline_data is not None:
            ax3.scatter(self.baseline_data['timestamp'], self.baseline_data['mean_acc'], 
                       alpha=0.6, s=30, c='gray', label='Historical')
            ax3.axhline(y=IDLE_BASELINE, color='blue', linestyle='--', alpha=0.7)
            ax3.axhline(y=CRUISE_BASELINE, color='orange', linestyle='--', alpha=0.7)
            ax3.legend()
        self.lines['current'] = ax3.scatter([], [], c='red', s=100, marker='o', label='Current')
        
        # Plot 4: Status and alerts
        ax4 = self.axes[1, 1]
        ax4.set_title('Status & Alerts', fontweight='bold')
        ax4.axis('off')
        self.lines['status_text'] = ax4.text(0.1, 0.8, 'Connecting...', fontsize=14, 
                                            transform=ax4.transAxes, color='yellow')
        self.lines['current_val'] = ax4.text(0.1, 0.6, '', fontsize=12, 
                                            transform=ax4.transAxes, color='white')
        self.lines['baseline_diff'] = ax4.text(0.1, 0.4, '', fontsize=12, 
                                              transform=ax4.transAxes, color='white')
        self.lines['alert'] = ax4.text(0.1, 0.2, '', fontsize=14, fontweight='bold',
                                      transform=ax4.transAxes, color='green')
        self.lines['device_info'] = ax4.text(0.1, 0.95, '', fontsize=10, 
                                            transform=ax4.transAxes, color='cyan')
        self.lines['packet_count'] = ax4.text(0.1, 0.05, '', fontsize=10, 
                                             transform=ax4.transAxes, color='magenta')
        
        # Add Change Device button
        ax_button = self.fig.add_axes([0.8, 0.92, 0.15, 0.06])
        self.change_device_button = Button(ax_button, 'Change Device', color='gray', hovercolor='orange')
        self.change_device_button.on_clicked(self.on_change_device)
        
        plt.tight_layout(rect=[0, 0, 0.98, 0.9])
    
    def parse_wt901_data(self, data):
        """Parse WT901BLE68 acceleration data from BLE packet - supports both 0x51 and 0x61 formats"""
        try:
            if len(data) >= 11 and data[0] == 0x55 and data[1] == 0x51:
                # Standard WT901 IMU frame (11 bytes)
                acc_x = struct.unpack('<h', data[2:4])[0] / 32768.0 * 16  # Convert to g
                acc_y = struct.unpack('<h', data[4:6])[0] / 32768.0 * 16
                acc_z = struct.unpack('<h', data[6:8])[0] / 32768.0 * 16
                
            elif len(data) >= 16 and data[0] == 0x55 and data[1] == 0x61:
                # Custom WT901BLE68 format (16 bytes) - acceleration in positions 2-7
                acc_x = struct.unpack('<h', data[2:4])[0] / 32768.0 * 16
                acc_y = struct.unpack('<h', data[4:6])[0] / 32768.0 * 16
                acc_z = struct.unpack('<h', data[6:8])[0] / 32768.0 * 16
                
            else:
                return None, None, None, None
            
            # Calculate total acceleration
            acc_total = np.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
            
            return acc_x, acc_y, acc_z, acc_total
        except Exception as e:
            print(f"Error parsing data: {e}", flush=True)
        return None, None, None, None
    
    def update_plot(self, frame):
        """Update the real-time plots"""
        # Consume data from queue and add to deques
        queue_size = self.data_queue.qsize()
        if queue_size > 0:
            print(f"Consuming {queue_size} items from queue", flush=True)
        
        while not self.data_queue.empty():
            try:
                data = self.data_queue.get_nowait()
                self.timestamps.append(data['timestamp'])
                self.acc_data.append(data['acc_data'])
                self.acc_total.append(data['acc_total'])
            except queue.Empty:
                break
        
        # Debug: Print data status
        if frame % 10 == 0:  # Print every 10th frame to avoid spam
            print(f"Update frame {frame}: {len(self.timestamps)} timestamps, {len(self.acc_total)} acc values, {self.packet_count} packets", flush=True)
        
        # Always update connection status and device info
        if self.is_connected:
            self.lines['status_text'].set_text("Status: Connected ✓")
            self.lines['status_text'].set_color('green')
            if self.device_name and self.device_mac:
                self.lines['device_info'].set_text(f"Device: {self.device_name} ({self.device_mac})")
            else:
                self.lines['device_info'].set_text("")
        elif self.disconnect_flag:
            self.lines['status_text'].set_text("Status: Disconnected ✗")
            self.lines['status_text'].set_color('red')
            self.lines['device_info'].set_text("")
        else:
            self.lines['status_text'].set_text("Connecting...")
            self.lines['status_text'].set_color('yellow')
            self.lines['device_info'].set_text("")

        # Update real-time acceleration plot
        if len(self.timestamps) > 0:
            window = min(100, len(self.timestamps))
            # Convert deques to lists for slicing
            recent_times = list(self.timestamps)[-window:]
            recent_acc = list(self.acc_total)[-window:]
            
            # Use simple x-axis (0 to window-1) for real-time plotting
            x_data = list(range(len(recent_acc)))
            self.lines['acc'].set_data(x_data, recent_acc)
            
            # Update y-axis limits to show data properly
            if len(recent_acc) > 0:
                y_min = min(recent_acc) - 0.01
                y_max = max(recent_acc) + 0.01
                self.axes[0, 0].set_ylim(y_min, y_max)
            
            self.axes[0, 0].set_xlim(0, len(recent_acc))

        # Update rolling statistics
        if len(self.acc_total) >= 10:
            window = min(50, len(self.acc_total))
            # Convert deque to list for slicing
            recent_data = list(self.acc_total)[-window:]
            means = []
            stds = []
            peaks = []
            for i in range(5, len(recent_data)):
                window_data = recent_data[i-5:i+1]
                means.append(np.mean(window_data))
                stds.append(np.std(window_data))
                peaks.append(np.max(window_data))
            if means:
                x_data = list(range(len(means)))
                self.lines['mean'].set_data(x_data, means)
                self.lines['std'].set_data(x_data, stds)
                self.lines['peak'].set_data(x_data, peaks)
                
                # Update y-axis limits for stats
                all_stats = means + stds + peaks
                if all_stats:
                    y_min = min(all_stats) - 0.01
                    y_max = max(all_stats) + 0.01
                    self.axes[0, 1].set_ylim(y_min, y_max)
                
                self.axes[0, 1].set_xlim(0, len(means))

        # Update status/alerts for vibration only if we have data
        if len(self.acc_total) > 0:
            # Convert deque to list for slicing
            recent_acc = list(self.acc_total)[-10:]
            current_mean = np.mean(recent_acc)
            current_peak = np.max(recent_acc)
            if current_mean < IDLE_BASELINE + 0.05:
                baseline = IDLE_BASELINE
                baseline_name = "Idle"
            else:
                baseline = CRUISE_BASELINE
                baseline_name = "Cruise"
            diff = current_mean - baseline
            diff_percent = (diff / baseline) * 100
            self.lines['current_val'].set_text(f"Current Mean: {current_mean:.3f}g\nCurrent Peak: {current_peak:.3f}g")
            self.lines['baseline_diff'].set_text(f"vs {baseline_name} ({baseline}g): {diff:+.3f}g ({diff_percent:+.1f}%)")
            if abs(diff) > WARNING_THRESHOLD:
                self.lines['alert'].set_text("⚠️ WARNING: High vibration detected!")
                self.lines['alert'].set_color('red')
            elif abs(diff) > WARNING_THRESHOLD * 0.5:
                self.lines['alert'].set_text("⚠️ Caution: Vibration increasing")
                self.lines['alert'].set_color('orange')
            else:
                self.lines['alert'].set_text("✓ Normal vibration levels")
                self.lines['alert'].set_color('green')
        else:
            self.lines['current_val'].set_text("")
            self.lines['baseline_diff'].set_text("")
            self.lines['alert'].set_text("")

        self.lines['packet_count'].set_text(f"Packets received: {self.packet_count}")

        return self.lines.values()
    
    async def data_handler(self, sender, data):
        # Print first 16 bytes as hex and ASCII (only every 50th notification to reduce spam)
        if not hasattr(self, '_notification_count'):
            self._notification_count = 0
        self._notification_count += 1
        
        if self._notification_count % 50 == 0:
            hex_bytes = ' '.join(f'{b:02x}' for b in data[:16])
            ascii_bytes = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in data[:16])
            print(f"Raw notification {self._notification_count} ({len(data)} bytes): {hex_bytes} | ASCII: {ascii_bytes}", flush=True)
        
        # Frame splitting: Support both 0x55 0x51 (11 bytes) and 0x55 0x61 (16 bytes) formats
        i = 0
        while i < len(data):
            if i + 11 <= len(data) and data[i] == 0x55 and data[i+1] == 0x51:
                # Standard WT901 IMU frame (11 bytes)
                frame = data[i:i+11]
                acc_x, acc_y, acc_z, acc_total = self.parse_wt901_data(frame)
                if acc_total is not None:
                    timestamp = datetime.now()
                    # Put data in queue for thread-safe access
                    self.data_queue.put({
                        'timestamp': timestamp,
                        'acc_data': [acc_x, acc_y, acc_z],
                        'acc_total': acc_total
                    })
                    self.packet_count += 1
                    # Only print every 100th packet to reduce console spam
                    if self.packet_count % 100 == 0:
                        print(f"Packet {self.packet_count}: AccX={acc_x:.4f}g, AccY={acc_y:.4f}g, AccZ={acc_z:.4f}g, Acc_total={acc_total:.4f}g", flush=True)
                i += 11
            elif i + 16 <= len(data) and data[i] == 0x55 and data[i+1] == 0x61:
                # Custom WT901BLE68 format (16 bytes)
                frame = data[i:i+16]
                acc_x, acc_y, acc_z, acc_total = self.parse_wt901_data(frame)
                if acc_total is not None:
                    timestamp = datetime.now()
                    # Put data in queue for thread-safe access
                    self.data_queue.put({
                        'timestamp': timestamp,
                        'acc_data': [acc_x, acc_y, acc_z],
                        'acc_total': acc_total
                    })
                    self.packet_count += 1
                    # Only print every 100th packet to reduce console spam
                    if self.packet_count % 100 == 0:
                        print(f"Packet {self.packet_count}: AccX={acc_x:.4f}g, AccY={acc_y:.4f}g, AccZ={acc_z:.4f}g, Acc_total={acc_total:.4f}g", flush=True)
                i += 16
            else:
                i += 1
    
    async def connect_to_device(self, device):
        """Connect to WT901BLE68 device with debug and initialization"""
        try:
            print(f"Connecting to {device.address}...", flush=True)
            self.client = BleakClient(device.address)
            await self.client.connect()
            self.device_name = device.name or 'Unknown'
            self.device_mac = device.address
            # Debug: List all services and characteristics (compatible with bleak versions)
            print("Discovering services and characteristics...", flush=True)
            services = getattr(self.client, 'services', None)
            if services:
                for service in services:
                    print(f"Service: {service.uuid}", flush=True)
                    for char in service.characteristics:
                        print(f"  Char: {char.uuid} | Properties: {char.properties}", flush=True)
            else:
                print("(Could not enumerate services; skipping)", flush=True)
            # Debug: Try to write a 'start streaming' command (0xFF, 0xAA, 0x69) to the write characteristic
            try:
                start_cmd = bytes([0xFF, 0xAA, 0x69])
                await self.client.write_gatt_char(WT901_WRITE_CHAR_UUID, start_cmd)
                print(f"Sent start streaming command to {WT901_WRITE_CHAR_UUID}", flush=True)
            except Exception as e:
                print(f"Write to start streaming failed: {e}", flush=True)
            # Subscribe to notifications
            try:
                await self.client.start_notify(WT901_CHAR_UUID, self.data_handler)
                print(f"Subscribed to notifications on {WT901_CHAR_UUID}", flush=True)
            except Exception as e:
                print(f"Notification subscription failed: {e}", flush=True)
            self.is_connected = True
            self.disconnect_flag = False
            print("Connected! Receiving data...", flush=True)
            return True
        except Exception as e:
            print(f"Connection failed: {e}", flush=True)
            self.is_connected = False
            self.disconnect_flag = True
            return False
    
    async def disconnect(self):
        """Disconnect from device"""
        if self.client and self.client.is_connected:
            await self.client.disconnect()
        self.is_connected = False
        self.disconnect_flag = True
        print("Disconnected", flush=True)

    def on_change_device(self, event):
        # Pause animation
        if self.ani:
            self.ani.event_source.stop()
        # Scan and select device
        new_device = self.scan_and_select_device()
        if new_device:
            asyncio.create_task(self.reconnect_to_device(new_device))
        else:
            print('No device selected.', flush=True)
        if self.ani:
            self.ani.event_source.start()

    def scan_and_select_device(self):
        # Use tkinter for device selection dialog
        loop = asyncio.get_event_loop()
        devices, _ = loop.run_until_complete(scan_devices())
        device_names = [f"{d.name or 'Unknown'} ({d.address})" for _, d in devices]
        if not device_names:
            return None
        # Show dialog
        if not self.root:
            self.root = tk.Tk()
            self.root.withdraw()
        selected = simpledialog.askstring('Select Device', 'Enter device number:\n' + '\n'.join(f"[{i}] {name}" for i, name in enumerate(device_names)))
        if selected is None or not selected.isdigit():
            return None
        idx = int(selected)
        if 0 <= idx < len(devices):
            return devices[idx][1]
        return None

    async def reconnect_to_device(self, device):
        await self.disconnect()
        await self.connect_to_device(device)

async def scan_devices():
    """Scan for BLE devices"""
    print("Scanning for BLE devices...", flush=True)
    devices = await BleakScanner.discover()
    
    wt901_devices = []
    default_device = None
    
    for i, device in enumerate(devices):
        # Check for default device by MAC address
        if device.address.upper() == DEFAULT_DEVICE_MAC.upper():
            default_device = (i, device)
            print(f"Found default device: {device.name} ({device.address})", flush=True)
        
        # Check for WT901 devices by name
        if device.name and "WT901" in device.name:
            wt901_devices.append((i, device))
        elif device.name and "WitMotion" in device.name:
            wt901_devices.append((i, device))
        elif device.name and "IMU" in device.name:
            wt901_devices.append((i, device))
    
    # Add default device to list if found
    if default_device and default_device not in wt901_devices:
        wt901_devices.append(default_device)
    
    if not wt901_devices:
        print("No WT901 devices found. Available devices:", flush=True)
        for i, device in enumerate(devices):
            print(f"[{i}] {device.name or 'Unknown'} ({device.address})", flush=True)
        return None
    
    print("WT901 devices found:", flush=True)
    for idx, device in wt901_devices:
        is_default = " (DEFAULT)" if device.address.upper() == DEFAULT_DEVICE_MAC.upper() else ""
        print(f"[{idx}] {device.name} ({device.address}){is_default}", flush=True)
    
    return wt901_devices, default_device

async def main():
    """Main function"""
    print("=== Allora Yacht - Live Vibration Monitor ===", flush=True)
    print("Connecting to WT901BLE68 for real-time vibration monitoring...", flush=True)
    
    # Load baseline data
    monitor = LiveVibrationMonitor()
    monitor.load_baseline_data()
    
    # Setup plotting
    monitor.setup_plot()
    
    # Try to auto-connect to default device
    scan_result = await scan_devices()
    devices, default_device = scan_result if scan_result else ([], None)
    selected_device = None
    if default_device:
        selected_device = default_device[1]
        print(f"Auto-connecting to default device: {selected_device.name} ({selected_device.address})", flush=True)
    elif devices:
        device_idx = int(input("Select device number: "))
        for idx, device in devices:
            if idx == device_idx:
                selected_device = device
                break
    if not selected_device:
        print("No device selected. Exiting.", flush=True)
        return
    if await monitor.connect_to_device(selected_device):
        monitor.ani = FuncAnimation(monitor.fig, monitor.update_plot, interval=100, blit=True)
        try:
            plt.show()
        except KeyboardInterrupt:
            print("\nStopping...", flush=True)
        finally:
            await monitor.disconnect()
    else:
        print("Failed to connect to device.", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WT901BLE68 Live Vibration Monitor")
    parser.add_argument("--unbuffered", "-u", action="store_true", help="Force unbuffered output (live print)")
    args = parser.parse_args()
    if args.unbuffered:
        try:
            sys.stdout.reconfigure(line_buffering=True, write_through=True)
        except Exception:
            os.environ["PYTHONUNBUFFERED"] = "1"
    asyncio.run(main()) 