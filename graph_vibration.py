#!/usr/bin/env python3
"""
Allora Yacht Vibration Graphing Tool
Creates comprehensive visualizations of vibration data.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import re
from datetime import datetime
import os

def load_vibration_data(log_file="vibration_log.csv"):
    """
    Load and prepare vibration data for graphing.
    """
    if not os.path.exists(log_file):
        print(f"❌ Log file not found: {log_file}")
        return None
    
    # Load data
    df = pd.read_csv(log_file)
    
    # Convert timestamps
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df['File_Timestamp'] = pd.to_datetime(df['File_Timestamp'], errors='coerce')
    
    # Convert numeric columns
    df['RPM'] = pd.to_numeric(df['RPM'], errors='coerce')
    df['Speed_knots'] = pd.to_numeric(df['Speed_knots'], errors='coerce')
    
    # Create time-based index
    df = df.sort_values('File_Timestamp')
    
    return df

def create_time_series_plot(df, save_path="vibration_time_series.png"):
    """
    Create time series plot of mean acceleration over time.
    """
    plt.figure(figsize=(15, 8))
    
    # Plot mean acceleration over time
    plt.subplot(2, 1, 1)
    plt.plot(df['File_Timestamp'], df['Mean_Acc_g'], 'o-', linewidth=2, markersize=6, alpha=0.7)
    
    # Add baseline lines
    plt.axhline(y=1.01, color='green', linestyle='--', alpha=0.7, label='Idle Baseline (1.01g)')
    plt.axhline(y=1.03, color='blue', linestyle='--', alpha=0.7, label='Cruise Baseline (1.03g)')
    plt.axhline(y=1.23, color='red', linestyle='--', alpha=0.7, label='Warning Threshold (1.23g)')
    
    # Color points by status
    colors = {'Normal': 'green', 'ATTENTION': 'orange', 'WARNING': 'red'}
    for status in colors:
        mask = df['Status'] == status
        if mask.any():
            plt.scatter(df.loc[mask, 'File_Timestamp'], df.loc[mask, 'Mean_Acc_g'], 
                       c=colors[status], s=100, alpha=0.8, label=f'{status} ({mask.sum()})')
    
    plt.title('🚢 Allora Yacht - Vibration Trends Over Time', fontsize=16, fontweight='bold')
    plt.ylabel('Mean Acceleration (g)', fontsize=12)
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Format x-axis
    plt.xticks(rotation=45)
    
    # Add peak acceleration subplot
    plt.subplot(2, 1, 2)
    plt.plot(df['File_Timestamp'], df['Peak_Acc_g'], 's-', linewidth=2, markersize=6, alpha=0.7, color='purple')
    plt.title('Peak Acceleration Over Time', fontsize=14)
    plt.ylabel('Peak Acceleration (g)', fontsize=12)
    plt.xlabel('Date/Time', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"📊 Time series plot saved: {save_path}")

def create_status_breakdown(df, save_path="vibration_status_breakdown.png"):
    """
    Create pie chart and bar chart of status breakdown.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    # Pie chart
    status_counts = df['Status'].value_counts()
    colors = ['green', 'orange', 'red']
    wedges, texts, autotexts = ax1.pie(status_counts.values, labels=status_counts.index, 
                                       autopct='%1.1f%%', colors=colors[:len(status_counts)],
                                       startangle=90)
    ax1.set_title('Status Distribution', fontsize=14, fontweight='bold')
    
    # Bar chart
    bars = ax2.bar(status_counts.index, status_counts.values, color=colors[:len(status_counts)])
    ax2.set_title('Status Count', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Number of Readings')
    
    # Add value labels on bars
    for bar, value in zip(bars, status_counts.values):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                str(value), ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"📊 Status breakdown saved: {save_path}")

def create_rpm_speed_analysis(df, save_path="vibration_rpm_speed.png"):
    """
    Create scatter plots showing relationship between RPM, speed, and vibration.
    """
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    
    # RPM vs Mean Acceleration
    rpm_data = df[df['RPM'].notna()]
    if not rpm_data.empty:
        colors = {'Normal': 'green', 'ATTENTION': 'orange', 'WARNING': 'red'}
        for status in colors:
            mask = rpm_data['Status'] == status
            if mask.any():
                ax1.scatter(rpm_data.loc[mask, 'RPM'], rpm_data.loc[mask, 'Mean_Acc_g'], 
                           c=colors[status], s=100, alpha=0.7, label=status)
        
        ax1.set_xlabel('Engine RPM')
        ax1.set_ylabel('Mean Acceleration (g)')
        ax1.set_title('RPM vs Mean Acceleration')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
    
    # Speed vs Mean Acceleration
    speed_data = df[df['Speed_knots'].notna()]
    if not speed_data.empty:
        for status in colors:
            mask = speed_data['Status'] == status
            if mask.any():
                ax2.scatter(speed_data.loc[mask, 'Speed_knots'], speed_data.loc[mask, 'Mean_Acc_g'], 
                           c=colors[status], s=100, alpha=0.7, label=status)
        
        ax2.set_xlabel('Speed (knots)')
        ax2.set_ylabel('Mean Acceleration (g)')
        ax2.set_title('Speed vs Mean Acceleration')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
    
    # RPM vs Peak Acceleration
    if not rpm_data.empty:
        for status in colors:
            mask = rpm_data['Status'] == status
            if mask.any():
                ax3.scatter(rpm_data.loc[mask, 'RPM'], rpm_data.loc[mask, 'Peak_Acc_g'], 
                           c=colors[status], s=100, alpha=0.7, label=status)
        
        ax3.set_xlabel('Engine RPM')
        ax3.set_ylabel('Peak Acceleration (g)')
        ax3.set_title('RPM vs Peak Acceleration')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
    
    # Speed vs Peak Acceleration
    if not speed_data.empty:
        for status in colors:
            mask = speed_data['Status'] == status
            if mask.any():
                ax4.scatter(speed_data.loc[mask, 'Speed_knots'], speed_data.loc[mask, 'Peak_Acc_g'], 
                           c=colors[status], s=100, alpha=0.7, label=status)
        
        ax4.set_xlabel('Speed (knots)')
        ax4.set_ylabel('Peak Acceleration (g)')
        ax4.set_title('Speed vs Peak Acceleration')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"📊 RPM/Speed analysis saved: {save_path}")

def create_location_analysis(df, save_path="vibration_location_analysis.png"):
    """
    Create analysis based on location/notes in filenames.
    """
    # Extract location from notes
    df['Location'] = df['Notes'].str.extract(r'(stern|salon|deck|coffee table|shaft)', flags=re.IGNORECASE)
    df['Location'] = df['Location'].fillna('other')
    
    # Group by location
    location_stats = df.groupby('Location').agg({
        'Mean_Acc_g': ['mean', 'std', 'count'],
        'Peak_Acc_g': ['mean', 'max'],
        'Status': lambda x: (x == 'WARNING').sum()
    }).round(3)
    
    # Flatten column names
    location_stats.columns = ['_'.join(col).strip() for col in location_stats.columns]
    
    # Create visualization
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    # Mean acceleration by location
    locations = location_stats.index
    means = location_stats['Mean_Acc_g_mean']
    colors = ['red' if location_stats.loc[loc, 'Status_<lambda>'] > 0 else 'green' for loc in locations]
    
    bars1 = ax1.bar(locations, means, color=colors, alpha=0.7)
    ax1.set_title('Mean Acceleration by Location', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Mean Acceleration (g)')
    ax1.tick_params(axis='x', rotation=45)
    
    # Add value labels
    for bar, value in zip(bars1, means):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01, 
                f'{value:.3f}', ha='center', va='bottom', fontweight='bold')
    
    # Peak acceleration by location
    peaks = location_stats['Peak_Acc_g_mean']
    bars2 = ax2.bar(locations, peaks, color=colors, alpha=0.7)
    ax2.set_title('Peak Acceleration by Location', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Peak Acceleration (g)')
    ax2.tick_params(axis='x', rotation=45)
    
    # Add value labels
    for bar, value in zip(bars2, peaks):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05, 
                f'{value:.3f}', ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"📊 Location analysis saved: {save_path}")
    
    # Print location statistics
    print("\n📍 Location Statistics:")
    print("=" * 50)
    print(location_stats.to_string())

def create_summary_dashboard(df, save_path="vibration_dashboard.png"):
    """
    Create a comprehensive dashboard with key metrics.
    """
    fig = plt.figure(figsize=(20, 12))
    
    # Set up the grid
    gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)
    
    # 1. Time series (top row, spans 3 columns)
    ax1 = fig.add_subplot(gs[0, :3])
    ax1.plot(df['File_Timestamp'], df['Mean_Acc_g'], 'o-', linewidth=2, markersize=6, alpha=0.7)
    ax1.axhline(y=1.01, color='green', linestyle='--', alpha=0.7, label='Idle Baseline')
    ax1.axhline(y=1.03, color='blue', linestyle='--', alpha=0.7, label='Cruise Baseline')
    ax1.set_title('Vibration Trends Over Time', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Mean Acceleration (g)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(axis='x', rotation=45)
    
    # 2. Status pie chart (top right)
    ax2 = fig.add_subplot(gs[0, 3])
    status_counts = df['Status'].value_counts()
    colors = ['green', 'orange', 'red']
    ax2.pie(status_counts.values, labels=status_counts.index, autopct='%1.1f%%', 
            colors=colors[:len(status_counts)], startangle=90)
    ax2.set_title('Status Distribution', fontsize=12, fontweight='bold')
    
    # 3. RPM vs Vibration (middle left)
    ax3 = fig.add_subplot(gs[1, 0])
    rpm_data = df[df['RPM'].notna()]
    if not rpm_data.empty:
        ax3.scatter(rpm_data['RPM'], rpm_data['Mean_Acc_g'], alpha=0.7)
        ax3.set_xlabel('Engine RPM')
        ax3.set_ylabel('Mean Acceleration (g)')
        ax3.set_title('RPM vs Vibration')
        ax3.grid(True, alpha=0.3)
    
    # 4. Speed vs Vibration (middle center)
    ax4 = fig.add_subplot(gs[1, 1])
    speed_data = df[df['Speed_knots'].notna()]
    if not speed_data.empty:
        ax4.scatter(speed_data['Speed_knots'], speed_data['Mean_Acc_g'], alpha=0.7)
        ax4.set_xlabel('Speed (knots)')
        ax4.set_ylabel('Mean Acceleration (g)')
        ax4.set_title('Speed vs Vibration')
        ax4.grid(True, alpha=0.3)
    
    # 5. Peak vs Mean (middle right)
    ax5 = fig.add_subplot(gs[1, 2])
    ax5.scatter(df['Mean_Acc_g'], df['Peak_Acc_g'], alpha=0.7)
    ax5.set_xlabel('Mean Acceleration (g)')
    ax5.set_ylabel('Peak Acceleration (g)')
    ax5.set_title('Peak vs Mean Acceleration')
    ax5.grid(True, alpha=0.3)
    
    # 6. Deviation histogram (bottom left)
    ax6 = fig.add_subplot(gs[2, 0])
    ax6.hist(df['Deviation_g'], bins=10, alpha=0.7, color='skyblue', edgecolor='black')
    ax6.set_xlabel('Deviation from Baseline (g)')
    ax6.set_ylabel('Frequency')
    ax6.set_title('Deviation Distribution')
    ax6.grid(True, alpha=0.3)
    
    # 7. Standard deviation vs mean (bottom center)
    ax7 = fig.add_subplot(gs[2, 1])
    ax7.scatter(df['Mean_Acc_g'], df['Std_Dev_g'], alpha=0.7)
    ax7.set_xlabel('Mean Acceleration (g)')
    ax7.set_ylabel('Standard Deviation (g)')
    ax7.set_title('Variability vs Mean')
    ax7.grid(True, alpha=0.3)
    
    # 8. Summary statistics (bottom right)
    ax8 = fig.add_subplot(gs[2, 2:])
    ax8.axis('off')
    
    # Calculate summary statistics
    total_readings = len(df)
    normal_count = (df['Status'] == 'Normal').sum()
    warning_count = (df['Status'] == 'WARNING').sum()
    attention_count = (df['Status'] == 'ATTENTION').sum()
    
    mean_acc_avg = df['Mean_Acc_g'].mean()
    peak_acc_max = df['Peak_Acc_g'].max()
    deviation_avg = df['Deviation_g'].abs().mean()
    
    summary_text = f"""
    📊 VIBRATION ANALYSIS SUMMARY
    
    Total Readings: {total_readings}
    Normal: {normal_count} ({normal_count/total_readings*100:.1f}%)
    Warnings: {warning_count} ({warning_count/total_readings*100:.1f}%)
    Attention: {attention_count} ({attention_count/total_readings*100:.1f}%)
    
    Average Mean Acceleration: {mean_acc_avg:.3f} g
    Maximum Peak Acceleration: {peak_acc_max:.3f} g
    Average Deviation: {deviation_avg:.3f} g
    
    Date Range: {df['File_Timestamp'].min().strftime('%Y-%m-%d')} to {df['File_Timestamp'].max().strftime('%Y-%m-%d')}
    """
    
    ax8.text(0.05, 0.95, summary_text, transform=ax8.transAxes, fontsize=12,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle="round,pad=0.5", facecolor="lightgray", alpha=0.8))
    
    plt.suptitle('🚢 Allora Yacht - Vibration Analysis Dashboard', fontsize=16, fontweight='bold')
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"📊 Dashboard saved: {save_path}")

def main():
    """
    Main function to create all visualizations.
    """
    print("🚢 Allora Yacht - Vibration Data Visualization")
    print("=" * 50)
    
    # Load data
    df = load_vibration_data()
    if df is None:
        return
    
    print(f"📁 Loaded {len(df)} vibration readings")
    print(f"📅 Date range: {df['File_Timestamp'].min().strftime('%Y-%m-%d')} to {df['File_Timestamp'].max().strftime('%Y-%m-%d')}")
    print()
    
    # Set style
    plt.style.use('default')
    sns.set_palette("husl")
    
    # Create all visualizations
    try:
        create_time_series_plot(df)
        create_status_breakdown(df)
        create_rpm_speed_analysis(df)
        create_location_analysis(df)
        create_summary_dashboard(df)
        
        print("\n✅ All visualizations completed!")
        print("📊 Generated files:")
        print("  - vibration_time_series.png")
        print("  - vibration_status_breakdown.png")
        print("  - vibration_rpm_speed.png")
        print("  - vibration_location_analysis.png")
        print("  - vibration_dashboard.png")
        
    except Exception as e:
        print(f"❌ Error creating visualizations: {e}")

if __name__ == "__main__":
    main() 