#!/usr/bin/env python3

import pandas as pd
import numpy as np
import sys
from datetime import datetime

if len(sys.argv) != 2:
    print("Usage: ./calcvib.py <logfile.txt>")
    sys.exit(1)

log_file = sys.argv[1]

try:
    df = pd.read_csv(log_file, sep="\t")
    df['time'] = pd.to_datetime(df['time'], errors='coerce')
    df = df.dropna(subset=['time'])

    df['Acc_total'] = np.sqrt(
        df['AccX(g)']**2 +
        df['AccY(g)']**2 +
        df['AccZ(g)']**2
    )

    mean_vib = df['Acc_total'].mean()
    std_vib = df['Acc_total'].std()
    peak_vib = df['Acc_total'].max()

    print(f"📊 File: {log_file}")
    print(f"Mean Acc (g): {mean_vib:.3f}")
    print(f"Std Dev (g): {std_vib:.3f}")
    print(f"Peak Acc (g): {peak_vib:.3f}")

    # Append to log.csv
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_df = pd.DataFrame([{
        "Timestamp": now,
        "File": log_file,
        "Mean Acc (g)": round(mean_vib, 3),
        "Std Dev (g)": round(std_vib, 3),
        "Peak Acc (g)": round(peak_vib, 3)
    }])

    log_df.to_csv("vibration_log.csv", mode='a', index=False, header=not pd.io.common.file_exists("vibration_log.csv"))

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)