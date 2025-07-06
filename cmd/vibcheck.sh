#!/bin/bash

# Usage: ./vibcheck.sh path/to/file.txt

source .venv/bin/activate
python calcvib.py "$1"