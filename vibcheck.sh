#!/bin/bash
# Allora Vibration Check Script
# Usage: ./vibcheck.sh [filename.txt] or drag and drop files

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate virtual environment
if [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
else
    echo "❌ Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

# Function to analyze a single file
analyze_file() {
    local file="$1"
    
    if [ ! -f "$file" ]; then
        echo "❌ File not found: $file"
        return 1
    fi
    
    echo "🔍 Analyzing: $(basename "$file")"
    echo "----------------------------------------"
    
    python "$SCRIPT_DIR/calcvib.py" "$file"
    
    if [ $? -eq 0 ]; then
        echo "✅ Analysis complete for: $(basename "$file")"
    else
        echo "❌ Analysis failed for: $(basename "$file")"
    fi
    
    echo ""
}

# Main execution
echo "🚢 Allora Vibration Analysis"
echo "============================"

# If no arguments provided, check for dropped files
if [ $# -eq 0 ]; then
    echo "📁 No files specified. Please provide file paths or drag files onto this script."
    echo ""
    echo "Usage examples:"
    echo "  ./vibcheck.sh data/filename.txt"
    echo "  ./vibcheck.sh 'data/20250629181931 idle engine .txt'"
    echo ""
    echo "Or drag and drop files onto this script."
    exit 1
fi

# Process each file provided as argument
for file in "$@"; do
    analyze_file "$file"
done

echo "🎯 Analysis complete for all files!"
echo "📊 Check vibration_log.csv for results"