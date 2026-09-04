"""Executable ADME/Tox predictors with explicit backend labeling."""

from __future__ import annotations

import json
import os
import pickle
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from protacxtend.tools.rdkit_chemistry import calculate_descriptors


DEFAULT_LOCAL_MODEL_PATHS = [
    Path("protacxtend/models/admet_model.pkl"),
    Path("protacxtend/models/admet_model.joblib"),
]


def calculate_protac_admet_descriptors(smiles: str) -> dict[str, Any]:
    result = calculate_descriptors(smiles)
    if not result["success"]:
        return {
            "source": "ADMET descriptor layer",
            "query": {"smiles": smiles},
            "success": False,
            "error": result["error"],
            "descriptors": {},
            "status": "unavailable",
        }
    d = result["descriptors"]
    descriptors = {
        "MW": d["MW"],
        "TPSA": d["TPSA"],
        "LogP": d["LogP"],
        "rotatable_bonds": d["rotatable_bonds"],
        "HBD": d["HBD"],
        "HBA": d["HBA"],
        "QED": d.get("QED"),
        "SA_score": d.get("SA_score"),
    }
    return {
        "source": "ADMET descriptor layer",
        "query": {"smiles": smiles},
        "success": True,
        "error": None,
        "descriptors": descriptors,
        "status": "ok",
    }


def _risk_from_score(score: float) -> str:
    if score >= 0.67:
        return "high"
    if score >= 0.34:
        return "medium"
    return "low"


def run_rule_based_admet_flags(smiles: str) -> dict[str, Any]:
    descriptor_result = calculate_protac_admet_descriptors(smiles)
    if not descriptor_result["success"]:
        return {
            "source": "ADMET rule engine",
            "query": {"smiles": smiles},
            "success": False,
            "error": descriptor_result["error"],
            "status": "unavailable",
            "backend_used": "descriptor_rule_based",
            "real_output_generated": False,
            "limitations": "RDKit descriptor calculation failed.",
        }
    d = descriptor_result["descriptors"]
    mw = float(d["MW"])
    tpsa = float(d["TPSA"])
    logp = float(d["LogP"])
    rot = float(d["rotatable_bonds"])
    solubility = max(-8.5, min(2.0, 0.16 - (0.63 * logp) - (0.0062 * mw) + (0.066 * rot)))
    permeability_proxy = max(0.0, min(1.0, 1.15 - 0.0007 * tpsa - 0.00025 * max(mw - 700.0, 0.0)))
    herg_score = max(0.0, min(1.0, 0.33 + 0.11 * max(logp - 2.8, 0.0) + 0.05 * max(mw - 800.0, 0.0) / 300.0))
    ames_score = max(0.0, min(1.0, 0.20 + 0.10 * max(logp - 3.0, 0.0) + 0.08 * (1.0 - (d.get("QED") or 0.4))))
    dili_score = max(0.0, min(1.0, 0.30 + 0.14 * max(logp - 2.5, 0.0) + 0.05 * max(mw - 750.0, 0.0) / 250.0))
    cyp_score = max(0.0, min(1.0, 0.22 + 0.14 * max(logp - 3.2, 0.0) + 0.02 * (rot / 12.0)))
    pgp_score = max(0.0, min(1.0, 0.34 + 0.0012 * max(tpsa - 130.0, 0.0) + 0.03 * max(mw - 700.0, 0.0) / 200.0))
    return {
        "source": "ADMET rule engine",
        "query": {"smiles": smiles},
        "success": True,
        "error": None,
        "status": "ok",
        "backend_used": "descriptor_rule_based",
        "real_output_generated": True,
        "limitations": (
            "Descriptor/rule output only, not ML endpoint predictions; PROTAC high MW/TPSA is expected "
            "but still penalizes permeability proxy."
        ),
        "solubility": round(solubility, 3),
        "permeability_proxy": round(permeability_proxy, 3),
        "hERG_risk": _risk_from_score(herg_score),
        "AMES_risk": _risk_from_score(ames_score),
        "DILI_risk": _risk_from_score(dili_score),
        "CYP_risk": _risk_from_score(cyp_score),
        "Pgp_risk": _risk_from_score(pgp_score),
        "MW": d["MW"],
        "TPSA": d["TPSA"],
        "LogP": d["LogP"],
        "rotatable_bonds": int(d["rotatable_bonds"]),
    }


def load_local_admet_model(model_path: str | Path) -> dict[str, Any]:
    path = Path(model_path)
    if not path.exists():
        return {"success": False, "error": f"Local ADMET model file does not exist: {path}", "model": None, "status": "unavailable"}
    try:
        if path.suffix == ".joblib":
            import joblib

            model = joblib.load(path)
        else:
            with path.open("rb") as handle:
                model = pickle.load(handle)
    except Exception as exc:
        return {"success": False, "error": f"Local ADMET model load failed: {exc}", "model": None, "status": "unavailable"}
    return {"success": True, "error": None, "model": model, "status": "ok"}


def _find_local_model_path() -> Path | None:
    for path in DEFAULT_LOCAL_MODEL_PATHS:
        if path.exists():
            return path
    env_path = os.getenv("ADMET_LOCAL_MODEL_PATH")
    if env_path and Path(env_path).exists():
        return Path(env_path)
    return None


def predict_with_local_admet_model(smiles: str, model_name: str = "default") -> dict[str, Any]:
    model_path = os.getenv(f"ADMET_LOCAL_MODEL_{model_name.upper()}_PATH") or os.getenv("ADMET_LOCAL_MODEL_PATH")
    path = Path(model_path) if model_path else _find_local_model_path()
    if path is None:
        return {
            "source": "ADMET local model",
            "query": {"smiles": smiles, "model_name": model_name},
            "success": False,
            "error": "Local ADMET model unavailable.",
            "status": "unavailable",
            "backend_used": "local_model",
            "real_output_generated": False,
            "limitations": "No local model file found.",
        }
    loaded = load_local_admet_model(path)
    if not loaded["success"]:
        return {
            "source": "ADMET local model",
            "query": {"smiles": smiles, "model_name": model_name},
            "success": False,
            "error": loaded["error"],
            "status": "unavailable",
            "backend_used": "local_model",
            "real_output_generated": False,
            "limitations": "Model file exists but could not be loaded.",
        }
    descriptor_result = calculate_protac_admet_descriptors(smiles)
    if not descriptor_result["success"]:
        return {
            "source": "ADMET local model",
            "query": {"smiles": smiles, "model_name": model_name},
            "success": False,
            "error": descriptor_result["error"],
            "status": "unavailable",
            "backend_used": "local_model",
            "real_output_generated": False,
            "limitations": "Descriptor generation failed; local model cannot run.",
        }
    d = descriptor_result["descriptors"]
    model = loaded["model"]
    features = [[d["MW"], d["TPSA"], d["LogP"], d["rotatable_bonds"], d["HBD"], d["HBA"]]]
    try:
        if hasattr(model, "predict"):
            pred = model.predict(features)
            row = pred[0]
        else:
            return {
                "source": "ADMET local model",
                "query": {"smiles": smiles, "model_name": model_name},
                "success": False,
                "error": "Model object has no predict() method.",
                "status": "unavailable",
                "backend_used": "local_model",
                "real_output_generated": False,
                "limitations": "Unsupported local model interface.",
            }
    except Exception as exc:
        return {
            "source": "ADMET local model",
            "query": {"smiles": smiles, "model_name": model_name},
            "success": False,
            "error": f"Local ADMET model prediction failed: {exc}",
            "status": "unavailable",
            "backend_used": "local_model",
            "real_output_generated": False,
            "limitations": "Model execution failed.",
        }

    if isinstance(row, dict):
        output = dict(row)
    elif isinstance(row, (list, tuple)):
        keys = ["solubility", "permeability_proxy", "hERG_risk", "AMES_risk", "DILI_risk", "CYP_risk", "Pgp_risk"]
        output = {key: row[idx] if idx < len(row) else None for idx, key in enumerate(keys)}
    else:
        output = {"model_output": row}
    output.update(
        {
            "source": "ADMET local model",
            "query": {"smiles": smiles, "model_name": model_name},
            "success": True,
            "error": None,
            "status": "ok",
            "backend_used": "local_model",
            "real_output_generated": True,
            "limitations": f"Local model inference from {path.name}.",
            "MW": d["MW"],
            "TPSA": d["TPSA"],
            "LogP": d["LogP"],
            "rotatable_bonds": int(d["rotatable_bonds"]),
        }
    )
    return output


def _predict_with_external_api(smiles: str) -> dict[str, Any]:
    url = os.getenv("ADMET_API_URL")
    key = os.getenv("ADMET_API_KEY")
    if not url or not key:
        return {
            "source": "ADMET external API",
            "query": {"smiles": smiles},
            "success": False,
            "error": "ADMET_API_URL or ADMET_API_KEY is not configured.",
            "status": "unavailable",
            "backend_used": "external_api",
            "real_output_generated": False,
            "limitations": "External ADME/Tox API credentials/config missing.",
        }
    payload = json.dumps({"smiles": smiles}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}", "User-Agent": "PROTACXtend/0.1"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=12.0) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "source": "ADMET external API",
            "query": {"smiles": smiles},
            "success": False,
            "error": f"External ADMET API call failed: {exc}",
            "status": "unavailable",
            "backend_used": "external_api",
            "real_output_generated": False,
            "limitations": "API call failed.",
        }
    data.update(
        {
            "source": "ADMET external API",
            "query": {"smiles": smiles},
            "success": True,
            "error": None,
            "status": "ok",
            "backend_used": "external_api",
            "real_output_generated": True,
            "limitations": "External API prediction.",
        }
    )
    return data


def _heuristic_stub(smiles: str) -> dict[str, Any]:
    descriptor_result = calculate_protac_admet_descriptors(smiles)
    d = descriptor_result.get("descriptors", {})
    return {
        "source": "ADMET heuristic stub",
        "query": {"smiles": smiles},
        "success": True,
        "error": None,
        "status": "heuristic_stub",
        "backend_used": "heuristic_stub",
        "real_output_generated": False,
        "limitations": "Heuristic fallback only; not ML or API output.",
        "solubility": None,
        "permeability_proxy": None,
        "hERG_risk": "unknown",
        "AMES_risk": "unknown",
        "DILI_risk": "unknown",
        "CYP_risk": "unknown",
        "Pgp_risk": "unknown",
        "MW": d.get("MW"),
        "TPSA": d.get("TPSA"),
        "LogP": d.get("LogP"),
        "rotatable_bonds": d.get("rotatable_bonds"),
    }


def predict_admet(smiles: str, backend: str = "auto") -> dict[str, Any]:
    selected = (backend or "auto").strip().lower()
    if selected == "descriptor_rule_based":
        return run_rule_based_admet_flags(smiles)
    if selected == "local_model":
        return predict_with_local_admet_model(smiles, model_name="default")
    if selected == "external_api":
        return _predict_with_external_api(smiles)
    if selected == "heuristic_stub":
        return _heuristic_stub(smiles)

    if selected != "auto":
        return {
            "source": "ADMET orchestrator",
            "query": {"smiles": smiles, "backend": backend},
            "success": False,
            "error": f"Unsupported backend: {backend}",
            "status": "unavailable",
            "backend_used": "unknown",
            "real_output_generated": False,
            "limitations": "Unsupported backend.",
        }

    local = predict_with_local_admet_model(smiles, model_name="default")
    if local["success"]:
        return local
    api = _predict_with_external_api(smiles)
    if api["success"]:
        return api
    rule = run_rule_based_admet_flags(smiles)
    if rule["success"]:
        return rule
    return _heuristic_stub(smiles)
