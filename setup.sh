#!/bin/bash
# Setup script for Allora Vibration Analysis

echo "🚢 Setting up Allora Vibration Analysis Environment"
echo "=================================================="

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📚 Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "To activate the environment:"
echo "  source .venv/bin/activate"
echo ""
echo "To analyze a single file:"
echo "  source .venv/bin/activate && python calcvib.py 'data/filename.txt'"
echo ""
echo "To analyze all files:"
echo "  source .venv/bin/activate && python batch_analyze.py"
echo "" 