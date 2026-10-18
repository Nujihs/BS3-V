#!/bin/bash

# Jianpu Converter Installation Script

echo "========================================"
echo "  Jianpu to BD Converter - Installation"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 not found, please install Python"
    echo "Ubuntu/Debian: sudo apt-get install python3 python3-pip"
    echo "MacOS: brew install python3"
    exit 1
fi

echo "Python3 is installed"
python3 --version
echo ""

# Create virtual environment (optional)
read -p "Create virtual environment? (Y/N): " create_venv
if [[ $create_venv =~ ^[Yy]$ ]]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "Virtual environment created"
    echo ""
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies..."
pip3 install -r requirements.txt

if [ $? -ne 0 ]; then
    echo ""
    echo "Installation failed!"
    echo "Please check network or try using mirror:"
    echo "pip3 install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple"
    exit 1
fi

echo ""
echo "========================================"
echo "  Installation Complete!"
echo "========================================"
echo ""
echo "To run:"
echo "1. Add execute permission: chmod +x start.sh"
echo "2. Run: ./start.sh"
echo ""
echo "Visit: http://127.0.0.1:5000"
echo ""
