#!/bin/bash

# Jianpu Converter Startup Script

echo "========================================"
echo "  Jianpu Converter System"
echo "========================================"
echo ""

# Check Python3
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 not found, please install Python"
    exit 1
fi

echo "Starting server..."
echo "Visit: http://127.0.0.1:5000"
echo "Press Ctrl+C to stop"
echo ""

# Start server
python3 backend/app.py

if [ $? -ne 0 ]; then
    echo ""
    echo "Startup failed! Please check:"
    echo "1. Install dependencies: pip3 install -r requirements.txt"
    echo "2. Check if port 5000 is available"
    echo ""
fi
