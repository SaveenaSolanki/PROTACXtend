#!/bin/bash
# BioMiner Setup
echo "Setting up BioMiner..."
cd "$(dirname "$0")"
if [ -d "biominer" ]; then
    echo "BioMiner already cloned"
else
    git clone https://github.com/jiaxianyan/BioMiner.git biominer
    cd biominer
    conda create -n biominer python=3.11 -y 2>/dev/null || echo "Conda not available"
    source activate biominer 2>/dev/null || true
    pip install -r requirements.txt 2>/dev/null || echo "requirements.txt not found"
    echo "BioMiner installed at $(pwd)"
fi
