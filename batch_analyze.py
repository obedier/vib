#!/usr/bin/env python3
"""
Batch Vibration Analysis for Allora Yacht
Processes all vibration log files in the data directory.
"""

import os
import glob
from calcvib import analyze_vibration_data, compare_to_baseline, log_results
import pandas as pd
from datetime import datetime

def process_all_files(data_dir="data", output_file="vibration_log.csv"):
    """
    Process all .txt files in the data directory.
    """
    # Find all .txt files in data directory
    pattern = os.path.join(data_dir, "*.txt")
    files = glob.glob(pattern)
    
    if not files:
        print(f"No .txt files found in {data_dir}/")
        return
    
    print(f"Found {len(files)} files to process...")
    print("=" * 60)
    
    results = []
    
    for i, file_path in enumerate(sorted(files), 1):
        try:
            print(f"Processing {i}/{len(files)}: {os.path.basename(file_path)}")
            
            # Analyze the file
            analysis = analyze_vibration_data(file_path)
            comparison = compare_to_baseline(analysis['mean_acc'], analysis['notes'])
            
            # Combine results
            file_results = {
                'filename': file_path,
                **analysis,
                **comparison
            }
            
            results.append(file_results)
            
            # Log individual result
            log_results(file_results, output_file)
            
            # Show brief summary
            status_icon = "🟢" if comparison['status'] == "Normal" else "🟡" if comparison['status'] == "ATTENTION" else "🔴"
            print(f"   {status_icon} {analysis['mean_acc']:.3f}g ({comparison['status']})")
            
        except Exception as e:
            print(f"   ❌ Error processing {os.path.basename(file_path)}: {e}")
    
    print("=" * 60)
    print(f"✅ Processed {len(results)} files successfully")
    print(f"📊 Results saved to: {output_file}")
    
    return results

def generate_summary_report(results, output_file="vibration_summary.csv"):
    """
    Generate a summary report with key insights.
    """
    if not results:
        print("No results to summarize")
        return
    
    # Create summary DataFrame
    summary_data = []
    
    for r in results:
        summary_data.append({
            'File': os.path.basename(r['filename']),
            'File_Timestamp': r['file_timestamp'].strftime('%Y-%m-%d %H:%M:%S') if r['file_timestamp'] else '',
            'Mean_Acc_g': round(r['mean_acc'], 3),
            'Std_Dev_g': round(r['std_dev'], 3),
            'Peak_Acc_g': round(r['peak_acc'], 3),
            'RPM': r['rpm'] or '',
            'Speed_knots': r['speed'] or '',
            'Notes': r['notes'] or '',
            'Status': r['status'],
            'Baseline_g': round(r['baseline'], 3),
            'Deviation_g': round(r['deviation'], 3)
        })
    
    df = pd.DataFrame(summary_data)
    
    # Sort by file timestamp if available
    if 'File_Timestamp' in df.columns and df['File_Timestamp'].notna().any():
        df = df.sort_values('File_Timestamp')
    
    # Save summary
    df.to_csv(output_file, index=False)
    
    # Print summary statistics
    print("\n📋 SUMMARY STATISTICS:")
    print("=" * 40)
    
    # Status breakdown
    status_counts = df['Status'].value_counts()
    print("Status Breakdown:")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")
    
    # RPM analysis
    rpm_data = df[df['RPM'].notna() & (df['RPM'] != '')].copy()
    if not rpm_data.empty:
        print(f"\nRPM Analysis ({len(rpm_data)} files):")
        rpm_data['RPM'] = pd.to_numeric(rpm_data['RPM'], errors='coerce')
        rpm_data = rpm_data.dropna(subset=['RPM'])
        if not rpm_data.empty:
            print(f"  Range: {rpm_data['RPM'].min():.0f} - {rpm_data['RPM'].max():.0f} RPM")
            print(f"  Average: {rpm_data['RPM'].mean():.0f} RPM")
    
    # Speed analysis
    speed_data = df[df['Speed_knots'].notna() & (df['Speed_knots'] != '')].copy()
    if not speed_data.empty:
        print(f"\nSpeed Analysis ({len(speed_data)} files):")
        speed_data['Speed_knots'] = pd.to_numeric(speed_data['Speed_knots'], errors='coerce')
        speed_data = speed_data.dropna(subset=['Speed_knots'])
        if not speed_data.empty:
            print(f"  Range: {speed_data['Speed_knots'].min():.1f} - {speed_data['Speed_knots'].max():.1f} knots")
            print(f"  Average: {speed_data['Speed_knots'].mean():.1f} knots")
    
    # Vibration trends
    print(f"\nVibration Trends:")
    print(f"  Mean acceleration range: {df['Mean_Acc_g'].min():.3f} - {df['Mean_Acc_g'].max():.3f} g")
    print(f"  Average mean acceleration: {df['Mean_Acc_g'].mean():.3f} g")
    print(f"  Peak acceleration range: {df['Peak_Acc_g'].min():.3f} - {df['Peak_Acc_g'].max():.3f} g")
    
    # Warnings
    warnings = df[df['Status'] == 'WARNING']
    if not warnings.empty:
        print(f"\n⚠️  WARNINGS ({len(warnings)} files):")
        for _, row in warnings.iterrows():
            print(f"  {row['File']}: {row['Mean_Acc_g']:.3f}g ({row['Deviation_g']:+.3f}g deviation)")
    
    print(f"\n📄 Summary saved to: {output_file}")

def main():
    """Main function for batch processing."""
    print("🚢 ALLORA YACHT - BATCH VIBRATION ANALYSIS")
    print("=" * 60)
    
    # Process all files
    results = process_all_files()
    
    if results:
        # Generate summary report
        generate_summary_report(results)
        
        print("\n✅ Batch analysis complete!")
        print("📁 Check vibration_log.csv for detailed results")
        print("📊 Check vibration_summary.csv for summary report")

if __name__ == "__main__":
    main() 