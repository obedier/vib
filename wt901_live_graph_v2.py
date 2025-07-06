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
import matplotlib.animation as animation
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

TEST_CAPTURE_FILE = "test_capture.json"

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
                print(f"DEBUG: Saving batch of {len(data_batch)} data points", flush=True)
                # Append to existing data or create new file
                existing_data = []
                if os.path.exists(self.data_file):
                    try:
                        with open(self.data_file, 'r') as f:
                            existing_data = json.load(f)
                        print(f"DEBUG: Loaded {len(existing_data)} existing data points", flush=True)
                    except:
                        existing_data = []
                        print(f"DEBUG: No existing data or error loading, starting fresh", flush=True)
                
                # Add new data
                existing_data.extend(data_batch)
                print(f"DEBUG: Total data points after adding batch: {len(existing_data)}", flush=True)
                
                # Keep only last 1000 data points to prevent file bloat
                if len(existing_data) > 1000:
                    existing_data = existing_data[-1000:]
                    print(f"DEBUG: Trimmed to last 1000 data points", flush=True)
                
                with open(self.data_file, 'w') as f:
                    json.dump(existing_data, f)
                print(f"DEBUG: Successfully saved {len(existing_data)} data points to {self.data_file}", flush=True)
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
    
    def __init__(self, test_mode=False):
        self.messenger = FileMessenger()
        self.ble_handler = BLEHandler(self.messenger)
        self.ble_thread = None
        self.test_mode = test_mode
        self.test_data = []
        self.test_data_index = 0
        self.test_start_time = None
        
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
        
        self.showing_historical = False  # Always start in live mode
        self.toggle_button = None
        self.show_status = True  # Status is default view
        self.capturing_test = False
        self.replaying_test = test_mode
        self.data_source_status = 'Live BLE Data' if not test_mode else 'Test Data Replay'
        self.last_snapshot_time = 0  # For periodic logging
        self.reference_lines = []  # Track reference lines for live plot
        self.connected = False  # Track connection status
        
        # Set initial button label
        self.status_button_label = 'Show Historical' if self.show_status else 'Show Status'
        
    def update_button_label(self):
        """Ensure button label reflects current state"""
        if hasattr(self, 'status_button'):
            new_label = 'Show Historical' if self.show_status else 'Show Status'
            self.status_button.label.set_text(new_label)
            print(f"DEBUG: Button label updated to '{new_label}' (show_status={self.show_status})", flush=True)
        
    def load_baseline_data(self):
        """Load historical vibration data for comparison"""
        try:
            if pd.io.common.file_exists('cmd/vibration_log.csv'):
                df = pd.read_csv('cmd/vibration_log.csv')
                df['timestamp'] = pd.to_datetime(df['Timestamp'], format='ISO8601', errors='coerce')
                df['mean_acc'] = df['Mean Acc (g)']
                self.baseline_data = df
                print(f"Loaded {len(df)} historical readings", flush=True)
            else:
                print("No historical data found - using default baselines", flush=True)
                self.baseline_data = None
        except Exception as e:
            print(f"Error loading baseline data: {e}", flush=True)
            self.baseline_data = None
    
    async def connect_to_device(self, device):
        try:
            print(f"Connecting to {device.address}...", flush=True)
            self.data_source_status = f'Live BLE Data: {device.name} ({device.address})'
            self.update_data_source_status()
            # Here you would start BLE connection and data streaming logic
            # For now, just simulate connection
            print("Connected! Receiving data...", flush=True)
            return True
        except Exception as e:
            print(f"Connection failed: {e}", flush=True)
            self.data_source_status = 'Test Data Replay'
            self.update_data_source_status()
            self.replaying_test = True
            self.load_test_data()
            return False

    def setup_plot(self):
        plt.style.use('default')
        self.fig, self.axes = plt.subplots(2, 2, figsize=(15, 10))
        self.fig.patch.set_facecolor('white')
        for row in self.axes:
            for ax in row:
                ax.set_facecolor('white')
        self.fig.suptitle('Allora Yacht - Live Vibration Monitor v2 (WT901BLE68)', 
                         fontsize=16, fontweight='bold')
        # Add data source status indicator at the top
        self.status_text_top = self.fig.text(0.5, 0.97, f'Data Source: {self.data_source_status}', ha='center', va='top', fontsize=12, color='blue')
        # Add buttons along the top (smaller height)
        ax_status = self.fig.add_axes([0.05, 0.92, 0.15, 0.04])
        # Ensure button label reflects current state
        initial_label = 'Show Historical' if self.show_status else 'Show Status'
        self.status_button = Button(ax_status, initial_label, color='gray', hovercolor='orange')
        self.status_button.on_clicked(self.on_toggle_status)
        ax_capture = self.fig.add_axes([0.22, 0.92, 0.15, 0.04])
        self.capture_button = Button(ax_capture, 'Capture Test Data', color='gray', hovercolor='orange')
        self.capture_button.on_clicked(self.on_capture_test_data)
        ax_replay = self.fig.add_axes([0.39, 0.92, 0.15, 0.04])
        self.replay_button = Button(ax_replay, 'Replay Test Data', color='gray', hovercolor='orange')
        self.replay_button.on_clicked(self.on_replay_test_data)
        # Initialize all status text elements in lower right
        ax4 = self.axes[1, 1]
        ax4.set_title('Status & Alerts', fontweight='bold')
        ax4.axis('off')
        self.lines = {}
        self.lines['status_text'] = ax4.text(0.1, 0.8, 'Connecting...', fontsize=16, 
                                            transform=ax4.transAxes, color='orange', fontweight='bold')
        self.lines['current_val'] = ax4.text(0.1, 0.6, '', fontsize=14, 
                                            transform=ax4.transAxes, color='black', fontweight='bold')
        self.lines['baseline_diff'] = ax4.text(0.1, 0.4, '', fontsize=14, 
                                              transform=ax4.transAxes, color='black', fontweight='bold')
        self.lines['alert'] = ax4.text(0.1, 0.2, '', fontsize=16, fontweight='bold',
                                      transform=ax4.transAxes, color='green')
        self.lines['device_info'] = ax4.text(0.1, 0.95, '', fontsize=12, 
                                            transform=ax4.transAxes, color='blue', fontweight='bold')
        self.lines['packet_count'] = ax4.text(0.1, 0.05, '', fontsize=12, 
                                             transform=ax4.transAxes, color='purple', fontweight='bold')
        # Initialize historical plot elements (initially hidden)
        self.historical_elements = {}
        # Note: Historical elements are now handled directly in update_lower_right()
        # These are kept for compatibility but not actively used
        self.historical_elements['title'] = ax4.text(0.5, 0.95, 'Historical Vibration Log (One Point Per Run)', 
                                                    fontsize=12, fontweight='bold', ha='center', va='top',
                                                    transform=ax4.transAxes, color='black', visible=False)
        self.historical_elements['error_text'] = ax4.text(0.5, 0.5, '', ha='center', va='center', 
                                                         transform=ax4.transAxes, color='red', visible=False)
        # Initialize historical plot lines (empty initially)
        self.historical_lines = {'mean': None, 'peak': None, 'std': None}
        
        # Debug: Print what text elements were created
        print(f"DEBUG: Created {len(self.lines)} text elements: {list(self.lines.keys())}", flush=True)
        
        plt.tight_layout(rect=[0, 0, 0.98, 0.9])
        # Top-left: Live Acceleration plot
        self.lines['acc'], = self.axes[0, 0].plot([], [], 'b-', label='Acc Total')
        self.axes[0, 0].set_title('Live Acceleration (g)')
        self.axes[0, 0].set_ylabel('g')
        self.axes[0, 0].set_xlabel('Sample')
        self.axes[0, 0].grid(True, alpha=0.3)
        self.axes[0, 0].legend()
        # Set initial y-axis limits for acceleration (typical range for vibration monitoring)
        self.axes[0, 0].set_ylim(0.95, 1.25)
        # Top-right: Rolling Mean & Peak
        self.lines['mean'], = self.axes[0, 1].plot([], [], 'b-', label='Mean')
        self.lines['peak'], = self.axes[0, 1].plot([], [], 'y-', label='Peak')
        self.axes[0, 1].set_title('Rolling Mean & Peak')
        self.axes[0, 1].set_ylabel('g')
        self.axes[0, 1].set_xlabel('Window')
        self.axes[0, 1].grid(True, alpha=0.3)
        self.axes[0, 1].legend()
        # Set initial y-axis limits for mean & peak
        self.axes[0, 1].set_ylim(0.95, 1.25)
        # Bottom-left: Rolling Std Dev
        self.lines['std'], = self.axes[1, 0].plot([], [], 'r-', label='Std Dev')
        self.axes[1, 0].set_title('Rolling Std Dev')
        self.axes[1, 0].set_ylabel('g')
        self.axes[1, 0].set_xlabel('Window')
        self.axes[1, 0].grid(True, alpha=0.3)
        self.axes[1, 0].legend()
        # Set initial y-axis limits for std dev (typically smaller range)
        self.axes[1, 0].set_ylim(0.0, 0.1)

    def on_toggle_status(self, event):
        self.show_status = not self.show_status
        print(f"DEBUG: Toggle button clicked - switching to show_status={self.show_status}", flush=True)
        # Update button label to show what view you can switch TO
        self.update_button_label()
        # Force a complete update of the lower right panel
        self.update_lower_right()
        # Force a redraw to ensure all elements are properly displayed
        self.fig.canvas.draw()
        print(f"DEBUG: Toggle completed - show_status={self.show_status}", flush=True)

    def on_capture_test_data(self, event):
        if not self.capturing_test:
            self.capturing_test = True
            self.capture_button.label.set_text('Capturing...')
            self.capture_test_data()
            self.capture_button.label.set_text('Capture Test Data')
            self.capturing_test = False

    def on_replay_test_data(self, event):
        self.replaying_test = not self.replaying_test
        self.data_source_status = 'Test Data Replay' if self.replaying_test else 'Live BLE Data'
        self.update_data_source_status()
        self.replay_button.label.set_text('Stop Replay' if self.replaying_test else 'Replay Test Data')
        if self.replaying_test:
            self.load_test_data()
        else:
            self.test_data = []
            self.test_data_index = 0
            self.test_start_time = None

    def update_lower_right(self):
        ax = self.axes[1, 1]
        
        if self.show_status:
            ax.clear()  # Clear any previous plot lines, legends, or artifacts
            ax.set_title('Status & Alerts', fontweight='bold')
            ax.axis('off')
            # Re-create status text objects if missing (after ax.clear())
            for key, props in [
                ('status_text', dict(x=0.1, y=0.8, s='Connecting...', fontsize=16, color='orange', fontweight='bold')),
                ('current_val', dict(x=0.1, y=0.6, s='', fontsize=14, color='black', fontweight='bold')),
                ('baseline_diff', dict(x=0.1, y=0.4, s='', fontsize=14, color='black', fontweight='bold')),
                ('alert', dict(x=0.1, y=0.2, s='', fontsize=16, color='green', fontweight='bold')),
                ('device_info', dict(x=0.1, y=0.95, s='', fontsize=12, color='blue', fontweight='bold')),
                ('packet_count', dict(x=0.1, y=0.05, s='', fontsize=12, color='purple', fontweight='bold'))
            ]:
                if key not in self.lines or self.lines[key] not in ax.texts:
                    self.lines[key] = ax.text(props['x'], props['y'], props['s'], fontsize=props['fontsize'],
                                              transform=ax.transAxes, color=props['color'], fontweight=props['fontweight'])
                    print(f"DEBUG: Re-created text object for {key}", flush=True)
            # Hide all historical elements
            for key in self.historical_elements:
                self.historical_elements[key].set_visible(False)
            # Show and update status fields
            for key in ['status_text', 'current_val', 'baseline_diff', 'alert', 'device_info', 'packet_count']:
                if key in self.lines:
                    self.lines[key].set_visible(True)
                    print(f"DEBUG: Made {key} visible", flush=True)
                else:
                    print(f"DEBUG: Warning - {key} not found in self.lines", flush=True)
            print(f"DEBUG: Status panel mode - acc_total length: {len(self.acc_total)}", flush=True)
            print(f"DEBUG: update_lower_right - acc_total length: {len(self.acc_total)}", flush=True)
            if len(self.acc_total) > 0:
                # Update status text fields
                recent_acc = list(self.acc_total)[-30:]
                current_mean = np.mean(recent_acc)
                current_peak = np.max(recent_acc)
                current_std = np.std(recent_acc)
                print(f"DEBUG: update_lower_right - recent_acc: {len(recent_acc)} points, mean={current_mean:.3f}, peak={current_peak:.3f}", flush=True)
                if 'current_val' in self.lines:
                    current_text = f"Current Mean: {current_mean:.3f}g\nCurrent Peak: {current_peak:.3f}g"
                    self.lines['current_val'].set_text(current_text)
                    print(f"DEBUG: Set current_val to: {current_text}", flush=True)
                baseline = 1.01
                diff = current_mean - baseline
                diff_percent = (diff / baseline) * 100
                if 'baseline_diff' in self.lines:
                    baseline_text = f"vs Idle (1.01g): {diff:+.3f}g ({diff_percent:+.1f}%)"
                    self.lines['baseline_diff'].set_text(baseline_text)
                    print(f"DEBUG: Set baseline_diff to: {baseline_text}", flush=True)
                # Device info
                devinfo = f"Device: {self.device_name or 'N/A'}\nMAC: {self.device_mac or 'N/A'}"
                if 'device_info' in self.lines:
                    self.lines['device_info'].set_text(devinfo)
                    print(f"DEBUG: Set device_info to: {devinfo}", flush=True)
                if 'packet_count' in self.lines:
                    packet_text = f"Packets: {self.packet_count}"
                    self.lines['packet_count'].set_text(packet_text)
                    print(f"DEBUG: Set packet_count to: {packet_text}", flush=True)
                # Alert logic
                if 'alert' in self.lines:
                    if current_mean > 1.23:
                        self.lines['alert'].set_text("ALERT: Vibration High!")
                        self.lines['alert'].set_color('red')
                    elif current_mean > 1.03:
                        self.lines['alert'].set_text("Warning: Above Cruise")
                        self.lines['alert'].set_color('orange')
                    else:
                        self.lines['alert'].set_text("")
                        self.lines['alert'].set_color('black')
                if 'status_text' in self.lines:
                    self.lines['status_text'].set_text("")
                    self.lines['status_text'].set_color('black')
                print(f"DEBUG: Status panel updated: mean={current_mean:.3f}, peak={current_peak:.3f}", flush=True)
            else:
                # Not connected yet
                print("DEBUG: update_lower_right - no data, showing 'Connecting...'", flush=True)
                for key in ['current_val', 'baseline_diff', 'device_info', 'packet_count', 'alert']:
                    if key in self.lines:
                        self.lines[key].set_text("")
                        if key == 'alert':
                            self.lines[key].set_color('black')
                if 'status_text' in self.lines:
                    self.lines['status_text'].set_text("Connecting...")
                    self.lines['status_text'].set_color('orange')
                print("DEBUG: Status panel: Connecting...", flush=True)
        else:
            # HISTORICAL PANEL
            ax.clear()
            ax.set_title('Historical Comparison', fontweight='bold')
            ax.set_ylabel('Mean Acceleration (g)')
            ax.set_xlabel('Time')
            ax.grid(True, alpha=0.3)
            for key in ['status_text', 'current_val', 'baseline_diff', 'alert', 'device_info', 'packet_count']:
                self.lines[key].set_visible(False)
            for key in self.historical_elements:
                self.historical_elements[key].set_visible(False)
            import pandas as pd
            log_path = 'cmd/vibration_log.csv'
            has_data = False
            if os.path.exists(log_path):
                try:
                    df = pd.read_csv(log_path)
                    if not df.empty and 'Timestamp' in df.columns and 'Mean Acc (g)' in df.columns:
                        has_data = True
                        df['timestamp'] = pd.to_datetime(df['Timestamp'], format='ISO8601', errors='coerce')
                        df = df.dropna(subset=['timestamp'])
                        if not df.empty:
                            ax.plot(df['timestamp'], df['Mean Acc (g)'], 'o-', color='blue', 
                                   label='Historical Data', markersize=6, linewidth=2)
                            ax.axhline(1.01, color='green', linestyle='--', linewidth=1, 
                                      label='Idle Baseline (1.01g)', alpha=0.7)
                            ax.axhline(1.03, color='orange', linestyle='--', linewidth=1, 
                                      label='Cruise Baseline (1.03g)', alpha=0.7)
                            ax.axhline(1.23, color='red', linestyle='--', linewidth=1, 
                                      label='Warning Threshold (1.23g)', alpha=0.7)
                            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
                            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
                            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
                            ax.legend(loc='upper right')
                            ax.grid(True, alpha=0.3)
                        else:
                            has_data = False
                except Exception as e:
                    print(f"Error loading historical data: {e}", flush=True)
                    has_data = False
            if not has_data:
                ax.text(0.5, 0.5, 'No historical data available', 
                       ha='center', va='center', fontsize=14, color='red', 
                       transform=ax.transAxes, fontweight='bold')
                ax.text(0.5, 0.4, 'Historical data will appear here\nwhen vibration logs are captured', 
                       ha='center', va='center', fontsize=10, color='gray', 
                       transform=ax.transAxes)

    def update_plot(self, frame):
        if self.replaying_test:
            self.feed_test_data()
        message = self.messenger.get_message()
        if message:
            self.handle_message(message)
        self.load_latest_data()
        status = self.messenger.get_status()
        self.is_connected = status.get('connected', False)
        self.device_name = status.get('device_name')
        self.device_mac = status.get('device_mac')
        # --- LIVE REFERENCE LINES ---
        ax_live = self.axes[0, 0]
        # Remove previous reference lines
        for ref_line in getattr(self, 'reference_lines', []):
            try:
                ref_line.remove()
            except Exception:
                pass
        self.reference_lines = []
        idle = 1.01
        cruise = 1.03
        warn = 1.23
        # --- MAIN PLOT DATA ---
        if len(self.timestamps) > 0:
            window = min(100, len(self.timestamps))
            recent_times = list(self.timestamps)[-window:]
            recent_acc = list(self.acc_total)[-window:]
            x_data = list(range(len(recent_acc)))
            self.lines['acc'].set_data(x_data, recent_acc)
            if len(recent_acc) > 0:
                # Only update y-axis limits if data exceeds current bounds
                current_ylim = ax_live.get_ylim()
                data_min = min(recent_acc)
                data_max = max(recent_acc)
                
                # Add small margin for better visualization
                margin = 0.02
                new_y_min = data_min - margin
                new_y_max = data_max + margin
                
                # Only update if data exceeds current bounds
                if new_y_min < current_ylim[0] or new_y_max > current_ylim[1]:
                    ax_live.set_ylim(new_y_min, new_y_max)
                
                # Set x-axis limits
                ax_live.set_xlim(0, window)
            print(f"DEBUG: acc plot updated with {len(recent_acc)} points", flush=True)
        # --- END MAIN PLOT DATA ---
        # Add reference lines after main plot line
        self.reference_lines.append(ax_live.axhline(idle, color='blue', linestyle='--', linewidth=1, label='Idle Baseline (1.01g)'))
        self.reference_lines.append(ax_live.axhline(cruise, color='orange', linestyle='--', linewidth=1, label='Cruise Baseline (1.03g)'))
        self.reference_lines.append(ax_live.axhline(warn, color='red', linestyle='--', linewidth=1, label='Warning Threshold (1.23g)'))
        # Ensure main plot line is present
        if self.lines['acc'] not in ax_live.lines:
            ax_live.add_line(self.lines['acc'])
            print("DEBUG: Re-added main plot line to axes", flush=True)
        handles, labels = ax_live.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax_live.legend(by_label.values(), by_label.keys())
        # --- END LIVE REFERENCE LINES ---
        # --- ROLLING MEAN & PEAK ---
        ax_mean = self.axes[0, 1]
        if len(self.acc_total) > 0:
            window = min(100, len(self.acc_total))
            win_size = 30
            means = []
            peaks = []
            x_vals = []
            acc_list = list(self.acc_total)[-window:]
            alpha = 0.2  # EMA smoothing factor
            ema_mean = None
            for i in range(window - win_size + 1):
                win = acc_list[i:i+win_size]
                mean = np.mean(win)
                peak = np.max(win)
                if ema_mean is None:
                    ema_mean = mean
                else:
                    ema_mean = alpha * mean + (1 - alpha) * ema_mean
                means.append(ema_mean)
                peaks.append(peak)
                x_vals.append(i + win_size // 2)
            self.lines['mean'].set_data(x_vals, means)
            self.lines['peak'].set_data(x_vals, peaks)
            if means and peaks:
                ax_mean.set_xlim(0, window)
                
                # Only update y-axis limits if data exceeds current bounds
                current_ylim = ax_mean.get_ylim()
                data_min = min(means + peaks)
                data_max = max(means + peaks)
                
                # Add small margin for better visualization
                margin = 0.02
                new_y_min = data_min - margin
                new_y_max = data_max + margin
                
                # Only update if data exceeds current bounds
                if new_y_min < current_ylim[0] or new_y_max > current_ylim[1]:
                    ax_mean.set_ylim(new_y_min, new_y_max)

        # --- ROLLING STD DEV ---
        ax_std = self.axes[1, 0]
        if len(self.acc_total) > 0:
            window = min(100, len(self.acc_total))
            win_size = 30
            stds = []
            x_vals = []
            acc_list = list(self.acc_total)[-window:]
            alpha = 0.2
            ema_std = None
            for i in range(window - win_size + 1):
                win = acc_list[i:i+win_size]
                std = np.std(win)
                if ema_std is None:
                    ema_std = std
                else:
                    ema_std = alpha * std + (1 - alpha) * ema_std
                stds.append(ema_std)
                x_vals.append(i + win_size // 2)
            self.lines['std'].set_data(x_vals, stds)
            if stds:
                ax_std.set_xlim(0, window)
                
                # Only update y-axis limits if data exceeds current bounds
                current_ylim = ax_std.get_ylim()
                data_min = min(stds)
                data_max = max(stds)
                
                # Add small margin for better visualization
                margin = 0.01
                new_y_min = data_min - margin
                new_y_max = data_max + margin
                
                # Only update if data exceeds current bounds
                if new_y_min < current_ylim[0] or new_y_max > current_ylim[1]:
                    ax_std.set_ylim(new_y_min, new_y_max)

        # --- PERIODIC HISTORICAL SNAPSHOT ---
        now = time.time()
        if now - self.last_snapshot_time > 30 and len(self.acc_total) > 10:
            mean = float(np.mean(self.acc_total))
            std = float(np.std(self.acc_total))
            peak = float(np.max(self.acc_total))
            ts = datetime.now().isoformat()
            log_path = 'cmd/vibration_log.csv'
            import csv, os
            write_header = not os.path.exists(log_path)
            with open(log_path, 'a', newline='') as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(['Timestamp', 'Mean Acc (g)', 'Std Dev (g)', 'Peak Acc (g)'])
                writer.writerow([ts, mean, std, peak])
            self.last_snapshot_time = now
        # --- END HISTORICAL SNAPSHOT ---
        # --- STATUS PANEL ALWAYS SHOWS DETAILS ---
        # REMOVED: Redundant status panel update from update_plot
        # Status panel is now only updated in update_lower_right() below
        # --- END STATUS PANEL DETAILS ---
        self.update_lower_right()
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
            print(f"DEBUG: load_latest_data - loaded {len(latest_data)} points from file", flush=True)
            if latest_data:
                print(f"DEBUG: load_latest_data - first data point: {latest_data[0]}", flush=True)
                print(f"DEBUG: load_latest_data - last data point: {latest_data[-1]}", flush=True)
            else:
                print(f"DEBUG: load_latest_data - no data loaded from file", flush=True)
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
                    print(f"DEBUG: load_latest_data - error parsing data_point: {data_point}, error: {e}", flush=True)
                    continue
            # Set connected True if we have data
            if len(self.acc_total) > 0:
                if not self.connected:
                    print("DEBUG: Connection established, data received.", flush=True)
                self.connected = True
            print(f"DEBUG: Processed {len(self.acc_total)} data points into local storage", flush=True)
            if len(self.acc_total) > 0:
                print(f"DEBUG: Latest acc_total value: {self.acc_total[-1]:.4f}g", flush=True)
        except Exception as e:
            print(f"Error loading latest data: {e}", flush=True)
            import traceback
            traceback.print_exc()
    
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

    def load_test_data(self):
        try:
            with open(TEST_CAPTURE_FILE, 'r') as f:
                self.test_data = json.load(f)
        except Exception as e:
            print(f"No test data found: {e}", flush=True)
            self.test_data = []
        self.test_data_index = 0
        self.test_start_time = None

    def feed_test_data(self):
        if not self.test_data:
            self.load_test_data()
        if not self.test_data:
            return
        now = time.time()
        if self.test_start_time is None:
            self.test_start_time = now
        elapsed = now - self.test_start_time
        idx = int((elapsed * len(self.test_data)) / 60) % len(self.test_data)
        data_point = self.test_data[idx]
        self.timestamps.append(datetime.fromisoformat(data_point['timestamp']))
        self.acc_data.append([data_point['acc_x'], data_point['acc_y'], data_point['acc_z']])
        self.acc_total.append(data_point['acc_total'])

    def capture_test_data(self):
        print("Capturing 1 minute of data for test mode...", flush=True)
        captured = []
        start = time.time()
        while time.time() - start < 60:
            if len(self.acc_total) > 0:
                captured.append({
                    'timestamp': datetime.now().isoformat(),
                    'acc_x': self.acc_data[-1][0],
                    'acc_y': self.acc_data[-1][1],
                    'acc_z': self.acc_data[-1][2],
                    'acc_total': self.acc_total[-1]
                })
            time.sleep(0.05)
        with open(TEST_CAPTURE_FILE, 'w') as f:
            json.dump(captured, f)
        print(f"Saved {len(captured)} samples to {TEST_CAPTURE_FILE}", flush=True)

    def update_data_source_status(self):
        if hasattr(self, 'status_text_top'):
            self.status_text_top.set_text(f'Data Source: {self.data_source_status}')
            self.fig.canvas.draw_idle()

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
    monitor.update_button_label()  # Ensure button label is correct after setup
    monitor.update_lower_right()  # Initialize the lower right panel
    
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
        print("No device selected or found. Switching to test data replay mode.", flush=True)
        monitor.replaying_test = True
        monitor.data_source_status = 'Test Data Replay'
        monitor.update_data_source_status()
        monitor.load_test_data()
    else:
        await monitor.connect_to_device(selected_device)
        monitor.start_ble_thread(selected_device)
    
    monitor.ani = animation.FuncAnimation(monitor.fig, monitor.update_plot, interval=100, blit=False)
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
    parser.add_argument("--test", "-t", action="store_true", help="Test mode: replay 1 min of captured data")
    args = parser.parse_args()
    
    if args.unbuffered:
        sys.stdout.reconfigure(line_buffering=True)
    
    monitor = LiveVibrationMonitor(test_mode=args.test)
    if args.test:
        if not os.path.exists(TEST_CAPTURE_FILE):
            monitor.capture_test_data()
        else:
            print(f"Test mode: Replaying {TEST_CAPTURE_FILE}", flush=True)
        
        # Set up test mode properly
        monitor.replaying_test = True
        monitor.data_source_status = 'Test Data Replay'
        monitor.load_test_data()
        
        monitor.setup_plot()
        monitor.update_button_label()  # Ensure button label is correct after setup
        monitor.update_lower_right()  # Initialize the lower right panel
        monitor.ani = animation.FuncAnimation(monitor.fig, monitor.update_plot, interval=100, blit=False)
        plt.show()
    else:
        asyncio.run(main()) 