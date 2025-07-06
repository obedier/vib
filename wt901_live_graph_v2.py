#!/usr/bin/env python3
"""
WT901BLE68 Live Vibration Monitor v2 - Background Threading with File Messaging
Connects to WT901BLE68 sensor and displays live vibration data with baseline comparison
Uses background BLE thread and file-based messaging for robust GUI updates
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
import json
import threading
import time
import tempfile
from collections import deque
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

# File-based messaging system
MESSAGE_FILE = "vib_messages.json"
STATUS_FILE = "vib_status.json"
DATA_FILE = "vib_data.json"

class FileMessenger:
    """File-based messaging system for BLE-GUI communication"""
    
    def __init__(self):
        self.message_file = MESSAGE_FILE
        self.status_file = STATUS_FILE
        self.data_file = DATA_FILE
        self.lock = threading.Lock()
    
    def send_message(self, message_type, data):
        """Send a message to the GUI thread"""
        with self.lock:
            message = {
                'timestamp': datetime.now().isoformat(),
                'type': message_type,
                'data': data
            }
            try:
                with open(self.message_file, 'w') as f:
                    json.dump(message, f)
            except Exception as e:
                print(f"Error sending message: {e}", flush=True)
    
    def get_message(self):
        """Get the latest message from BLE thread"""
        with self.lock:
            try:
                if os.path.exists(self.message_file):
                    with open(self.message_file, 'r') as f:
                        message = json.load(f)
                    # Delete the message after reading
                    os.remove(self.message_file)
                    return message
            except Exception as e:
                print(f"Error reading message: {e}", flush=True)
        return None
    
    def update_status(self, status_data):
        """Update connection status"""
        with self.lock:
            try:
                with open(self.status_file, 'w') as f:
                    json.dump(status_data, f)
            except Exception as e:
                print(f"Error updating status: {e}", flush=True)
    
    def get_status(self):
        """Get current status"""
        with self.lock:
            try:
                if os.path.exists(self.status_file):
                    with open(self.status_file, 'r') as f:
                        return json.load(f)
            except Exception as e:
                print(f"Error reading status: {e}", flush=True)
        return {'connected': False, 'device_name': None, 'device_mac': None}
    
    def save_data_batch(self, data_batch):
        """Save a batch of vibration data"""
        with self.lock:
            try:
                # Append to existing data or create new file
                existing_data = []
                if os.path.exists(self.data_file):
                    try:
                        with open(self.data_file, 'r') as f:
                            existing_data = json.load(f)
                    except:
                        existing_data = []
                
                # Add new data
                existing_data.extend(data_batch)
                
                # Keep only last 1000 data points to prevent file bloat
                if len(existing_data) > 1000:
                    existing_data = existing_data[-1000:]
                
                with open(self.data_file, 'w') as f:
                    json.dump(existing_data, f)
            except Exception as e:
                print(f"Error saving data: {e}", flush=True)
    
    def get_latest_data(self, max_points=100):
        """Get latest vibration data"""
        with self.lock:
            try:
                if os.path.exists(self.data_file):
                    with open(self.data_file, 'r') as f:
                        data = json.load(f)
                    return data[-max_points:] if len(data) > max_points else data
            except Exception as e:
                print(f"Error reading data: {e}", flush=True)
        return []

class BLEHandler:
    """Background BLE handler for WT901BLE68"""
    
    def __init__(self, messenger):
        self.messenger = messenger
        self.client = None
        self.is_running = False
        self.device_name = None
        self.device_mac = None
        self.packet_count = 0
        self.data_batch = []
        self.batch_size = 50  # Send data in batches
    
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
    
    async def data_handler(self, sender, data):
        """Handle incoming BLE data"""
        # Print raw notifications occasionally
        if not hasattr(self, '_notification_count'):
            self._notification_count = 0
        self._notification_count += 1
        
        if self._notification_count % 100 == 0:
            hex_bytes = ' '.join(f'{b:02x}' for b in data[:16])
            print(f"Raw notification {self._notification_count} ({len(data)} bytes): {hex_bytes}", flush=True)
        
        # Frame splitting: Support both 0x55 0x51 (11 bytes) and 0x55 0x61 (16 bytes) formats
        i = 0
        while i < len(data):
            if i + 11 <= len(data) and data[i] == 0x55 and data[i+1] == 0x51:
                # Standard WT901 IMU frame (11 bytes)
                frame = data[i:i+11]
                acc_x, acc_y, acc_z, acc_total = self.parse_wt901_data(frame)
                if acc_total is not None:
                    self.process_acceleration_data(acc_x, acc_y, acc_z, acc_total)
                i += 11
            elif i + 16 <= len(data) and data[i] == 0x55 and data[i+1] == 0x61:
                # Custom WT901BLE68 format (16 bytes)
                frame = data[i:i+16]
                acc_x, acc_y, acc_z, acc_total = self.parse_wt901_data(frame)
                if acc_total is not None:
                    self.process_acceleration_data(acc_x, acc_y, acc_z, acc_total)
                i += 16
            else:
                i += 1
    
    def process_acceleration_data(self, acc_x, acc_y, acc_z, acc_total):
        """Process and store acceleration data"""
        timestamp = datetime.now().isoformat()
        data_point = {
            'timestamp': timestamp,
            'acc_x': acc_x,
            'acc_y': acc_y,
            'acc_z': acc_z,
            'acc_total': acc_total
        }
        
        self.data_batch.append(data_point)
        self.packet_count += 1
        
        # Print every 100th packet
        if self.packet_count % 100 == 0:
            print(f"Packet {self.packet_count}: AccX={acc_x:.4f}g, AccY={acc_y:.4f}g, AccZ={acc_z:.4f}g, Acc_total={acc_total:.4f}g", flush=True)
        
        # Send data batch when it reaches the batch size
        if len(self.data_batch) >= self.batch_size:
            self.messenger.save_data_batch(self.data_batch)
            self.messenger.send_message('data_update', {
                'packet_count': self.packet_count,
                'batch_size': len(self.data_batch)
            })
            self.data_batch = []
    
    async def connect_to_device(self, device):
        """Connect to WT901BLE68 device"""
        try:
            print(f"Connecting to {device.address}...", flush=True)
            self.client = BleakClient(device.address)
            await self.client.connect()
            self.device_name = device.name or 'Unknown'
            self.device_mac = device.address
            
            # Update status
            self.messenger.update_status({
                'connected': True,
                'device_name': self.device_name,
                'device_mac': self.device_mac,
                'connection_time': datetime.now().isoformat()
            })
            
            # Send connection message
            self.messenger.send_message('connected', {
                'device_name': self.device_name,
                'device_mac': self.device_mac
            })
            
            # Try to send start streaming command
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
            
            print("Connected! Receiving data...", flush=True)
            return True
        except Exception as e:
            print(f"Connection failed: {e}", flush=True)
            self.messenger.update_status({
                'connected': False,
                'device_name': None,
                'device_mac': None,
                'error': str(e)
            })
            self.messenger.send_message('connection_failed', {'error': str(e)})
            return False
    
    async def disconnect(self):
        """Disconnect from device"""
        if self.client and self.client.is_connected:
            await self.client.disconnect()
        self.messenger.update_status({
            'connected': False,
            'device_name': None,
            'device_mac': None
        })
        self.messenger.send_message('disconnected', {})
        print("Disconnected", flush=True)
    
    async def run_ble_loop(self, device):
        """Main BLE event loop"""
        self.is_running = True
        try:
            if await self.connect_to_device(device):
                # Keep the connection alive
                while self.is_running:
                    await asyncio.sleep(0.1)
            else:
                self.messenger.send_message('connection_failed', {'error': 'Failed to connect'})
        except Exception as e:
            print(f"BLE loop error: {e}", flush=True)
            self.messenger.send_message('error', {'error': str(e)})
        finally:
            await self.disconnect()
            self.is_running = False

class LiveVibrationMonitor:
    """Main GUI class for live vibration monitoring"""
    
    def __init__(self):
        self.messenger = FileMessenger()
        self.ble_handler = BLEHandler(self.messenger)
        self.ble_thread = None
        
        # Data storage
        self.acc_data = deque(maxlen=1000)
        self.timestamps = deque(maxlen=1000)
        self.acc_total = deque(maxlen=1000)
        self.baseline_data = None
        
        # GUI components
        self.fig, self.axes = None, None
        self.lines = {}
        self.ani = None
        self.root = None
        self.change_device_button = None
        
        # Status
        self.is_connected = False
        self.device_name = None
        self.device_mac = None
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
        self.fig.suptitle('Allora Yacht - Live Vibration Monitor v2 (WT901BLE68)', 
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
    
    def update_plot(self, frame):
        """Update the real-time plots"""
        # Check for messages from BLE thread
        message = self.messenger.get_message()
        if message:
            self.handle_message(message)
        
        # Load latest data from file
        self.load_latest_data()
        
        # Update connection status
        status = self.messenger.get_status()
        self.is_connected = status.get('connected', False)
        self.device_name = status.get('device_name')
        self.device_mac = status.get('device_mac')
        
        # Update status display
        if self.is_connected:
            self.lines['status_text'].set_text("Status: Connected ✓")
            self.lines['status_text'].set_color('green')
            if self.device_name and self.device_mac:
                self.lines['device_info'].set_text(f"Device: {self.device_name} ({self.device_mac})")
            else:
                self.lines['device_info'].set_text("")
        else:
            self.lines['status_text'].set_text("Status: Disconnected ✗")
            self.lines['status_text'].set_color('red')
            self.lines['device_info'].set_text("")

        # Update real-time acceleration plot
        if len(self.timestamps) > 0:
            window = min(100, len(self.timestamps))
            # Convert deques to lists for plotting
            recent_times = list(self.timestamps)[-window:]
            recent_acc = list(self.acc_total)[-window:]
            
            # Use simple x-axis (0 to window-1) for real-time plotting
            x_data = list(range(len(recent_acc)))
            self.lines['acc'].set_data(x_data, recent_acc)
            
            # Update y-axis limits to show data properly
            if len(recent_acc) > 0:
                y_min = min(recent_acc) - 0.02
                y_max = max(recent_acc) + 0.02
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
    
    def handle_message(self, message):
        """Handle messages from BLE thread"""
        msg_type = message.get('type')
        data = message.get('data', {})
        
        if msg_type == 'connected':
            print(f"Connected to {data.get('device_name')} ({data.get('device_mac')})", flush=True)
        elif msg_type == 'disconnected':
            print("Device disconnected", flush=True)
        elif msg_type == 'connection_failed':
            print(f"Connection failed: {data.get('error')}", flush=True)
        elif msg_type == 'data_update':
            self.packet_count = data.get('packet_count', self.packet_count)
            print(f"Data update: {data.get('batch_size')} new points, total packets: {self.packet_count}", flush=True)
        elif msg_type == 'error':
            print(f"BLE error: {data.get('error')}", flush=True)
    
    def load_latest_data(self):
        """Load latest data from file and update local storage"""
        try:
            latest_data = self.messenger.get_latest_data(max_points=200)
            
            # Clear existing data and reload
            self.timestamps.clear()
            self.acc_data.clear()
            self.acc_total.clear()
            
            for data_point in latest_data:
                try:
                    timestamp = datetime.fromisoformat(data_point['timestamp'])
                    self.timestamps.append(timestamp)
                    self.acc_data.append([data_point['acc_x'], data_point['acc_y'], data_point['acc_z']])
                    self.acc_total.append(data_point['acc_total'])
                except Exception as e:
                    print(f"Error processing data point: {e}", flush=True)
                    
        except Exception as e:
            print(f"Error loading latest data: {e}", flush=True)
    
    def start_ble_thread(self, device):
        """Start BLE handler in background thread"""
        def run_ble_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.ble_handler.run_ble_loop(device))
            finally:
                loop.close()
        
        self.ble_thread = threading.Thread(target=run_ble_loop, daemon=True)
        self.ble_thread.start()
        print("BLE thread started", flush=True)
    
    def stop_ble_thread(self):
        """Stop BLE handler thread"""
        if self.ble_handler:
            self.ble_handler.is_running = False
        if self.ble_thread and self.ble_thread.is_alive():
            self.ble_thread.join(timeout=2)
        print("BLE thread stopped", flush=True)
    
    def on_change_device(self, event):
        """Handle device change button click"""
        # Pause animation
        if self.ani:
            self.ani.event_source.stop()
        
        # Stop current BLE thread
        self.stop_ble_thread()
        
        # Scan and select device
        new_device = self.scan_and_select_device()
        if new_device:
            self.start_ble_thread(new_device)
        else:
            print('No device selected.', flush=True)
        
        # Resume animation
        if self.ani:
            self.ani.event_source.start()

    def scan_and_select_device(self):
        """Scan for devices and let user select"""
        print("Scanning for devices...", flush=True)
        try:
            # Run device scan in a separate thread to avoid blocking GUI
            def scan_devices_sync():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    devices = loop.run_until_complete(scan_devices())
                    return devices
                finally:
                    loop.close()
            
            scan_thread = threading.Thread(target=scan_devices_sync, daemon=True)
            scan_thread.start()
            scan_thread.join(timeout=10)
            
            # For now, return the default device
            # In a full implementation, you'd show a dialog here
            return None
            
        except Exception as e:
            print(f"Error scanning devices: {e}", flush=True)
            return None

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
    print("=== Allora Yacht - Live Vibration Monitor v2 ===", flush=True)
    print("Connecting to WT901BLE68 for real-time vibration monitoring...", flush=True)
    print("Using background BLE threading with file-based messaging", flush=True)
    
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
    
    # Start BLE thread
    monitor.start_ble_thread(selected_device)
    
    # Start matplotlib animation
    monitor.ani = FuncAnimation(monitor.fig, monitor.update_plot, interval=100, blit=True)
    
    try:
        plt.show()
    except KeyboardInterrupt:
        print("\nStopping...", flush=True)
    finally:
        monitor.stop_ble_thread()
        # Clean up message files
        for file in [MESSAGE_FILE, STATUS_FILE, DATA_FILE]:
            if os.path.exists(file):
                try:
                    os.remove(file)
                except:
                    pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WT901BLE68 Live Vibration Monitor v2")
    parser.add_argument("--unbuffered", "-u", action="store_true", help="Force unbuffered output (live print)")
    args = parser.parse_args()
    
    if args.unbuffered:
        sys.stdout.reconfigure(line_buffering=True)
    
    asyncio.run(main()) 