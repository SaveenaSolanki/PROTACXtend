# 1. Use a stable Miniconda base
FROM continuumio/miniconda3:23.10.0-1

# 2. Workspace Setup
WORKDIR /app
USER root

# 3. Install system-level build tools (Required for some scientific C-extensions)
RUN apt-get update && apt-get install -y \
    curl wget vim build-essential unzip git \
    && apt-get clean

# 4. Copy Environment Files
COPY Magnet.yml /app/Magnet.yml
COPY reinvent_clean.yml /app/reinvent.yml
COPY admet.yml /app/admet.yml

# 5. Create Environments
RUN conda env create -f /app/Magnet.yml && \
    conda env create -f /app/reinvent.yml && \
    conda env create -f /app/admet.yml && \
    conda clean -afy

# 6. The Symlink Bridge (Critical for REINVENT internal pathing)
RUN ln -s /opt/conda/envs/$(grep "name:" reinvent.yml | cut -d' ' -f2) /opt/conda/envs/reinvent

# =====================================================================
# 7. THE HARDWARE, REINVENT & MAGNET REPAIR (Surgical Strikes)
# =====================================================================

# A. Version-Locked Library Sync (ULTRA-CRITICAL: Added numpy/scipy for GROVER)
RUN /opt/conda/envs/reinvent/bin/pip install \
    reinvent-chemistry==0.0.51 \
    reinvent-models==0.0.14 \
    reinvent-scoring==0.0.71 \
    pydantic==1.10.11 \
    numpy==1.21.6 \
    scipy==1.7.3 \
    pandas \
    pathos \
    tensorboard \
    setuptools \
    seaborn \
    matplotlib

# B. DTO Manifest Injection (Fixes the Link-INVENT ImportError)
RUN mkdir -p /opt/conda/envs/reinvent/lib/python3.7/site-packages/reinvent_models/link_invent/dto/ && \
    echo 'class BatchLikelihoodDTO: pass' > /opt/conda/envs/reinvent/lib/python3.7/site-packages/reinvent_models/link_invent/dto/batch_likelihood_dto.py && \
    echo 'from .batch_likelihood_dto import BatchLikelihoodDTO' >> /opt/conda/envs/reinvent/lib/python3.7/site-packages/reinvent_models/link_invent/dto/__init__.py

# C. GPU SAFETY: Replace .cuda() with device-aware logic
RUN find /opt/conda/envs/reinvent/lib/python3.7/site-packages/reinvent_models/ -name "*.py" \
    -exec sed -i 's/\.cuda()/.to(torch.device("cuda" if torch.cuda.is_available() else "cpu"))/g' {} +

# D. PYTORCH FIX: Smart map_location for model loading
RUN sed -i "s/torch.load(path_to_file)/torch.load(path_to_file, map_location=torch.device('cuda' if torch.cuda.is_available() else 'cpu'))/g" \
    /opt/conda/envs/reinvent/lib/python3.7/site-packages/reinvent_models/link_invent/link_invent_model.py

# E. MAGNET ENVIRONMENT FIX (Resolves Pickling & descriptastorus issues)
RUN /opt/conda/envs/Magnet/bin/pip install \
    descriptastorus \
    scikit-learn==1.2.2

# =====================================================================

# 8. Final App Setup & Permissions
COPY . /app
RUN mkdir -p /app/outputs /app/data /app/models /app/repos && \
    chmod -R 777 /app/outputs

# 9. Global Python Path (Ensures 'running_modes' and 'grover' are discoverable)
ENV PYTHONPATH="/app/repos/reinvent:/app/repos:/app/repos/grover"

# 10. Execution Setup
EXPOSE 8000
SHELL ["conda", "run", "-n", "Magnet", "/bin/bash", "-c"]

# Start the FastAPI server
CMD ["/opt/conda/envs/Magnet/bin/uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]