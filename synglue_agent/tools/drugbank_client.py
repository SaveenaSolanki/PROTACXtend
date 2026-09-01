"""DrugBank client with local import and keyed API path.

DrugBank requires licensed access. PROTACXtend therefore supports a local
CSV export instead of pretending to call an unrestricted public API.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from synglue_agent.backend.schemas import TargetRecord
from synglue_agent.tools.online_ligand_miner import load_local_drugbank_binders


DRUGBANK_API_BASE = os.getenv("DRUGBANK_API_BASE_URL", "https://api.drugbank.com/v1")


def retrieve_drugbank_binders(target_record: TargetRecord, drugbank_path: str | Path | None = None):
    path = Path(drugbank_path) if drugbank_path else None
    return load_local_drugbank_binders(target_record, path)


def _drugbank_api_key() -> str | None:
    return os.getenv("DRUGBANK_API_KEY") or os.getenv("DRUGBANK_TOKEN")


def drugbank_api_status() -> dict[str, Any]:
    key = _drugbank_api_key()
    return {
        "available": bool(key),
        "base_url": DRUGBANK_API_BASE,
        "auth_mode": "bearer_token",
        "note": "Set DRUGBANK_API_KEY (or DRUGBANK_TOKEN) to enable executable online lookup.",
    }


def _request_drugbank(path: str, params: dict[str, Any] | None = None, timeout: float = 10.0) -> tuple[dict[str, Any] | None, str | None, str]:
    key = _drugbank_api_key()
    if not key:
        return None, "DrugBank API credentials are not configured.", f"{DRUGBANK_API_BASE}/{path}"
    query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v not in (None, "")})
    url = f"{DRUGBANK_API_BASE}/{path}"
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "Authorization": f"Bearer {key}", "User-Agent": "PROTACXtend/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8")), None, url
    except urllib.error.HTTPError as exc:
        return None, f"DrugBank HTTP error {exc.code}: {exc.reason}", url
    except urllib.error.URLError as exc:
        return None, f"DrugBank network error: {exc.reason}", url
    except TimeoutError:
        return None, "DrugBank request timed out.", url
    except json.JSONDecodeError as exc:
        return None, f"DrugBank returned invalid JSON: {exc}", url


def search_drugbank_compounds(query: str, top_k: int = 20, timeout: float = 10.0) -> dict[str, Any]:
    request_query = {"query": query, "top_k": top_k}
    if not query or not str(query).strip():
        return {"source": "DrugBank API", "query": request_query, "success": False, "error": "Query is required.", "records": []}
    payload, error, url = _request_drugbank("us/drugs", params={"q": query, "limit": max(int(top_k), 1)}, timeout=timeout)
    if error:
        return {"source": "DrugBank API", "query": request_query, "success": False, "error": error, "records": [], "source_url": url}
    raw = payload.get("data") or payload.get("drugs") or []
    records = []
    for item in raw[:top_k]:
        records.append(
            {
                "source": "DrugBank API",
                "target": None,
                "target_id": None,
                "molecule_name": item.get("name"),
                "smiles": item.get("smiles") or item.get("canonical_smiles"),
                "activity_type": None,
                "activity_value": None,
                "activity_unit": None,
                "pchembl_value": None,
                "assay_description": None,
                "confidence_score": None,
                "source_url": url,
                "success": True,
                "error": None,
            }
        )
    return {
        "source": "DrugBank API",
        "query": request_query,
        "success": bool(records),
        "error": None if records else "no_hits",
        "status": "ok" if records else "no_hits",
        "records": records,
        "source_url": url,
    }


def drugbank_import_status(drugbank_path: str | Path | None = None) -> dict:
    path = Path(drugbank_path) if drugbank_path else Path(__file__).resolve().parents[1] / "data" / "drugbank_local.csv"
    return {
        "available": path.exists(),
        "path": str(path),
        "note": "Use a licensed DrugBank CSV export with target and SMILES columns.",
    }
