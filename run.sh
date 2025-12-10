#!/bin/bash

echo "Starting Grainger Product Selection Server..."
echo ""

# Activate virtual environment
source venv/bin/activate

# Change to app directory
cd app

# Start server
python main.py
