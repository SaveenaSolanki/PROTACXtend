
import os
import uuid
import shutil
import zipfile
import time
import logging
import threading
import pandas as pd
import io
import csv
from typing import Optional, List, Dict
from fastapi import FastAPI, BackgroundTasks, Query, Request, APIRouter, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

# Internal SynGlue Modules
import savi_module_4 as module_4  
import multiprocess_synglue
from db_utils import get_db, init_db, get_next_queue_no

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SynGlueAPI")


# --- Lean Trie Globals ---
import pickle


# --- Trie/Hash Globals for Screening ---
TRIE_GLOBAL = None
HASH_GLOBAL = None

app = FastAPI(title="SynGlue Design & Screening API")
# --- Startup & Include ---

# --- FastAPI Startup Event: Load Trie/Hash ---
@app.on_event("startup")
def load_trie_and_hash():
    global TRIE_GLOBAL, HASH_GLOBAL
    try:
        db_dir = os.environ.get("SYNGLUE_DATA_DIR", os.environ.get("SYNGLUE_DB_DIR", "/app/data"))
        trie_p = os.path.join(db_dir, "Lean_MagnetDB_Trie.pkl")
        hash_p = os.path.join(db_dir, "Clean_Metadata_Hash_FINAL_GENE_FIXED.pkl")
        meta_p = os.path.join(db_dir, "Targets_for_magnetdb.csv")
        with open(trie_p, "rb") as f:
            TRIE_GLOBAL = pickle.load(f)
        # Use multiprocess_synglue's patcher for hash
        HASH_GLOBAL = multiprocess_synglue.load_and_patch_database(hash_p, meta_p)
        logger.info("Trie and Hash loaded at startup.")
    except Exception as e:
        logger.error("Trie/Hash loading failed at startup: %s", e)

# --- CORS Configuration ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuration Helper ---
def get_config():
    """Safely extracts CONFIG from module_4 without side-effects."""
    try:
        if hasattr(module_4, 'CONFIG'):
            return module_4.CONFIG.copy()
        import ast, inspect
        source = inspect.getsource(module_4)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if hasattr(target, 'id') and target.id == 'CONFIG':
                        config_ns = {}
                        exec(compile(ast.Module([node], []), '<ast>', 'exec'), module_4.__dict__, config_ns)
                        return config_ns['CONFIG'].copy()
    except Exception as e:
        logger.error(f"Config extraction failed: {e}")
    raise AttributeError('CONFIG not found or inaccessible in module_4')

# =============================================================================
# --- DESIGN PIPELINE LOGIC ---
# =============================================================================

def run_pipeline(job_id: str, target: str, threshold: float):
    """Background task to run the PROTAC design pipeline."""
    try:
        # 1. Mark as Running
        with get_db() as conn:
            conn.execute("UPDATE jobs SET status=? WHERE job_id=?", ("running", job_id))

        output_dir = os.path.join(os.environ.get("SYNGLUE_OUTPUT_DIR", "/app/outputs"), "Design_Runs", job_id)
        os.makedirs(output_dir, exist_ok=True)
        
        CONFIG = get_config()
        CONFIG["output_dir"] = output_dir

        # 2. Database Selection
        logger.info(f"[{job_id}] Selecting fragments for {target}...")
        E3 = pd.read_csv(CONFIG["e3_db_path"])
        AA = pd.read_pickle(CONFIG["fragments_db_path"])
        selector = module_4.SynGlueSelector(E3)
        
        subset_AA = AA[(AA['Protein'].str.upper() == target.upper()) & (AA['percentage'] >= threshold)]
        if subset_AA.empty:
            raise ValueError(f"No fragments found for {target} above {threshold}%")

        payload = selector.run_selection(target, subset_AA)
        if "Error" in payload:
            raise ValueError(payload["Error"])

        # 3. Generative Phase (Link-INVENT)
        wh_smi = payload['Warhead_SMILES']
        e3_smi = payload['E3_Tagged_SMILES']
        module_4.visualize_exit_vectors(wh_smi, e3_smi, output_dir)
        
        pair_string = f"{wh_smi}|{e3_smi}"
        # PASSING JOB_ID TO LINK-INVENT FOR UNIQUE PATHS
        generated_df, out_path = module_4.run_link_invent(pair_string, CONFIG, job_id=job_id)
        
        if generated_df is None:
            raise RuntimeError("Link-INVENT engine failed to generate molecules.")

        # 4. Scoring & ADMET
        predicted_df = module_4.run_ai_predictions(generated_df, out_path, CONFIG)
        classified_df = module_4.run_linker_classification(predicted_df, wh_smi, e3_smi, out_path, CONFIG)
        module_4.visualize_top_protacs(classified_df, out_path, top_n=3)
        module_4.run_admet_ai(classified_df, out_path, CONFIG, top_n=20)

        # 5. Package Results
        zip_path = os.path.join(output_dir, f"{job_id}_results.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:

            admet_csv = os.path.join(output_dir, 'ADMET_Predictions_Top_20.csv')
            admet_csv_written = False
            for root, _, files in os.walk(output_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, output_dir)
                    # Always include ADMET_Predictions_Top_20.csv
                    if file == 'ADMET_Predictions_Top_20.csv':
                        zipf.write(file_path, rel_path)
                        admet_csv_written = True
                        continue
                    if file.endswith(('.zip', '.json')) or file == 'progress.log':
                        continue
                    zipf.write(file_path, rel_path)
            # If for some reason the ADMET csv was not found in the walk, try to add it directly
            if not admet_csv_written and os.path.exists(admet_csv):
                zipf.write(admet_csv, os.path.relpath(admet_csv, output_dir))

        with get_db() as conn:
            conn.execute("UPDATE jobs SET status=?, output_dir=?, zip_path=?, error=NULL WHERE job_id=?", 
                         ("completed", output_dir, zip_path, job_id))

    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}")
        with get_db() as conn:
            conn.execute("UPDATE jobs SET status=?, error=? WHERE job_id=?", ("failed", str(e), job_id))
    finally:
        _start_next_queued_job("design")

def _start_next_queued_job(job_type: str):
    """Triggers the next job in the queue."""
    with get_db() as conn:
        query = "SELECT job_id, target, threshold FROM jobs WHERE status = 'queued' AND job_type=? ORDER BY queue_no ASC LIMIT 1"
        row = conn.execute(query, (job_type,)).fetchone()
    if row:
        if job_type == "design":
            threading.Thread(target=run_pipeline, args=(row[0], row[1], row[2])).start()
        else:
            # Handle next screen job
            pass

# =============================================================================
# --- RATE LIMITING ---
# =============================================================================

RATE_LIMITS = {
    'submit_job': {'per_second': 5, 'per_minute': 10},
    'job_status': {'per_second': 5, 'per_minute': 20},
    'download_results': {'per_second': 5, 'per_minute': 20},
}

def is_rate_limited(ip: str, endpoint: str) -> (bool, str):
    now = time.time()
    per_second = RATE_LIMITS[endpoint]['per_second']
    per_minute = RATE_LIMITS[endpoint]['per_minute']
    with get_db() as conn:
        conn.execute("DELETE FROM rate_limit WHERE timestamp < ?", (now - 60,))
        conn.execute("INSERT INTO rate_limit (ip_address, endpoint, timestamp) VALUES (?, ?, ?)", (ip, endpoint, now))
        count_1s = conn.execute("SELECT COUNT(*) FROM rate_limit WHERE ip_address=? AND endpoint=? AND timestamp > ?", (ip, endpoint, now - 1)).fetchone()[0]
        if count_1s > per_second: return True, f"Rate limit exceeded: >{per_second} req/s"
        count_60s = conn.execute("SELECT COUNT(*) FROM rate_limit WHERE ip_address=? AND endpoint=? AND timestamp > ?", (ip, endpoint, now - 60)).fetchone()[0]
        if count_60s > per_minute: return True, f"Rate limit exceeded: >{per_minute} req/min"
    return False, ""

# =============================================================================
# --- ROUTERS & ENDPOINTS ---
# =============================================================================

design_router = APIRouter(prefix="/synglue/api/design", tags=["Design"])
screen_router = APIRouter(prefix="/synglue/api/screen", tags=["Screening"])

class JobRequest(BaseModel):
    target: str
    threshold: Optional[float] = 75.0

class ScreenJobRequest(BaseModel):
    molecules: List[Dict[str, str]]

# --- Design Endpoints ---

@design_router.post("/submit/")
async def submit_job(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
        job_req = JobRequest(**body)
        ip = request.client.host
        limited, reason = is_rate_limited(ip, 'submit_job')
        if limited:
            return JSONResponse(status_code=429, content={"error": reason})
        job_id = str(uuid.uuid4())
        queue_no = get_next_queue_no()
        with get_db() as conn:
            conn.execute(
                "INSERT INTO jobs (job_id, job_type, target, threshold, status, queue_no, ip_address) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job_id, "design", job_req.target, job_req.threshold, "queued", queue_no, ip)
            )
            running_count = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'running' AND job_type='design'").fetchone()[0]
        if running_count == 0:
            background_tasks.add_task(run_pipeline, job_id, job_req.target, job_req.threshold)
        return {"job_id": job_id, "status": "queued"}
    except Exception as e:
        logger.error(f"Error in submit_job: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@design_router.get("/status/")
async def job_status(request: Request, job_id: str = Query(...)):
    try:
        with get_db() as conn:
            row = conn.execute("SELECT status, error, queue_no FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            return JSONResponse(status_code=404, content={"error": "Job not found"})
        pos = None
        if row[0] in ("queued", "running"):
            with get_db() as conn:
                pos = conn.execute("SELECT COUNT(*) FROM jobs WHERE (status='queued' OR status='running') AND queue_no < ?", (row[2],)).fetchone()[0] + 1
        return {"job_id": job_id, "status": row[0], "error": row[1], "queue_position": pos}
    except Exception as e:
        logger.error(f"Error in job_status: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@design_router.get("/download/")
async def download_results(request: Request, job_id: str = Query(...)):
    try:
        with get_db() as conn:
            row = conn.execute("SELECT zip_path, status FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row or row[1] != "completed":
            return JSONResponse(status_code=404, content={"error": "Results not ready"})
        return FileResponse(row[0], filename=f"SynGlue_{job_id}_results.zip")
    except Exception as e:
        logger.error(f"Error in download_results: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- Screening Endpoints ---

@screen_router.post("/submit_csv/")
async def submit_screen_csv(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    try:
        content = await file.read()
        decoded = content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
        molecules = []
        for row in reader:
            name = row.get('NAME') or row.get('Name') or row.get('name')
            smiles = row.get('SMILES') or row.get('Smiles') or row.get('smiles')
            if name and smiles:
                molecules.append({"name": name, "smiles": smiles})
        if not molecules:
            return JSONResponse(status_code=400, content={"error": "No valid molecules found"})
        job_id = str(uuid.uuid4())
        queue_no = get_next_queue_no('screen')
        output_dir = os.path.join(os.environ.get("SYNGLUE_OUTPUT_DIR", "/app/outputs"), "Screen_Runs", job_id)
        os.makedirs(output_dir, exist_ok=True)
        input_path = os.path.join(output_dir, "input.csv")
        with open(input_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Name", "SMILES"])
            for mol in molecules:
                writer.writerow([mol["name"], mol["smiles"]])
        with get_db() as conn:
            conn.execute("INSERT INTO jobs (job_id, job_type, status, queue_no, output_dir) VALUES (?, ?, ?, ?, ?)",
                         (job_id, 'screen', "queued", queue_no, output_dir))
        background_tasks.add_task(run_hybrid_mapping, job_id, input_path, output_dir)
        return {"job_id": job_id, "status": "queued"}
    except Exception as e:
        logger.error(f"Error in submit_screen_csv: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- New: Screen Job Submission (JSON) ---
@screen_router.post("/submit/")
async def submit_screen(background_tasks: BackgroundTasks, request: Request):
    try:
        body = await request.json()
        molecules = body.get("molecules", [])
        if not isinstance(molecules, list) or not all(isinstance(m, dict) and "name" in m and "smiles" in m for m in molecules):
            return JSONResponse(status_code=400, content={"error": "Request must contain a 'molecules' list of {name, smiles} objects."})
        if not molecules:
            return JSONResponse(status_code=400, content={"error": "No valid molecules found in request."})
        job_id = str(uuid.uuid4())
        queue_no = get_next_queue_no('screen')
        output_dir = os.path.join(os.environ.get("SYNGLUE_OUTPUT_DIR", "/app/outputs"), "Screen_Runs", job_id)
        os.makedirs(output_dir, exist_ok=True)
        input_path = os.path.join(output_dir, "input.json")
        # Save molecules as CSV for compatibility with engine
        csv_path = os.path.join(output_dir, "input.csv")
        import csv as pycsv
        with open(csv_path, "w", newline="") as f:
            writer = pycsv.writer(f)
            writer.writerow(["Name", "SMILES"])
            for mol in molecules:
                writer.writerow([mol["name"], mol["smiles"]])
        with get_db() as conn:
            conn.execute("INSERT INTO jobs (job_id, job_type, status, queue_no, output_dir) VALUES (?, ?, ?, ?, ?)",
                         (job_id, 'screen', "queued", queue_no, output_dir))
        background_tasks.add_task(run_hybrid_mapping, job_id, csv_path, output_dir)
        return {"job_id": job_id, "status": "queued"}
    except Exception as e:
        logger.error(f"Error in submit_screen: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

def run_hybrid_mapping(job_id, input_path, output_dir):
    with get_db() as conn:
        conn.execute("UPDATE jobs SET status=? WHERE job_id=?", ("running", job_id))
    try:
        global TRIE_GLOBAL, HASH_GLOBAL
        db_dir = os.environ.get("SYNGLUE_DATA_DIR", os.environ.get("SYNGLUE_DB_DIR", "/app/data"))
        workers = int(os.environ.get("SYNGLUE_WORKERS", "10"))
        # Patch multiprocess_synglue to use preloaded trie/hash if available
        if TRIE_GLOBAL is not None and HASH_GLOBAL is not None:
            multiprocess_synglue.GLOBAL_TRIE = TRIE_GLOBAL
            multiprocess_synglue.GLOBAL_HASH = HASH_GLOBAL
            result_file = multiprocess_synglue.run_hybrid_engine(
                db_dir=db_dir,
                output_dir=output_dir,
                num_workers=workers,
                csv_path=input_path,
                use_loaded_trie=True
            )
        else:
            result_file = multiprocess_synglue.run_hybrid_engine(
                db_dir=db_dir,
                output_dir=output_dir,
                num_workers=workers,
                csv_path=input_path
            )
        zip_path = os.path.join(output_dir, f"{job_id}_screen_results.zip")
        if result_file and os.path.exists(result_file):
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                zipf.write(result_file, os.path.basename(result_file))
            with get_db() as conn:
                conn.execute("UPDATE jobs SET status=?, zip_path=? WHERE job_id=?", ("completed", zip_path, job_id))
    except Exception as e:
        with get_db() as conn:
            conn.execute("UPDATE jobs SET status=?, error=? WHERE job_id=?", ("failed", str(e), job_id))

# --- Screen Job Status Endpoint ---
@screen_router.get("/status/")
async def screen_job_status(request: Request, job_id: str = Query(...)):
    try:
        with get_db() as conn:
            row = conn.execute("SELECT status, error, queue_no, zip_path FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            return JSONResponse(status_code=404, content={"error": "Job not found"})
        pos = None
        if row[0] in ("queued", "running"):
            with get_db() as conn:
                pos = conn.execute("SELECT COUNT(*) FROM jobs WHERE (status='queued' OR status='running') AND queue_no < ?", (row[2],)).fetchone()[0] + 1
        return {
            "job_id": job_id,
            "status": row[0],
            "error": row[1],
            "result_path": row[3],
            "queue_position": pos
        }
    except Exception as e:
        logger.error(f"Error in screen_job_status: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- Screen Job Download Endpoint ---
@screen_router.get("/download/")
async def download_screen_results(request: Request, job_id: str = Query(...)):
    try:
        with get_db() as conn:
            row = conn.execute("SELECT zip_path, status FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row or row[1] != "completed":
            return JSONResponse(status_code=404, content={"error": "Results not ready"})
        return FileResponse(row[0], filename=f"SynGlue_{job_id}_screen_results.zip")
    except Exception as e:
        logger.error(f"Error in download_screen_results: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- Startup & Include ---



app.include_router(design_router)
app.include_router(screen_router)

@app.get("/")
def root():
    try:
        return {"status": "online", "message": "SynGlue API is running"}
    except Exception as e:
        logger.error(f"Error in root endpoint: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})