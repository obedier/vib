#!/usr/bin/env python3
"""
Allora Yacht Vibration Analysis - WT901BLE68 Sensor
Processes vibration logs and calculates key metrics for shaft monitoring.
"""

import pandas as pd
import numpy as np
import sys
import re
import os
from datetime import datetime
from pathlib import Path

def extract_metadata_from_filename(filename):
    """
    Extract RPM, speed, and notes from filename patterns like:
    - "20250629181931 idle engine .txt"
    - "20250629184710 cruising 1500 rpm 11.5 knots .txt"
    - "20250628113139 port stern 1415 rpm .txt"
    """
    basename = os.path.basename(filename)
    
    # Extract timestamp from filename (first 14 digits)
    timestamp_match = re.search(r'(\d{14})', basename)
    file_timestamp = None
    if timestamp_match:
        try:
            timestamp_str = timestamp_match.group(1)
            file_timestamp = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
        except ValueError:
            pass
    
    # Extract RPM
    rpm_match = re.search(r'(\d+)\s*rpm', basename, re.IGNORECASE)
    rpm = rpm_match.group(1) if rpm_match else None
    
    # Extract speed (knots)
    speed_match = re.search(r'(\d+(?:\.\d+)?)\s*knots?', basename, re.IGNORECASE)
    speed = speed_match.group(1) if speed_match else None
    
    # Extract notes (everything after timestamp, excluding RPM/speed)
    notes_parts = []
    if file_timestamp:
        # Remove timestamp from notes
        notes_text = basename.replace(timestamp_match.group(1), '').strip()
    else:
        notes_text = basename
    
    # Remove RPM and speed from notes
    if rpm:
        notes_text = re.sub(r'\d+\s*rpm', '', notes_text, flags=re.IGNORECASE)
    if speed:
        notes_text = re.sub(r'\d+(?:\.\d+)?\s*knots?', '', notes_text, flags=re.IGNORECASE)
    
    # Clean up notes
    notes_text = re.sub(r'[._-]+', ' ', notes_text).strip()
    notes = notes_text if notes_text else None
    
    return {
        'file_timestamp': file_timestamp,
        'rpm': rpm,
        'speed': speed,
        'notes': notes
    }

def analyze_vibration_data(file_path):
    """
    Analyze vibration data from WT901BLE68 sensor log file.
    Returns calculated metrics and metadata.
    """
    try:
        # Read tab-separated data
        df = pd.read_csv(file_path, sep='\t')
        
        # Parse timestamp column
        df['time'] = pd.to_datetime(df['time'], errors='coerce')
        
        # Drop rows with invalid timestamps
        df = df.dropna(subset=['time'])
        
        if df.empty:
            raise ValueError("No valid data rows found after timestamp parsing")
        
        # Calculate total acceleration magnitude
        df['Acc_total'] = np.sqrt(
            df['AccX(g)']**2 + 
            df['AccY(g)']**2 + 
            df['AccZ(g)']**2
        )
        
        # Calculate statistics
        mean_vib = df['Acc_total'].mean()
        std_vib = df['Acc_total'].std()
        peak_vib = df['Acc_total'].max()
        
        # Calculate sample duration (assuming 30-second samples)
        duration = 30.0  # seconds
        
        # Extract metadata from filename
        metadata = extract_metadata_from_filename(file_path)
        
        return {
            'mean_acc': mean_vib,
            'std_dev': std_vib,
            'peak_acc': peak_vib,
            'sample_count': len(df),
            'duration': duration,
            'file_timestamp': metadata['file_timestamp'],
            'rpm': metadata['rpm'],
            'speed': metadata['speed'],
            'notes': metadata['notes']
        }
        
    except Exception as e:
        raise ValueError(f"Error processing file {file_path}: {str(e)}")

def compare_to_baseline(mean_acc, notes):
    """
    Compare current reading to Allora baselines.
    Returns status and recommendation.
    """
    # Allora-specific baselines
    IDLE_BASELINE = 1.01  # g
    CRUISE_BASELINE = 1.03  # g
    SIGNIFICANT_INCREASE = 0.2  # g
    
    status = "Normal"
    recommendation = "Continue monitoring"
    
    # Determine expected baseline based on notes
    if notes and any(word in notes.lower() for word in ['idle', 'engine']):
        baseline = IDLE_BASELINE
        condition = "idle"
    elif notes and any(word in notes.lower() for word in ['cruise', 'moving', 'knots']):
        baseline = CRUISE_BASELINE
        condition = "cruising"
    else:
        baseline = CRUISE_BASELINE  # Default to cruise baseline
        condition = "unknown"
    
    # Calculate deviation
    deviation = mean_acc - baseline
    
    if abs(deviation) > SIGNIFICANT_INCREASE:
        status = "WARNING"
        if deviation > 0:
            recommendation = f"High vibration detected. Check shaft alignment and propeller balance. {deviation:.3f}g above {condition} baseline."
        else:
            recommendation = f"Unusually low vibration. Verify sensor placement and calibration. {abs(deviation):.3f}g below {condition} baseline."
    elif abs(deviation) > 0.1:
        status = "ATTENTION"
        recommendation = f"Moderate deviation from {condition} baseline ({deviation:+.3f}g). Monitor trend."
    
    return {
        'status': status,
        'baseline': baseline,
        'deviation': deviation,
        'recommendation': recommendation
    }

def log_results(results, log_file="vibration_log.csv"):
    """
    Append results to vibration log CSV file.
    """
    now = datetime.now()
    
    log_entry = {
        'Timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
        'File': results['filename'],
        'File_Timestamp': results['file_timestamp'].strftime('%Y-%m-%d %H:%M:%S') if results['file_timestamp'] else '',
        'Mean_Acc_g': round(results['mean_acc'], 3),
        'Std_Dev_g': round(results['std_dev'], 3),
        'Peak_Acc_g': round(results['peak_acc'], 3),
        'RPM': results['rpm'] or '',
        'Speed_knots': results['speed'] or '',
        'Notes': results['notes'] or '',
        'Status': results['status'],
        'Baseline_g': round(results['baseline'], 3),
        'Deviation_g': round(results['deviation'], 3),
        'Recommendation': results['recommendation']
    }
    
    # Create DataFrame and append to CSV
    log_df = pd.DataFrame([log_entry])
    
    # Check if file exists to determine header
    file_exists = os.path.exists(log_file)
    
    log_df.to_csv(log_file, mode='a', index=False, header=not file_exists)
    
    return log_file

def main():
    """Main function to process vibration log files."""
    if len(sys.argv) != 2:
        print("Usage: python calcvib.py <logfile.txt>")
        print("Example: python calcvib.py 'data/20250629181931 idle engine .txt'")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)
    
    try:
        # Analyze the vibration data
        analysis = analyze_vibration_data(file_path)
        
        # Compare to baseline
        comparison = compare_to_baseline(analysis['mean_acc'], analysis['notes'])
        
        # Combine results
        results = {
            'filename': file_path,
            **analysis,
            **comparison
        }
        
        # Display results
        print("=" * 60)
        print("🚢 ALLORA YACHT VIBRATION ANALYSIS")
        print("=" * 60)
        print(f"📁 File: {os.path.basename(file_path)}")
        print(f"📊 Sample Count: {results['sample_count']:,}")
        print(f"⏱️  Duration: {results['duration']} seconds")
        
        if results['file_timestamp']:
            print(f"🕐 File Timestamp: {results['file_timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        print("\n📈 VIBRATION METRICS:")
        print(f"   Mean Acceleration: {results['mean_acc']:.3f} g")
        print(f"   Standard Deviation: {results['std_dev']:.3f} g")
        print(f"   Peak Acceleration: {results['peak_acc']:.3f} g")
        
        print("\n🔧 OPERATIONAL DATA:")
        if results['rpm']:
            print(f"   Engine RPM: {results['rpm']}")
        if results['speed']:
            print(f"   Speed: {results['speed']} knots")
        if results['notes']:
            print(f"   Notes: {results['notes']}")
        
        print("\n⚠️  STATUS & RECOMMENDATIONS:")
        print(f"   Status: {results['status']}")
        print(f"   Baseline: {results['baseline']:.3f} g ({'idle' if results['baseline'] == 1.01 else 'cruise'})")
        print(f"   Deviation: {results['deviation']:+.3f} g")
        print(f"   Recommendation: {results['recommendation']}")
        
        # Log to CSV
        log_file = log_results(results)
        print(f"\n💾 Results logged to: {log_file}")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()