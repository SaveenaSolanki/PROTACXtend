# SynGlue Docker Deployment Guide

> **Project root:** `/storage/savi/saveenas/Projects/SynGlue_Py`
> **All commands below must be run from this directory unless stated otherwise.**

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Building the Docker Image](#2-building-the-docker-image)
3. [Directory Structure & What Each Path Does](#3-directory-structure--what-each-path-does)
4. [Running the Container (Detailed)](#4-running-the-container-detailed)
5. [Check the Container & API](#5-check-the-container--api)
6. [Stop, Remove & Restart the Container](#6-stop-remove--restart-the-container)
7. [Full Rebuild Cycle (Code Changes)](#7-full-rebuild-cycle-code-changes)
8. [Useful Commands](#8-useful-commands)
9. [Container Internals](#9-container-internals)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

| Requirement | Check Command | Expected Output |
|---|---|---|
| Docker installed | `docker --version` | `Docker version 24.x.x` |
| Docker running | `docker ps` | List of containers (no error) |
| NVIDIA GPU (optional) | `nvidia-smi` | GPU info table |
| NVIDIA Container Toolkit | `docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi` | GPU info inside container |

If Docker is not running, start it with:
```bash
sudo systemctl start docker
```

---

## 2. Building the Docker Image

### Step 1 — Go to the project directory
```bash
cd /storage/savi/saveenas/Projects/SynGlue_Py
```

### Step 2 — Build
```bash
docker build -t synglue-api .
```

**What is happening here:**
- Docker reads the `Dockerfile` in the current directory (`.`)
- It uses `continuumio/miniconda3:23.10.0-1` as the base image
- It installs system packages: `curl`, `wget`, `vim`, `build-essential`, `unzip`, `git`
- It copies 3 Conda environment YML files (`Magnet.yml`, `reinvent_clean.yml`, `admet.yml`) and creates **3 separate Conda environments** inside the image:
  - `Magnet` (Python 3.9) — for the FastAPI server
  - `reinvent` (Python 3.7) — for REINVENT molecular design (symlinked to `/opt/conda/envs/reinvent`)
  - `admet` — for ADMET predictions
- It patches REINVENT internals (replaces `.cuda()` calls with device-aware logic, fixes `torch.load` to use `map_location`)
- It installs `descriptastorus` and `scikit-learn==1.2.2` into the `Magnet` environment
- It copies all source code into `/app/`
- It sets `PYTHONPATH` and exposes port 8000

**⏱ Build time:** 20–40 minutes (mostly Conda solving & installing packages).

### Build without cache (if cached build fails)
```bash
docker build --no-cache -t synglue-api .
```

---

## 3. Directory Structure & What Each Path Does

### Host directories (on your machine)

```
/storage/savi/saveenas/Projects/SynGlue_Py/
├── data/          →  mounted at  /app/data/   inside container
├── models/        →  mounted at  /app/models/  inside container
├── outputs/       →  mounted at  /app/outputs/ inside container
├── repos/         →  mounted at  /app/repos/   inside container
│   ├── reinvent/
│   └── grover/
├── Dockerfile
├── app.py
├── Magnet.yml
├── reinvent_clean.yml
├── admet.yml
└── ... (other source files)
```

### What each mounted directory is for

| Host Path | Container Path | Purpose | What lives there |
|---|---|---|---|
| `./data/` | `/app/data/` | **Read-only data** — databases, lookup tables, dictionaries used by SynGlue for mapping and annotation | `magnet.db`, fragment files, target mappings, SMILES lookup tables |
| `./models/` | `/app/models/` | **Model weights** — pretrained PyTorch/Transformer models for DC50/Dmax prediction and PROTAC prioritization | `.pt` or `.pth` files, model configs |
| `./outputs/` | `/app/outputs/` | **Results** — all generated molecules, CSVs, logs get written here when you submit API jobs | `Design_Runs/`, `Screen_Runs/`, SynGlue outputs |
| `./repos/` | `/app/repos/` | **External code** — REINVENT4 and GROVER source repos that SynGlue imports from | `reinvent/` (molecular generation), `grover/` (embedding model) |

> **Important:** The host paths above are mounted as **bind mounts**. Any file the container writes to `/app/outputs/` will appear in `./outputs/` on your host machine immediately. This is how you retrieve results without `docker cp`.

### Why these must be mounted (not copied into the image)

| Reason | Explanation |
|---|---|
| **`data/` is large** | Contains DB files that shouldn't bloat the image |
| **`models/` is large** | Model weights can be GBs; rebuilding image for every weight change is impractical |
| **`outputs/` is dynamic** | Results are written at runtime — must persist across container restarts |
| **`repos/` needs updates** | REINVENT/GROVER repos may be updated independently of the Docker image |

---

## 4. Pre-Deployment Setup & Diagnostics Check

Because SynGlue relies on massive database libraries and pre-trained machine learning weights that are not committed to Git, you **must** verify that all essential host assets exist and are correctly placed before building or running the container.

### Step 1 — Verify Essential Files Checklists
Ensure that the following assets exist inside your host workspace folders:

#### 📁 Host Directory: `./data/`
| Host Filename | Purpose | Approx. Size |
|---|---|---|
| `Lean_MagnetDB_Trie.pkl` | High-speed Trie for fragment-to-target mapping | ~268 MB |
| `Clean_Metadata_Hash_FINAL_GENE_FIXED.pkl` | Metadata index mappings (Gene Symbol Fixed) | ~862 MB |
| `Targets_for_magnetdb.csv` | Master lookup target metadata dictionary | ~1.7 MB |
| `e3_ligand.csv` | Reference scoring indices for all E3 ligase targets | ~58 KB |
| `warhead_fragments.pkl` | Warhead/fragment matching matrices library | ~1.45 GB |
| `grover_e3.csv` | Descriptor features for GROVER E3 predictions | ~6.1 MB |
| `grover_warhead.csv` | Descriptor features for GROVER warhead predictions | ~57.5 MB |

#### 📁 Host Directory: `./models/`
| Host Filename | Purpose | Approx. Size |
|---|---|---|
| `grover_fixed.pt` | Trained GROVER checkpoint for embedding outputs | ~409 MB |
| `linker_classifier.pkl` | Gradient Boosting / Random Forest Linker classifier | ~6.3 MB |
| `linkinvent.prior` | Link-INVENT Policy Prior network model weights | ~90 MB |
| `multitask_transformer.pt` | PyTorch Multitask Transformer PROTAC affinity model | ~34.5 MB |
| `rf_dc50.joblib` | Random Forest model predicting DC50 affinity | ~43.3 MB |
| `rf_dmax.joblib` | Random Forest model predicting DMax efficiency | ~23.9 MB |

---

### Step 2 — Run Host Setup Diagnostics Precheck
We have provided an automatic environment verification script `precheck.py` that is fully retro-compatible with legacy Python installations (like your host's **Python 3.5.2**).

Run this diagnostic script from the project root on your host terminal:
```bash
python3 precheck.py
```

**Expected Healthy Diagnostic Output:**
```
======================================================================
            SynGlue Environment Precheck & Diagnostics Tool           
======================================================================
Active Base Path Resolution:
  - base_dir   : /storage/savi/saveenas/Projects/SynGlue_Py
  - data_dir   : /storage/savi/saveenas/Projects/SynGlue_Py/data
  - model_dir  : /storage/savi/saveenas/Projects/SynGlue_Py/models
  - output_dir : /storage/savi/saveenas/Projects/SynGlue_Py/outputs
  - repos_dir  : /storage/savi/saveenas/Projects/SynGlue_Py/repos
----------------------------------------------------------------------

[1/5] Checking Directory Existence & Write Permissions:
  [OK] Base workspace: /storage/savi/saveenas/Projects/SynGlue_Py (Writable)
  [OK] Data directory: /storage/savi/saveenas/Projects/SynGlue_Py/data
  [OK] Models directory: /storage/savi/saveenas/Projects/SynGlue_Py/models
  [OK] Outputs directory (Results): /storage/savi/saveenas/Projects/SynGlue_Py/outputs (Writable)
  [OK] Repos directory: /storage/savi/saveenas/Projects/SynGlue_Py/repos
  [OK] REINVENT clone: /storage/savi/saveenas/Projects/SynGlue_Py/repos/reinvent
  [OK] GROVER clone: /storage/savi/saveenas/Projects/SynGlue_Py/repos/grover

[2/5] Checking Environment Config Files (Project Root):
  [OK] FastAPI configuration / launcher (18.61 KB)
  [OK] Magnet Conda environment specification (336.00 B)
  [OK] Reinvent Conda environment specification (5.66 KB)
  [OK] ADMET Conda environment specification (3.13 KB)
  [OK] Docker Container build instruction (3.09 KB)

[3/5] Checking Essential Data Files (Magnet DB, Fragments, Targets):
  [OK] Magnet DB Trie (Lean) (267.86 MB)
  [OK] Magnet DB Metadata Hash (Gene Fixed) (861.87 MB)
  ... (all other data files OK)

[4/5] Checking Pretrained Model Weight & Prior Files:
  [OK] GROVER Deep Learning Checkpoint (408.77 MB)
  [OK] Linker Classifier Forest Model (6.35 MB)
  ... (all other model files OK)

[5/5] Checking Python/Conda Execution Environment & Symlinks:
  [WARNING] Host Python is older than 3.6 (3.5.2).
  Skipping module import checks on Host (they will run successfully inside the container).

======================================================================
Diagnostic Report Summary:
  - Total Errors   : 0
  - Total Warnings : 1

✅ All System Diagnostics Passed! SynGlue is ready for deployment/execution.
```
If the diagnostics tool reports any errors, resolve them before proceeding.

---

## 5. Running the Container (Detailed)

### Dynamic Path Configuration
SynGlue has been modified to support **fully explicit dynamic path overrides**. By passing `-e` environment variables, you can override where data, models, and outputs live inside the container.

### A — With GPU (Recommended — REINVENT/GROVER uses PyTorch/CUDA)
```bash
cd /storage/savi/saveenas/Projects/SynGlue_Py

docker run -d --gpus all -p 8000:8000 \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/outputs:/app/outputs \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/data:/app/data \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/models:/app/models \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/repos:/app/repos \
  -e SYNGLUE_DATA_DIR=/app/data \
  -e SYNGLUE_MODEL_DIR=/app/models \
  -e SYNGLUE_OUTPUT_DIR=/app/outputs \
  --name synglue synglue-api
```

### B — Without GPU (Fallback — CPU only)
```bash
cd /storage/savi/saveenas/Projects/SynGlue_Py

docker run -d -p 8000:8000 \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/outputs:/app/outputs \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/data:/app/data \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/models:/app/models \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/repos:/app/repos \
  -e SYNGLUE_DATA_DIR=/app/data \
  -e SYNGLUE_MODEL_DIR=/app/models \
  -e SYNGLUE_OUTPUT_DIR=/app/outputs \
  --name synglue synglue-api
```

### What each flag does — detailed

| Flag | What it does | Why you need it |
|---|---|---|
| `docker run` | Create and start a new container from an image | — |
| `-d` | **Detached mode** — runs in the background, doesn't lock your terminal | Without this, the terminal stays attached to container logs |
| `--gpus all` | Makes all host NVIDIA GPUs available inside the container | REINVENT models need GPU for reasonable speed. |
| `-p 8000:8000` | **Port mapping** — `host_port:container_port` | Lets you call the API locally at `http://localhost:8000` |
| `-v host:container` | **Bind mount** — maps a host folder into the container | Bridges storage between Host and Container |
| `-e SYNGLUE_DATA_DIR` | Sets inside-container path for DBs and metadata assets | Explicit parameter configuration |
| `-e SYNGLUE_MODEL_DIR` | Sets inside-container path for neural net model weights | Explicit parameter configuration |
| `-e SYNGLUE_OUTPUT_DIR` | Sets inside-container path for Design and Screening job runs | Explicit parameter configuration |
| `--name synglue` | Assigns a readable name to the container | Makes log tracking and restarts simpler |
| `synglue-api` | The Docker **image name** (the tag built in Section 2) | Tells Docker which image to launch |


### What happens when the container starts

1. Docker reads the image `synglue-api`
2. Mounts the 4 host directories at their container paths
3. Sets `PYTHONPATH=/app/repos/reinvent:/app/repos:/app/repos/grover`
4. Runs the **CMD** from the Dockerfile:
   ```
   /opt/conda/envs/Magnet/bin/uvicorn app:app --host 0.0.0.0 --port 8000
   ```
5. Uvicorn starts a FastAPI server listening on port 8000
6. The server is ready when you see:
   ```
   INFO:     Uvicorn running on http://0.0.0.0:8000
   ```

---

## 5. Check the Container & API

### Is the container running?
```bash
docker ps
```
You should see:
```
CONTAINER ID   IMAGE           COMMAND                  CREATED         STATUS         PORTS                    NAMES
xxxxxxxxxxxx   synglue-api     "/opt/conda/envs/Mag…"   X seconds ago   Up X minutes   0.0.0.0:8000->8000/tcp   synglue
```

**Key things to check in the output:**
- `STATUS` must say `Up` (not `Exited`)
- `PORTS` must show `0.0.0.0:8000->8000/tcp`
- `NAMES` should be `synglue`

### Check the server logs
```bash
docker logs synglue
```
Look for:
- No Python tracebacks
- `Uvicorn running on http://0.0.0.0:8000` (means server started successfully)
- `Application startup complete`

### Follow logs live (Ctrl+C to exit)
```bash
docker logs -f synglue
```

### Test & Verify API Docs & Endpoints (Comprehensive testing)

#### A — API Docs & Schema Verification
FastAPI automatically serves interactive docs and dynamic specifications. You can verify the API's presence and retrieve schemas with the following commands:
```bash
# Verify Swagger UI interactive documentation exists (returns HTTP 200)
curl -s -I http://127.0.0.1:8000/docs | grep "HTTP/"

# Verify OpenAPI Schema matches spec (returns HTTP 200)
curl -s -I http://127.0.0.1:8000/openapi.json | grep "HTTP/"
```

---

#### B — Endpoint Specific Job Submissions

##### 🧪 Test 1: Submit a new PROTAC Design Job (POST)
Send a POST request specifying the target protein and affinity percentage threshold:
```bash
curl -X POST "http://127.0.0.1:8000/synglue/api/design/submit/" \
     -H "Content-Type: application/json" \
     -d '{"target": "BRD4", "threshold": 75.0}'
```
**Expected JSON Response:**
```json
{"job_id": "c623d2fa-3e5f-4d3f-b3b4-4b53fa4e1509", "status": "queued"}
```

##### 🧪 Test 2: Check Job Status (GET)
Use the `job_id` returned from Test 1 to query progress:
```bash
curl "http://127.0.0.1:8000/synglue/api/design/status/?job_id=YOUR_JOB_ID_HERE"
```
**Expected JSON Response (Completed):**
```json
{
  "job_id": "YOUR_JOB_ID_HERE",
  "status": "completed",
  "error": null,
  "queue_position": null
}
```

##### 🧪 Test 3: Download Design Results (GET)
Once the status returns `"completed"`, you can download the generated PROTAC outputs as a zipped archive:
```bash
curl -o /storage/savi/saveenas/Projects/SynGlue_Py/outputs/results.zip \
     "http://127.0.0.1:8000/synglue/api/design/download/?job_id=YOUR_JOB_ID_HERE"
```

##### 🧪 Test 4: Submit a Screening Job via CSV Upload (POST)
To screen libraries of molecules for targeting capabilities, upload a SMILES CSV directly:
```bash
curl -X POST "http://127.0.0.1:8000/synglue/api/screen/submit_csv/" \
     -F "file=@NOXO_smiles_fixed_exit_vectors.csv"
```
**Expected JSON Response:**
```json
{"job_id": "7df3f4d6-849c-42b7-a342-a1f94c03ee73", "status": "queued"}
```
*(Query screening status and download screening results using `/synglue/api/screen/status/` and `/synglue/api/screen/download/` matching standard design patterns.)*

---

## 6. Stop, Remove & Restart the Container

### A — Stop the container (graceful shutdown)

```bash
docker stop synglue
```

**What happens:**
- Docker sends a `SIGTERM` signal to the main process (Uvicorn)
- Uvicorn stops accepting new requests
- Ongoing requests get a grace period (10s by default) to finish
- Docker sends `SIGKILL` if it hasn't exited after the timeout
- The container's filesystem is **preserved** — you can restart it later

**Verify it stopped:**
```bash
docker ps                    # synglue should NOT appear
docker ps -a                 # shows ALL containers (including stopped)
# CONTAINER ID   IMAGE           ...   STATUS                       NAMES
# xxxxxxxxxxxx   synglue-api          Exited (143) 5 seconds ago    synglue
```
Exit code 143 means it was killed by SIGTERM (normal).

### B — Restart the same container (preserves all data/mounts)

```bash
docker start synglue
```

**What happens:**
- Docker restarts the *existing* container (same ID, same mounts, same config)
- Uvicorn starts fresh
- All mounted volumes (`outputs/`, `data/`, `models/`, `repos/`) are still connected
- This is **fast** — no image rebuild needed

### C — Stop + start in one command

```bash
docker restart synglue
```
Equivalent to `docker stop synglue && docker start synglue`.

### D — Remove the container permanently

> ⚠️ Do this **only** if you want to permanently delete this container.
> You cannot `docker start` a removed container — you must `docker run` again.

```bash
docker stop synglue          # must be stopped first
docker rm synglue            # removes the container
```

**Verify it's removed:**
```bash
docker ps -a                 # synglue should NOT appear in any status
```

### E — Force removal (stop + remove in one step)

```bash
docker rm -f synglue
```
This forcefully stops and removes the container. Use with caution.

### F — Remove and create a fresh container

Use this when you want to start completely clean (but keep your data volumes):

```bash
# Step 1: Stop & remove old container
docker stop synglue && docker rm synglue

# Step 2: Run a fresh container (same command as section 4)
docker run -d --gpus all -p 8000:8000 \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/outputs:/app/outputs \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/data:/app/data \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/models:/app/models \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/repos:/app/repos \
  --name synglue synglue-api
```

### Decision flowchart

```
Is the container running?
├── Yes → Do you want to keep it?
│   ├── Yes → You're done.
│   └── No  → docker stop synglue
│              Will you need it again later?
│              ├── Yes → Leave it (docker start synglue later)
│              └── No  → docker rm synglue
└── No  → docker start synglue (if it exists)
         OR docker run ... (if it was removed)
```

---

## 7. Full Rebuild Cycle (Code Changes)

When you modify Python files (e.g., `app.py`, module code), you must rebuild the image.

### Step-by-step

```bash
# 1. Go to project root
cd /storage/savi/saveenas/Projects/SynGlue_Py

# 2. Stop & remove the current container
docker stop synglue && docker rm synglue

# 3. Rebuild the image with your changes
docker build --no-cache -t synglue-api .

# 4. Run a fresh container
docker run -d --gpus all -p 8000:8000 \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/outputs:/app/outputs \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/data:/app/data \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/models:/app/models \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/repos:/app/repos \
  --name synglue synglue-api

# 5. Verify
docker ps
curl http://127.0.0.1:8000/
```

**Note:** If you only changed files in `./repos/` (REINVENT/GROVER), you do NOT need to rebuild — just `docker restart synglue`. The repos are mounted as a volume, so changes are reflected instantly.

---

## 8. Useful Commands

### Open a shell inside the running container
```bash
docker exec -it synglue /bin/bash
```
Now you're inside the container at `/app/`. You can inspect files, run Python, etc.
Type `exit` or press Ctrl+D to leave.

### Run a Python script inside a specific Conda environment
```bash
docker exec synglue conda run -n Magnet python /app/your_script.py
docker exec synglue conda run -n reinvent python /app/repos/reinvent/script.py
```

### Copy files between host and container
```bash
# From container to host
docker cp synglue:/app/outputs/results.csv ./results.csv

# From host to container
docker cp ./input_file.csv synglue:/app/data/
```

### View live resource usage
```bash
docker stats synglue
```
Shows CPU %, memory, network I/O in real time. Ctrl+C to exit.

### List all images
```bash
docker images
```
Look for `synglue-api` in the list.

### Remove old/unused images (free disk space)
```bash
docker image prune -a
```

### View the container's full configuration
```bash
docker inspect synglue
```
This shows everything — environment variables, mounts, network settings, command, etc.

---

## 9. Container Internals

### Conda environments inside the image

| Environment | Base Command | Python | Installed Packages | Purpose |
|---|---|---|---|---|
| `Magnet` | `/opt/conda/envs/Magnet/bin/uvicorn` | 3.9 | fastapi, uvicorn, rdkit, pandas, scikit-learn, descriptastorus, biopython, matplotlib, seaborn, scipy, tqdm | **FastAPI server** — runs `app.py`, serves the API, does mapping/annotation |
| `reinvent` | `/opt/conda/envs/reinvent/bin/python` | 3.7 | reinvent-chemistry, reinvent-models, reinvent-scoring, numpy 1.21.6, scipy 1.7.3, pandas, pathos, torch (with CUDA patches) | **REINVENT4** — molecular generation, linker design, scoring |
| `admet` | `/opt/conda/envs/admet/bin/python` | — | ADMET prediction packages | **Solubility/ADMET** — absorption, distribution, metabolism, excretion, toxicity predictions |

### Symlink bridge
```
/opt/conda/envs/reinvent  →  /opt/conda/envs/<actual_reinvent_env_name>
```
This ensures hardcoded paths in REINVENT that reference `envs/reinvent/` still work.

### Key files inside `/app/`

| File | Purpose |
|---|---|
| `app.py` | FastAPI application — entry point for Uvicorn |
| `db_utils.py` | Database utilities for MagnetDB |
| `synglue_batch_inference.py` | Batch inference runner |
| `multiprocess_synglue.py` | Multi-processing pipeline |
| `structure_guided.py` | Structure-guided molecule design |
| `trie_structures.py` | Fragment-based TRIE data structure |
| `unified_synglue_pipeline.py` | End-to-end pipeline |

### Environment variable
```bash
PYTHONPATH=/app/repos/reinvent:/app/repos:/app/repos/grover
```
This is set in the Dockerfile so Python can `import` modules from REINVENT and GROVER repos.

### Dockerfile layers (from Dockerfile)

| Layer | What it does | Approx size |
|---|---|---|
| `FROM miniconda3` | Base image with Conda | ~1 GB |
| `apt-get install` | System build tools | ~200 MB |
| `COPY *.yml` | Environment YAML files | ~100 KB |
| `conda env create` × 3 | Creates 3 Conda environments | ~5-8 GB |
| `pip install` (reinvent) | REINVENT packages + fixes | ~500 MB |
| `pip install` (Magnet) | descriptastorus, sklearn | ~100 MB |
| `COPY .` | All source code | ~5 MB |
| **Total image size** | | **~7-10 GB** |

---

## 10. Troubleshooting

### Container exits immediately on start

```bash
docker logs synglue
```
**Common causes:**
- A Python import error (missing dependency)
- A missing file that `app.py` expects
- Conda environment not found

**Fix:** Read the traceback in logs, fix the issue, rebuild.

### `docker: Error response from daemon: could not select device driver "" with capabilities: [[gpu]]`

**Cause:** `--gpus all` was used but NVIDIA Container Toolkit is not installed.

**Fix:** Install it:
```bash
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```
Then retry `docker run`.

### Port 8000 already in use

```bash
sudo lsof -i :8000
```
Find the PID and kill the process, or use a different host port:
```bash
docker run -d --gpus all -p 8001:8000 ... --name synglue synglue-api
# Now access at http://localhost:8001
```

### Permission denied on mounted volumes

```bash
# Ensure host directories exist and are writable
mkdir -p /storage/savi/saveenas/Projects/SynGlue_Py/{outputs,data,models,repos}
chmod -R 755 /storage/savi/saveenas/Projects/SynGlue_Py/outputs
```

### `docker: command not found`

```bash
# Install Docker
sudo apt-get update && sudo apt-get install -y docker.io
sudo systemctl start docker
sudo systemctl enable docker
```

### Container runs but API returns connection refused

```bash
# Check if the container is actually running
docker ps

# Check the logs for errors
docker logs synglue

# Verify the port mapping
docker port synglue
# Expected: 8000/tcp -> 0.0.0.0:8000

# If port mapping is wrong, remove and re-run with correct -p flag
```

### GPU not accessible inside container

```bash
# Check inside container
docker exec synglue nvidia-smi

# If it fails, the container was started without --gpus all
# Stop, remove, and re-run with --gpus all
docker stop synglue && docker rm synglue
# Then re-run with --gpus all
```

### Out of disk space (Docker images/layers accumulate)

```bash
# Prune unused images, containers, volumes
docker system prune -a

# Check disk usage
docker system df
```
