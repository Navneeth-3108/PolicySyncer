#!/bin/bash
set -e

echo "========================================="
echo "Policy Conflict Detector - Setup Script"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Install Layer 1 dependencies
echo -e "${BLUE}[1/3] Installing Layer 1 dependencies...${NC}"
cd policy_layer1
pip install -r requirements.txt
echo -e "${GREEN}✓ Layer 1 dependencies installed${NC}"
echo ""

# Install Layer 2 dependencies
echo -e "${BLUE}[2/3] Installing Layer 2 dependencies...${NC}"
cd ../policy_layer2
pip install -r requirements.txt
echo -e "${GREEN}✓ Layer 2 dependencies installed${NC}"
echo ""

# Install Layer 3 dependencies (if requirements.txt exists)
echo -e "${BLUE}[3/3] Checking Layer 3 dependencies...${NC}"
cd ../policy_layer3
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Layer 3 dependencies installed${NC}"
else
    echo -e "${GREEN}✓ Layer 3 has no additional dependencies${NC}"
fi
echo ""

# Install Web UI / API Server dependencies
echo -e "${BLUE}Installing Web UI & API Server dependencies...${NC}"
cd ../app
pip install -r requirements.txt
echo -e "${GREEN}✓ Web UI & API Server dependencies installed${NC}"
echo ""

# Optional: Install advanced NLP models
echo ""
echo -e "${BLUE}Optional: Installing advanced NLP models for better performance...${NC}"
read -p "Install sentence-transformers and spaCy? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo "Installing sentence-transformers..."
    pip install sentence-transformers
    
    echo "Installing spaCy..."
    pip install spacy
    python -m spacy download en_core_web_sm
    
    echo "Installing transformers and torch for NLI..."
    pip install transformers torch
    
    echo -e "${GREEN}✓ Advanced NLP models installed${NC}"
else
    echo "Skipped optional NLP models. The pipeline will use stdlib fallbacks."
fi

echo ""
echo -e "${GREEN}========================================="
echo "✓ Setup complete!"
echo "=========================================${NC}"
echo ""
echo "To run the full pipeline, execute:"
echo "  python run_pipeline.py"
echo ""
