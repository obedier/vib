#!/usr/bin/env python3

import pandas as pd
import numpy as np
import sys

# Usage: ./calcvib.py myfile.txt
if len(sys.argv) != 2:
    print("Usage: ./vibration_log.py <logfile.txt>")
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

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)