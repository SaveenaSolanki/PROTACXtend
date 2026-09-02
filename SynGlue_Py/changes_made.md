# SynGlue Infrastructure & Path Configuration Change Log

This document lists every change made to the codebase to support dynamic path parameterization via environment variables and standard diagnostics prechecks.

---

## 1. File: `savi_module_4.py`
### Position: Lines 30 to 50
#### BEFORE:
```python
# 1. GLOBAL CONFIGURATION (Docker Paths)
# =============================================================================
CONFIG = {
    "e3_db_path": "/app/data/e3_ligand.csv",
    "fragments_db_path": "/app/data/warhead_fragments.pkl",
    "reinvent_env": "/opt/conda/envs/reinvent",
    "reinvent_dir": "/app/repos/reinvent",
    "output_dir": "/app/outputs",
    "batch_size": 16,
    "n_steps": 100,
    "grover_dir": "/app/repos/grover",
    "grover_checkpoint": "/app/models/grover_fixed.pt",
    "linkinvent_prior": "/app/models/linkinvent.prior",
    "pt_model": "/app/models/multitask_transformer.pt",
    "rf_dc50_model": "/app/models/rf_dc50.joblib",
    "rf_dmax_model": "/app/models/rf_dmax.joblib",
    "warhead_csv": "/app/data/grover_warhead.csv",
    "e3_csv": "/app/data/grover_e3.csv",
    "admet_env_python": "/opt/conda/envs/admet/bin/python",
    "linker_class_model": "/app/models/linker_classifier.pkl"
}
```

#### AFTER:
```python
# 1. GLOBAL CONFIGURATION (Docker & Host Environment Aware Paths)
# =============================================================================
# Resolve base paths from environment variables if present, otherwise auto-detect Docker vs. Host
BASE_DIR = os.environ.get("SYNGLUE_BASE_DIR", "/app" if os.path.exists("/app/data") else "/storage/savi/saveenas/Projects/SynGlue_Py")
DATA_DIR = os.environ.get("SYNGLUE_DATA_DIR", os.path.join(BASE_DIR, "data"))
MODEL_DIR = os.environ.get("SYNGLUE_MODEL_DIR", os.path.join(BASE_DIR, "models"))
OUTPUT_DIR = os.environ.get("SYNGLUE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
REPOS_DIR = os.environ.get("SYNGLUE_REPOS_DIR", os.path.join(BASE_DIR, "repos"))

CONFIG = {
    "e3_db_path": os.path.join(DATA_DIR, "e3_ligand.csv"),
    "fragments_db_path": os.path.join(DATA_DIR, "warhead_fragments.pkl"),
    "reinvent_env": os.environ.get("SYNGLUE_REINVENT_ENV", "/opt/conda/envs/reinvent" if os.path.exists("/opt/conda/envs/reinvent") else "/home/saveenas/miniconda3/envs/reinvent.v3.2"),
    "reinvent_dir": os.path.join(REPOS_DIR, "reinvent"),
    "output_dir": OUTPUT_DIR,
    "batch_size": 16,
    "n_steps": 100,
    "grover_dir": os.path.join(REPOS_DIR, "grover"),
    "grover_checkpoint": os.path.join(MODEL_DIR, "grover_fixed.pt"),
    "linkinvent_prior": os.path.join(MODEL_DIR, "linkinvent.prior"),
    "pt_model": os.path.join(MODEL_DIR, "multitask_transformer.pt"),
    "rf_dc50_model": os.path.join(MODEL_DIR, "rf_dc50.joblib"),
    "rf_dmax_model": os.path.join(MODEL_DIR, "rf_dmax.joblib"),
    "warhead_csv": os.path.join(DATA_DIR, "grover_warhead.csv"),
    "e3_csv": os.path.join(DATA_DIR, "grover_e3.csv"),
    "admet_env_python": os.environ.get("SYNGLUE_ADMET_ENV_PYTHON", "/opt/conda/envs/admet/bin/python" if os.path.exists("/opt/conda/envs/admet/bin/python") else "/home/saveenas/miniconda3/envs/admet/bin/python"),
    "linker_class_model": os.path.join(MODEL_DIR, "linker_classifier.pkl")
}
```

---

## 2. File: `module_4.py`
### Position: Lines 604 to 621
#### BEFORE:
```python
    CONFIG = {
        "e3_db_path": "/storage/savi/saveenas/Projects/SynGlue_Py/data/e3_ligand.csv",
        "fragments_db_path": "/storage/savi/saveenas/Projects/SynGlue_Py/data/warhead_fragments.pkl",
        "reinvent_dir": "/storage/savi/saveenas/Projects/SynGlue_Py/repos/reinvent",
        "reinvent_env": "/home/saveenas/miniconda3/envs/reinvent.v3.2",
        "output_dir": "/storage/savi/saveenas/Projects/SynGlue_Py/outputs",
        "batch_size": 16, 
        "n_steps": 100,
        "grover_dir": "/storage/savi/saveenas/Projects/SynGlue_Py/repos/grover",
        "grover_checkpoint": "/storage/savi/saveenas/Projects/SynGlue_Py/models/grover_fixed.pt",
        "pt_model": "/storage/savi/saveenas/Projects/SynGlue_Py/models/multitask_transformer.pt",
        "rf_dc50_model": "/storage/savi/saveenas/Projects/SynGlue_Py/models/rf_dc50.joblib",
        "rf_dmax_model": "/storage/savi/saveenas/Projects/SynGlue_Py/models/rf_dmax.joblib",
        "warhead_csv": "/storage/savi/saveenas/Projects/SynGlue_Py/data/grover_warhead.csv",
        "e3_csv": "/storage/savi/saveenas/Projects/SynGlue_Py/data/grover_e3.csv",
        "admet_env_python": "/home/saveenas/miniconda3/envs/admet/bin/python",
        "linker_class_model": "/storage/savi/saveenas/Projects/SynGlue_Py/models/linker_classifier.pkl"
    }
```

#### AFTER:
```python
    BASE_DIR = os.environ.get("SYNGLUE_BASE_DIR", "/app" if os.path.exists("/app/data") else "/storage/savi/saveenas/Projects/SynGlue_Py")
    DATA_DIR = os.environ.get("SYNGLUE_DATA_DIR", os.path.join(BASE_DIR, "data"))
    MODEL_DIR = os.environ.get("SYNGLUE_MODEL_DIR", os.path.join(BASE_DIR, "models"))
    OUTPUT_DIR = os.environ.get("SYNGLUE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
    REPOS_DIR = os.environ.get("SYNGLUE_REPOS_DIR", os.path.join(BASE_DIR, "repos"))

    CONFIG = {
        "e3_db_path": os.path.join(DATA_DIR, "e3_ligand.csv"),
        "fragments_db_path": os.path.join(DATA_DIR, "warhead_fragments.pkl"),
        "reinvent_env": os.environ.get("SYNGLUE_REINVENT_ENV", "/opt/conda/envs/reinvent" if os.path.exists("/opt/conda/envs/reinvent") else "/home/saveenas/miniconda3/envs/reinvent.v3.2"),
        "reinvent_dir": os.path.join(REPOS_DIR, "reinvent"),
        "output_dir": OUTPUT_DIR,
        "batch_size": 16,
        "n_steps": 100,
        "grover_dir": os.path.join(REPOS_DIR, "grover"),
        "grover_checkpoint": os.path.join(MODEL_DIR, "grover_fixed.pt"),
        "pt_model": os.path.join(MODEL_DIR, "multitask_transformer.pt"),
        "rf_dc50_model": os.path.join(MODEL_DIR, "rf_dc50.joblib"),
        "rf_dmax_model": os.path.join(MODEL_DIR, "rf_dmax.joblib"),
        "warhead_csv": os.path.join(DATA_DIR, "grover_warhead.csv"),
        "e3_csv": os.path.join(DATA_DIR, "grover_e3.csv"),
        "admet_env_python": os.environ.get("SYNGLUE_ADMET_ENV_PYTHON", "/opt/conda/envs/admet/bin/python" if os.path.exists("/opt/conda/envs/admet/bin/python") else "/home/saveenas/miniconda3/envs/admet/bin/python"),
        "linker_class_model": os.path.join(MODEL_DIR, "linker_classifier.pkl")
    }
```

---

## 3. File: `run_synglue_batch_from_csv.py`
### Position: Lines 37 to 62
#### BEFORE:
```python
CONFIG = {
    "e3_db_path": "/storage/savi/saveenas/Projects/SynGlue_Py/data/e3_ligand.csv",
    "fragments_db_path": "/storage/savi/saveenas/Projects/SynGlue_Py/data/warhead_fragments.pkl",

    "reinvent_dir": "/storage/savi/saveenas/Projects/SynGlue_Py/repos/reinvent",
    "reinvent_env": "/home/saveenas/miniconda3/envs/reinvent.v3.2",

    "output_dir": "/storage/savi/saveenas/Projects/SynGlue_Py/outputs",

    "batch_size": 16,
    "n_steps": 100,

    "grover_dir": "/storage/savi/saveenas/Projects/SynGlue_Py/repos/grover",
    "grover_checkpoint": "/storage/savi/saveenas/Projects/SynGlue_Py/models/grover_fixed.pt",

    "pt_model": "/storage/savi/saveenas/Projects/SynGlue_Py/models/multitask_transformer.pt",
    "rf_dc50_model": "/storage/savi/saveenas/Projects/SynGlue_Py/models/rf_dc50.joblib",
    "rf_dmax_model": "/storage/savi/saveenas/Projects/SynGlue_Py/models/rf_dmax.joblib",

    "warhead_csv": "/storage/savi/saveenas/Projects/SynGlue_Py/data/grover_warhead.csv",
    "e3_csv": "/storage/savi/saveenas/Projects/SynGlue_Py/data/grover_e3.csv",

    "admet_env_python": "/home/saveenas/miniconda3/envs/admet/bin/python",

    "linker_class_model": "/storage/savi/saveenas/Projects/SynGlue_Py/models/linker_classifier.pkl",
}
```

#### AFTER:
```python
BASE_DIR = os.environ.get("SYNGLUE_BASE_DIR", "/app" if os.path.exists("/app/data") else "/storage/savi/saveenas/Projects/SynGlue_Py")
DATA_DIR = os.environ.get("SYNGLUE_DATA_DIR", os.path.join(BASE_DIR, "data"))
MODEL_DIR = os.environ.get("SYNGLUE_MODEL_DIR", os.path.join(BASE_DIR, "models"))
OUTPUT_DIR = os.environ.get("SYNGLUE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
REPOS_DIR = os.environ.get("SYNGLUE_REPOS_DIR", os.path.join(BASE_DIR, "repos"))

CONFIG = {
    "e3_db_path": os.path.join(DATA_DIR, "e3_ligand.csv"),
    "fragments_db_path": os.path.join(DATA_DIR, "warhead_fragments.pkl"),

    "reinvent_dir": os.path.join(REPOS_DIR, "reinvent"),
    "reinvent_env": os.environ.get("SYNGLUE_REINVENT_ENV", "/opt/conda/envs/reinvent" if os.path.exists("/opt/conda/envs/reinvent") else "/home/saveenas/miniconda3/envs/reinvent.v3.2"),

    "output_dir": OUTPUT_DIR,

    "batch_size": 16,
    "n_steps": 100,

    "grover_dir": os.path.join(REPOS_DIR, "grover"),
    "grover_checkpoint": os.path.join(MODEL_DIR, "grover_fixed.pt"),

    "pt_model": os.path.join(MODEL_DIR, "multitask_transformer.pt"),
    "rf_dc50_model": os.path.join(MODEL_DIR, "rf_dc50.joblib"),
    "rf_dmax_model": os.path.join(MODEL_DIR, "rf_dmax.joblib"),

    "warhead_csv": os.path.join(DATA_DIR, "grover_warhead.csv"),
    "e3_csv": os.path.join(DATA_DIR, "grover_e3.csv"),

    "admet_env_python": os.environ.get("SYNGLUE_ADMET_ENV_PYTHON", "/opt/conda/envs/admet/bin/python" if os.path.exists("/opt/conda/envs/admet/bin/python") else "/home/saveenas/miniconda3/envs/admet/bin/python"),

    "linker_class_model": os.path.join(MODEL_DIR, "linker_classifier.pkl"),
}
```

---

## 4. File: `app.py`

### Change 4.1: Line 45
#### BEFORE:
```python
        db_dir = os.environ.get("SYNGLUE_DB_DIR", "/app/data")
```
#### AFTER:
```python
        db_dir = os.environ.get("SYNGLUE_DATA_DIR", os.environ.get("SYNGLUE_DB_DIR", "/app/data"))
```

### Change 4.2: Line 97
#### BEFORE:
```python
        output_dir = os.path.join("/app/outputs", "Design_Runs", job_id)
```
#### AFTER:
```python
        output_dir = os.path.join(os.environ.get("SYNGLUE_OUTPUT_DIR", "/app/outputs"), "Design_Runs", job_id)
```

### Change 4.3: Line 289
#### BEFORE:
```python
        output_dir = os.path.join("/app/outputs", "Screen_Runs", job_id)
```
#### AFTER:
```python
        output_dir = os.path.join(os.environ.get("SYNGLUE_OUTPUT_DIR", "/app/outputs"), "Screen_Runs", job_id)
```

### Change 4.4: Line 318
#### BEFORE:
```python
        output_dir = os.path.join("/app/outputs", "Screen_Runs", job_id)
```
#### AFTER:
```python
        output_dir = os.path.join(os.environ.get("SYNGLUE_OUTPUT_DIR", "/app/outputs"), "Screen_Runs", job_id)
```

### Change 4.5: Line 343
#### BEFORE:
```python
        db_dir = os.environ.get("SYNGLUE_DB_DIR", "/app/data")
```
#### AFTER:
```python
        db_dir = os.environ.get("SYNGLUE_DATA_DIR", os.environ.get("SYNGLUE_DB_DIR", "/app/data"))
```

---

## 5. File: `precheck.py` [NEW FILE]
*   **What it does:** Independent diagnostics checking workspace health, configurations, datasets, and ml models. Optimized for Python 3.5.2 Host systems.
