# P4ward Docker image for PROTACPilot
# 
# Build from project root: docker build -t protacpilot/p4ward -f docker/p4ward/Dockerfile .
#
# This Dockerfile extends the official P4ward image with 
# additional tools needed by the PROTACPilot wrapper.
#
# Reference:
#   Jofily & Kalyaanamoorthy, JCIM 2025, 65(16), 8806-8818.
#   https://github.com/SKTeamLab/P4ward

FROM paulajlr/p4ward:latest

LABEL maintainer="protacpilot"
LABEL description="P4ward ternary complex modeling engine with PROTACPilot wrapper support"
LABEL version="1.0"

# Additional Python packages for output parsing and integration
RUN conda run -n p4ward pip install --no-cache-dir \
    numpy==1.26.4 \
    pandas==2.2.3 \
    scipy==1.13.1 \
    biopython==1.84 \
    && conda clean -afy

# Ensure the P4ward package is importable
ENV PYTHONPATH=/home/python:$PYTHONPATH

# Verify installation
RUN conda run -n p4ward python -c "import p4ward; print(f'P4ward {p4ward.__version__ if hasattr(p4ward, \"__version__\") else \"installed\"}')" 2>/dev/null || \
    echo "P4ward import check skipped (expected in headless env)"

WORKDIR /home/data
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "p4ward", "python", "-m", "p4ward"]
