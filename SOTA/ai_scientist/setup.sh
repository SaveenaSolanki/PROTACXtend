#!/bin/bash
# AI Scientist Setup
echo "Setting up AI Scientist..."
cd "$(dirname "$0")"
if [ -d "ai-scientist" ]; then
    echo "AI Scientist already cloned"
else
    git clone https://github.com/SakanaAI/AI-Scientist.git ai-scientist
    cd ai-scientist
    conda create -n ai_scientist python=3.11 -y 2>/dev/null || echo "Conda not available, using pip"
    source activate ai-scientist 2>/dev/null || true
    pip install -r requirements.txt 2>/dev/null || echo "requirements.txt not found"
    echo "AI Scientist installed at $(pwd)"
fi
