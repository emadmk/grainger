#!/bin/bash

echo "========================================"
echo "  GRAINGER PRODUCT SELECTION SETUP"
echo "========================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python
echo -e "${YELLOW}[1/4] Checking Python...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}  Found: $PYTHON_VERSION${NC}"
else
    echo -e "${RED}  Python 3 not found! Please install Python 3.8+${NC}"
    exit 1
fi

# Create virtual environment
echo ""
echo -e "${YELLOW}[2/4] Creating virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate
echo -e "${GREEN}  Virtual environment created${NC}"

# Install dependencies
echo ""
echo -e "${YELLOW}[3/4] Installing dependencies...${NC}"
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
echo -e "${GREEN}  Dependencies installed${NC}"

# Check data folder
echo ""
echo -e "${YELLOW}[4/4] Checking data folder...${NC}"
if [ -d "data" ]; then
    FILE_COUNT=$(ls -1 data/*.csv data/*.txt data/*.dat 2>/dev/null | wc -l)
    if [ "$FILE_COUNT" -gt 0 ]; then
        echo -e "${GREEN}  Found $FILE_COUNT data file(s) in ./data/${NC}"
    else
        echo -e "${YELLOW}  No data files found in ./data/${NC}"
        echo -e "${YELLOW}  Please place your CSV files in the data folder${NC}"
    fi
else
    mkdir -p data
    echo -e "${YELLOW}  Created ./data/ folder${NC}"
    echo -e "${YELLOW}  Please place your CSV files in the data folder${NC}"
fi

echo ""
echo "========================================"
echo -e "${GREEN}  SETUP COMPLETE!${NC}"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Place your data files in ./data/ folder"
echo ""
echo "  2. Import data:"
echo "     source venv/bin/activate"
echo "     cd app && python import_data.py"
echo ""
echo "  3. Start server:"
echo "     python main.py"
echo ""
echo "  4. Open browser:"
echo "     http://YOUR_SERVER_IP:8000"
echo ""
echo "========================================"
