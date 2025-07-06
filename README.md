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
- **Live BLE Monitoring**: Real-time vibration monitoring with WT901BLE68 sensor
- **Device Management**: Scan, connect, and manage BLE devices dynamically
- **Mock Device Support**: Test with pre-recorded data without physical hardware

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

### Live BLE Monitoring
```bash
# Start live vibration monitoring
source .venv/bin/activate
python wt901_live_graph_v2.py

# Test mode with pre-recorded data
python wt901_live_graph_v2.py --test
```

### Device Management
1. **Scan for Devices**: Click "Scan BLE Devices" to discover available sensors
2. **Connect to Device**: Click "Connect" to establish BLE connection
3. **Mock Device**: Click "Mock Device" for testing without hardware
4. **Log Data Points**: Click "Log Data Point" to capture current statistics

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
├── wt901_live_graph_v2.py  # Live BLE monitoring dashboard
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

## 📝 Version History

### v0.57 (2025-07-06) - Historical Data & Logging Fixes
**Major Fixes:**
- **Fixed historical data plotting** - Corrected column names from `'Mean Acc (g)'` to `'Mean_Acc_g'` to match CSV format
- **Fixed logging button crashes** - Removed tkinter dependencies that caused segmentation faults
- **Restored correct CSV format** - Using original column structure with proper headers
- **Added comprehensive debug logging** - Shows CSV columns, row counts, and data loading status

**New Features:**
- **Non-blocking logging** - "Log Data Point" button now works without freezing the GUI
- **Immediate data logging** - Logs current vibration data with default values instantly
- **Console feedback** - Shows current vibration statistics when logging
- **Debug diagnostics** - Enhanced logging for troubleshooting data loading issues

**Technical Improvements:**
- Removed automatic periodic logging (was overwriting CSV with wrong format)
- Fixed matplotlib/tkinter conflicts that caused application crashes
- Added proper error handling for CSV loading and parsing
- Improved data validation and column name matching

### v0.56 (2025-07-06) - Status Panel Toggle Fixes
**Fixes:**
- **Always clear lower-right axes** when toggling to status panel to remove all historical plot artifacts
- **Clean status panel display** - No more leftover lines, legends, or baselines from historical view
- **Proper panel switching** - Status panel is now always clean after toggle

### v0.55 (2025-07-06) - Status Panel Redraw Fix
**Fixes:**
- **Re-create text objects if missing** after toggling back from historical view
- **Force complete redraw** of status panel elements
- **Always restore status panel** correctly after historical view

### v0.5 (2025-07-06) - Toggle Button & Panel Fixes
**Fixes:**
- **Fixed status panel toggle** - Preserve text content when switching views
- **Added debug logging** - Track element visibility and text updates
- **Clean panel switching** - Remove text clearing that caused display issues

### v0.4 (2025-07-06) - Live Dashboard with Toggle
**New Features:**
- **Real-time vibration monitoring** with WT901BLE68 BLE sensor
- **Live dashboard** with 4-panel layout (acceleration, mean/peak, std dev, status/historical)
- **Toggle button** to switch between status panel and historical data view
- **Background BLE threading** for non-blocking data collection
- **File-based messaging** between BLE thread and GUI thread
- **Stable graph axes** - No more jumping when data doesn't hit boundaries
- **Reference lines** - Idle (1.01g), Cruise (1.03g), Warning (1.23g) baselines

**Technical Architecture:**
- BLE thread → JSON files → GUI thread → matplotlib animation
- 50-point data batches, 100ms animation interval, 1000+ packets/sec
- Custom 0x55 0x61 frame format support for WT901BLE68
- Automatic device connection and data parsing

### v0.3 (2025-07-06) - Enhanced Analysis & Logging
**New Features:**
- **Smart metadata extraction** from filenames (RPM, speed, notes)
- **Comprehensive CSV logging** with operational data and recommendations
- **Status monitoring** with baseline comparisons and warnings
- **Batch processing** with summary reports
- **Drag-and-drop support** via shell scripts

**Improvements:**
- Enhanced filename parsing for operational context
- Added maintenance recommendations based on vibration levels
- Improved error handling and validation
- Better console output formatting

### v0.2 (2025-07-06) - Core Analysis Engine
**Features:**
- **Accurate vibration calculation** using `Acc_total = sqrt(AccX² + AccY² + AccZ²)`
- **Statistical analysis** (mean, standard deviation, peak)
- **Allora-specific baselines** (1.01g idle, 1.03g cruising)
- **CSV output** with detailed results
- **Virtual environment setup** for dependency management

### v0.1 (2025-07-06) - Initial Release
**Basic Features:**
- **WT901BLE68 sensor support** for 3-axis accelerometer data
- **Tab-separated file parsing** with timestamp validation
- **Basic vibration metrics** calculation
- **Simple CSV logging** of results

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