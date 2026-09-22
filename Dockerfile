# PROTACXtend API/runtime image.
#
# Build:
#   docker build -t protacxtend .
# Run (API):
#   docker run --rm -p 8000:8000 protacxtend
# Run (CLI):
#   docker run --rm protacxtend python -m protacxtend.cli doctor
#
# The image installs the *package* (not just loose files) so the console
# entry points and package metadata are present, and it installs only the
# API/UI extras.  Heavy scientific engines (RDKit, Chemprop, docking) are
# optional and are documented separately for workstation/HPC images.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Minimal OS deps commonly needed by scientific/python stacks.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Packaging metadata first for better layer caching.
COPY pyproject.toml README.md MANIFEST.in /app/

# Package source (including package data under protacxtend/data).
COPY protacxtend /app/protacxtend

# Install the project itself with the API + UI extras.  This creates the
# ``protacxtend`` / ``PROTACXtend`` entry points and installs runtime deps.
RUN python -m pip install --upgrade pip && \
    pip install ".[api,ui]"

# Create non-root runtime user.
RUN useradd -m -u 10001 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000 8501

# Default to API server; override CMD for CLI/Streamlit.
CMD ["python", "-m", "uvicorn", "protacxtend.backend.api_routes:app", "--host", "0.0.0.0", "--port", "8000"]
