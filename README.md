# 🚢 Allora Yacht Vibration Analysis System

A comprehensive vibration monitoring system for the Allora yacht using WT901BLE68 sensor data. This system processes vibration logs, calculates key metrics, and provides maintenance recommendations based on Allora-specific baselines.

## 📋 Features

- **Accurate Vibration Calculation**: Calculates `Acc_total = sqrt(AccX² + AccY² + AccZ²)` from 3-axis accelerometer data
- **Allora-Specific Baselines**: Compares readings to established baselines (1.01g idle, 1.03g cruising)
- **Smart Metadata Extraction**: Automatically extracts RPM, speed, and notes from filenames
- **Comprehensive Logging**: Saves detailed results to CSV with timestamps, operational data, and recommendations
- **Batch Processing**: Analyze multiple files at once with summary reports
- **Status Monitoring**: Provides warnings for significant deviations from baseline
- **Drag-and-Drop Support**: Easy file processing with shell scripts

## 🛠️ Installation

### Prerequisites
- Python 3.8 or higher
- macOS/Linux (tested on macOS)

### Quick Setup
```bash
# Clone or download the project
cd vib

# Run the setup script
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Create a Python virtual environment (`.venv`)
- Install required dependencies (pandas, numpy)
- Configure the environment for analysis

## 📊 Usage

### Single File Analysis
```bash
# Activate environment and analyze a file
source .venv/bin/activate
python calcvib.py "data/20250629181931 idle engine .txt"
```

### Using the Shell Script
```bash
# Make script executable
chmod +x vibcheck.sh

# Analyze a single file
./vibcheck.sh "data/20250629181931 idle engine .txt"

# Or drag and drop files onto the script
```

### Batch Analysis
```bash
# Process all files in the data directory
source .venv/bin/activate
python batch_analyze.py
```

## 📁 File Format

The system expects tab-separated `.txt` files with the following columns:
- `time`: Timestamp (parsed as datetime)
- `AccX(g)`: X-axis acceleration in g
- `AccY(g)`: Y-axis acceleration in g  
- `AccZ(g)`: Z-axis acceleration in g
- Additional columns (gyro, magnetometer) are ignored

### Filename Convention
Files should follow this naming pattern for optimal metadata extraction:
```
YYYYMMDDHHMMSS description rpm speed knots .txt
```

Examples:
- `20250629181931 idle engine .txt`
- `20250629184710 cruising 1500 rpm 11.5 knots .txt`
- `20250628113139 port stern 1415 rpm .txt`

## 📈 Output

### Console Output
```
============================================================
🚢 ALLORA YACHT VIBRATION ANALYSIS
============================================================
📁 File: 20250629181931 idle engine .txt
📊 Sample Count: 10,234
⏱️  Duration: 30 seconds
🕐 File Timestamp: 2025-06-29 18:19:31

📈 VIBRATION METRICS:
   Mean Acceleration: 1.012 g
   Standard Deviation: 0.045 g
   Peak Acceleration: 1.049 g

🔧 OPERATIONAL DATA:
   Notes: idle engine

⚠️  STATUS & RECOMMENDATIONS:
   Status: Normal
   Baseline: 1.010 g (idle)
   Deviation: +0.002 g
   Recommendation: Continue monitoring

💾 Results logged to: vibration_log.csv
============================================================
```

### CSV Log Output
Results are saved to `vibration_log.csv` with columns:
- `Timestamp`: Analysis timestamp
- `File`: Source filename
- `File_Timestamp`: Extracted from filename
- `Mean_Acc_g`: Mean acceleration in g
- `Std_Dev_g`: Standard deviation in g
- `Peak_Acc_g`: Peak acceleration in g
- `RPM`: Engine RPM (if detected)
- `Speed_knots`: Speed in knots (if detected)
- `Notes`: Operational notes
- `Status`: Normal/ATTENTION/WARNING
- `Baseline_g`: Expected baseline value
- `Deviation_g`: Deviation from baseline
- `Recommendation`: Maintenance recommendation

## 🎯 Allora-Specific Features

### Baseline Values
- **Idle**: 1.01g (engine running, vessel stationary)
- **Cruising**: 1.03g (normal operation at 11-12 knots)

### Warning Thresholds
- **Normal**: Within 0.1g of baseline
- **Attention**: 0.1-0.2g deviation
- **Warning**: >0.2g deviation

### Maintenance Recommendations
- High vibration: Check shaft alignment and propeller balance
- Low vibration: Verify sensor placement and calibration
- Trend monitoring: Track changes over time

## 🔧 Technical Details

### Sensor Configuration
- **Device**: WT901BLE68 (WitMotion)
- **Location**: Port stern tube area, floor panel above shaft
- **Sampling**: 100-200 Hz bandwidth, 50-100 Hz return rate
- **Mounting**: Taped for repeatability

### Data Processing
- **Calculation**: `Acc_total = sqrt(AccX² + AccY² + AccZ²)`
- **Statistics**: Mean, Standard Deviation, Peak
- **Duration**: Assumes 30-second samples
- **Validation**: Drops rows with invalid timestamps

### Dependencies
- `pandas>=1.5.0`: Data manipulation and CSV handling
- `numpy>=1.21.0`: Mathematical calculations

## 📋 File Structure
```
vib/
├── calcvib.py              # Main analysis script
├── batch_analyze.py        # Batch processing script
├── vibcheck.sh             # Shell wrapper script
├── setup.sh                # Environment setup
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── .venv/                 # Virtual environment
├── data/                  # Vibration log files
│   ├── 20250629181931 idle engine .txt
│   ├── 20250629184710 cruising 1500 rpm 11.5 knots .txt
│   └── ...
├── vibration_log.csv      # Detailed results log
└── vibration_summary.csv  # Batch analysis summary
```

## 🚨 Troubleshooting

### Common Issues

**Virtual Environment Not Found**
```bash
./setup.sh  # Run setup script
```

**File Not Found**
```bash
# Check file path and permissions
ls -la "data/filename.txt"
```

**Import Errors**
```bash
# Ensure virtual environment is activated
source .venv/bin/activate
pip install -r requirements.txt
```

**Invalid Data Format**
- Ensure files are tab-separated
- Check column names match expected format
- Verify timestamp format is parseable

## 📞 Support

For issues specific to the Allora yacht or sensor configuration, refer to:
- WT901BLE68 User Manual
- Allora technical specifications
- Vibration monitoring procedures

## 🔄 Future Enhancements

- [ ] Real-time Bluetooth data capture
- [ ] Google Sheets integration
- [ ] Trend analysis and forecasting
- [ ] Automated alert system
- [ ] Web dashboard interface
- [ ] Mobile app integration

---

**Note**: This system is specifically configured for the Allora yacht's vibration monitoring requirements. Baseline values and thresholds are based on the vessel's operational characteristics and should be adjusted for other applications. 