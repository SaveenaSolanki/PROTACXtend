#!/bin/bash
# Robin Setup
echo "Setting up Robin..."
cd "$(dirname "$0")"
if [ -d "robin" ]; then
    echo "Robin already cloned"
else
    git clone https://github.com/Future-House/robin.git robin
    cd robin
    conda create -n robin python=3.12 -y 2>/dev/null || echo "Conda not available"
    source activate robin 2>/dev/null || true
    pip install -r requirements.txt 2>/dev/null || echo "requirements.txt not found"
    echo "Robin installed at $(pwd)"
fi
