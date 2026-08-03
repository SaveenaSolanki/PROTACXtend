
curl -X POST "http://127.0.0.1:8000/synglue/api/submit_job/" \
  -H "Content-Type: application/json" \
  -d '{"target": "EGFR", "threshold": 80}'
curl "http://127.0.0.1:8000/synglue/api/job_status/?job_id=YOUR_JOB_ID"
curl -O "http://127.0.0.1:8000/synglue/api/download_results/?job_id=YOUR_JOB_ID"


# SynGlue API Documentation

## Overview
This API provides endpoints for two main workflows:

- **Design jobs** (PROTAC design): `/synglue/api/design/`
- **Screen jobs** (hybrid mapping): `/synglue/api/screen/`

All endpoints are under `/synglue/api/design/` or `/synglue/api/screen/`.

---


## 1. Design Job Endpoints


### Submit a Design Job
**Endpoint:** `POST /synglue/api/design/submit/`

**Request Body (JSON):**
```
{
  "target": "EGFR",         // (string) Target protein name (case-insensitive)
  "threshold": 80            // (float, optional, default: 75.0) Minimum fragment percentage
}
```

**Example:**
```bash
curl -X POST "http://127.0.0.1:8000/synglue/api/design/submit/" \
  -H "Content-Type: application/json" \
  -d '{"target": "EGFR", "threshold": 80}'
```

**Response:**
```
{
  "job_id": "<job-uuid>",
  "status": "queued"
}
```


### Check Design Job Status
**Endpoint:** `GET /synglue/api/design/status/?job_id=<job-uuid>`

**Example:**
```bash
curl "http://127.0.0.1:8000/synglue/api/design/status/?job_id=YOUR_JOB_ID"
```

**Response:**
```
{
  "job_id": "<job-uuid>",
  "status": "queued" | "running" | "completed" | "failed",
  "error": <string or null>,
  "queue_position": <int or null>
}
```


### Download Design Results
**Endpoint:** `GET /synglue/api/design/download/?job_id=<job-uuid>`

**Example:**
```bash
curl -O "http://127.0.0.1:8000/synglue/api/design/download/?job_id=YOUR_JOB_ID"
```

If the job is completed, this downloads a zip file with your results. If not ready, you will receive an error message.

---

## 2. Screen Job Endpoints



### Submit a Screen Job (JSON)
**Endpoint:** `POST /synglue/api/screen/submit/`

**Request Body (JSON):**
```
{
  "molecules": [
    {"name": "Aspirin", "smiles": "CC(=O)Oc1ccccc1C(=O)O"},
    {"name": "Imatinib", "smiles": "CC1=CC=CC=C1"}
  ]
}
```

**Example:**
```bash
curl -X POST "http://127.0.0.1:8000/synglue/api/screen/submit/" \
  -H "Content-Type: application/json" \
  -d '{"molecules": [{"name": "Aspirin", "smiles": "CC(=O)Oc1ccccc1C(=O)O"}, {"name": "Imatinib", "smiles": "CC1=CC=CC=C1"}]}'
```

**Response:**
```
{
  "job_id": "<job-uuid>",
  "status": "queued"
}
```

### Submit a Screen Job (CSV Upload)
**Endpoint:** `POST /synglue/api/screen/submit_csv/`

**Description:** Accepts a CSV file upload with columns `SMILES` and `NAME` (case-insensitive). Each row should represent a molecule.

**Form Data:**
- `file`: The CSV file to upload.

**CSV Example:**
```
SMILES,NAME
CC(=O)Oc1ccccc1C(=O)O,Aspirin
CC1=CC=CC=C1,Imatinib
```

**Example using curl:**
```bash
curl -X POST "http://127.0.0.1:8000/synglue/api/screen/submit_csv/" \
  -F "file=@molecules.csv"
```

**Response:**
```
{
  "job_id": "<job-uuid>",
  "status": "queued"
}
```


### Check Screen Job Status
**Endpoint:** `GET /synglue/api/screen/status/?job_id=<job-uuid>`

**Example:**
```bash
curl "http://127.0.0.1:8000/synglue/api/screen/status/?job_id=YOUR_JOB_ID"
```

**Response:**
```
{
  "job_id": "<job-uuid>",
  "status": "queued" | "running" | "completed" | "failed",
  "error": <string or null>,
  "result_path": <string>,
  "queue_position": <int or null>
}
```


### Download Screen Results
**Endpoint:** `GET /synglue/api/screen/download/?job_id=<job-uuid>`

**Example:**
```bash
curl -O "http://127.0.0.1:8000/synglue/api/screen/download/?job_id=   bae0746f-7989-4ae1-bf66-b42f9e70e661"
```

If the job is completed, this downloads a CSV file with your results. If not ready, you will receive an error message.

---

## 3. Root Endpoint

**Endpoint:** `GET /`

Returns a simple status message for health checks.

---

## Notes
- **Rate Limiting:** Each endpoint enforces per-IP rate limits. If exceeded, a 429 error is returned.
- **Job Queue:** Jobs are queued and processed in order. Only one job of each type runs at a time.
- **Error Handling:** If a job fails, the `error` field in status will contain a message.
- **Output Folders:**
  - Design jobs: `outputs/Design_Runs/{job_id}/`
  - Screen jobs: `outputs/Screen_Runs/{job_id}/`



