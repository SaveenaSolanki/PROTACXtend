"""DC50/Dmax model loading and inference infrastructure.

This module provides executable model discovery/loading/featurization logic.
If trained models are missing or incompatible, prediction output is explicitly
labeled and can fall back to heuristic_stub only when requested/auto mode.
"""

from __future__ import annotations

import json
import os
import pickle
from pathlib import Path
from typing import Any

from protacxtend.tools.rdkit_chemistry import calculate_descriptors


STATUS_MODEL_LOADED = "model_loaded"
STATUS_MODEL_MISSING = "model_missing"
STATUS_HEURISTIC_STUB = "heuristic_stub"
STATUS_INCOMPATIBLE_MODEL = "incompatible_model"
STATUS_FEATURIZATION_FAILED = "featurization_failed"


DEFAULT_METADATA = {
    "model_name": None,
    "version": None,
    "training_data": None,
    "endpoint": None,
    "feature_schema": None,
    "date": None,
}


def discover_degradation_models(model_dir: str = "models/") -> dict[str, Any]:
    root = Path(model_dir)
    if not root.is_absolute():
        root = Path.cwd() / root
    if not root.exists():
        return {
            "model_dir": str(root),
            "dc50_candidates": [],
            "dmax_candidates": [],
            "status": STATUS_MODEL_MISSING,
            "error": f"Model directory does not exist: {root}",
        }
    files = [path for path in root.rglob("*") if path.is_file()]
    supported = {".pkl", ".joblib", ".pt", ".pth", ".json", ".cbm"}
    files = [path for path in files if path.suffix.lower() in supported]
    dc50 = [str(path) for path in files if "dc50" in path.name.lower()]
    dmax = [str(path) for path in files if "dmax" in path.name.lower()]
    return {
        "model_dir": str(root),
        "dc50_candidates": sorted(dc50),
        "dmax_candidates": sorted(dmax),
        "status": STATUS_MODEL_LOADED if (dc50 or dmax) else STATUS_MODEL_MISSING,
        "error": None if (dc50 or dmax) else "No DC50/Dmax model files found.",
    }


def _extract_model_and_metadata(payload: Any, default_endpoint: str) -> tuple[Any, dict[str, Any]]:
    metadata = dict(DEFAULT_METADATA)
    metadata["endpoint"] = default_endpoint
    model = payload
    if isinstance(payload, dict):
        if "model" in payload:
            model = payload["model"]
        file_meta = payload.get("metadata", {})
        if isinstance(file_meta, dict):
            metadata.update({key: file_meta.get(key) for key in DEFAULT_METADATA if key in file_meta})
            metadata["endpoint"] = file_meta.get("endpoint", default_endpoint)
        for key in DEFAULT_METADATA:
            if key in payload and key != "endpoint":
                metadata[key] = payload[key]
        metadata["endpoint"] = payload.get("endpoint", metadata.get("endpoint", default_endpoint))
    metadata.setdefault("endpoint", default_endpoint)
    return model, metadata


def _load_model_file(model_path: str | Path, endpoint: str) -> dict[str, Any]:
    path = Path(model_path)
    if not path.exists():
        return {"status": STATUS_MODEL_MISSING, "success": False, "error": f"Model file not found: {path}", "model": None, "metadata": dict(DEFAULT_METADATA)}
    suffix = path.suffix.lower()
    try:
        if suffix == ".joblib":
            import joblib

            payload = joblib.load(path)
        elif suffix == ".pkl":
            with path.open("rb") as handle:
                payload = pickle.load(handle)
        elif suffix in {".pt", ".pth"}:
            try:
                import torch
            except Exception as exc:
                return {
                    "status": STATUS_INCOMPATIBLE_MODEL,
                    "success": False,
                    "error": f"PyTorch model provided but torch is unavailable: {exc}",
                    "model": None,
                    "metadata": dict(DEFAULT_METADATA),
                }
            payload = torch.load(path, map_location="cpu")
        elif suffix == ".json":
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        elif suffix == ".cbm":
            try:
                from catboost import CatBoostRegressor
            except Exception as exc:
                return {
                    "status": STATUS_INCOMPATIBLE_MODEL,
                    "success": False,
                    "error": f"CatBoost model provided but catboost is unavailable: {exc}",
                    "model": None,
                    "metadata": dict(DEFAULT_METADATA),
                }
            model = CatBoostRegressor()
            model.load_model(str(path))
            payload = {"model": model, "metadata": {"endpoint": endpoint, "model_name": path.name}}
        else:
            return {
                "status": STATUS_INCOMPATIBLE_MODEL,
                "success": False,
                "error": f"Unsupported model extension: {suffix}",
                "model": None,
                "metadata": dict(DEFAULT_METADATA),
            }
    except Exception as exc:
        return {
            "status": STATUS_INCOMPATIBLE_MODEL,
            "success": False,
            "error": f"Failed to load model: {exc}",
            "model": None,
            "metadata": dict(DEFAULT_METADATA),
        }
    model, metadata = _extract_model_and_metadata(payload, endpoint)
    if metadata.get("model_name") is None:
        metadata["model_name"] = path.name
    metadata["source_path"] = str(path)
    return {"status": STATUS_MODEL_LOADED, "success": True, "error": None, "model": model, "metadata": metadata}


def load_dc50_model(model_path: str | Path) -> dict[str, Any]:
    return _load_model_file(model_path, endpoint="dc50_nM")


def load_dmax_model(model_path: str | Path) -> dict[str, Any]:
    return _load_model_file(model_path, endpoint="dmax_percent")


def featurize_protac_for_degradation(candidate: Any) -> dict[str, Any]:
    smiles = getattr(candidate, "full_protac_smiles", None) or candidate.get("full_protac_smiles")
    if not smiles:
        return {"status": STATUS_FEATURIZATION_FAILED, "success": False, "error": "Candidate has no full_protac_smiles.", "feature_vector": None, "feature_map": None}
    descriptor_result = calculate_descriptors(smiles)
    if not descriptor_result["success"]:
        return {"status": STATUS_FEATURIZATION_FAILED, "success": False, "error": descriptor_result["error"], "feature_vector": None, "feature_map": None}
    d = descriptor_result["descriptors"]
    feature_map = {
        "MW": float(d["MW"]),
        "TPSA": float(d["TPSA"]),
        "LogP": float(d["LogP"]),
        "HBD": int(d["HBD"]),
        "HBA": int(d["HBA"]),
        "rotatable_bonds": int(d["rotatable_bonds"]),
        "ring_count": int(d["ring_count"]),
        "aromatic_ring_count": int(d["aromatic_ring_count"]),
        "heavy_atom_count": int(d["heavy_atom_count"]),
        "fraction_Csp3": float(d["fraction_Csp3"]),
    }
    feature_vector = [feature_map[key] for key in feature_map]
    return {"status": STATUS_MODEL_LOADED, "success": True, "error": None, "feature_map": feature_map, "feature_vector": feature_vector, "feature_schema": list(feature_map.keys())}


def _validate_schema(metadata: dict[str, Any], feature_map: dict[str, Any]) -> tuple[bool, str | None, list[Any]]:
    schema = metadata.get("feature_schema")
    if not schema:
        return True, None, list(feature_map.values())
    if not isinstance(schema, list) or not all(isinstance(item, str) for item in schema):
        return False, "Model feature_schema is invalid; expected list[str].", []
    missing = [name for name in schema if name not in feature_map]
    if missing:
        return False, f"Feature schema mismatch. Missing features: {missing}", []
    return True, None, [feature_map[name] for name in schema]


def _heuristic_stub_prediction(candidate: Any) -> dict[str, Any]:
    feat = featurize_protac_for_degradation(candidate)
    if not feat["success"]:
        return {
            "status": STATUS_FEATURIZATION_FAILED,
            "backend_used": "heuristic_stub",
            "real_output_generated": False,
            "error": feat["error"],
            "predicted_dc50_nM": None,
            "predicted_dmax_percent": None,
            "model_metadata": None,
            "limitations": "Featurization failed before heuristic fallback.",
        }
    f = feat["feature_map"]
    mw = f["MW"]
    tpsa = f["TPSA"]
    rot = f["rotatable_bonds"]
    dc50 = max(5.0, min(20000.0, 10 ** (2.15 + 0.0014 * max(mw - 700.0, 0.0) + 0.0022 * max(tpsa - 140.0, 0.0) + 0.01 * max(rot - 12.0, 0.0))))
    dmax = max(5.0, min(95.0, 86.0 - 0.012 * max(mw - 750.0, 0.0) - 0.03 * max(tpsa - 150.0, 0.0) - 0.55 * max(rot - 14.0, 0.0)))
    return {
        "status": STATUS_HEURISTIC_STUB,
        "backend_used": "heuristic_stub",
        "real_output_generated": False,
        "error": None,
        "predicted_dc50_nM": round(float(dc50), 3),
        "predicted_dmax_percent": round(float(dmax), 3),
        "model_metadata": {
            "model_name": "SynGlue-demo-heuristic-v0.1",
            "version": "v0.1",
            "training_data": None,
            "endpoint": "dc50_dmax_joint_heuristic",
            "feature_schema": feat["feature_schema"],
            "date": None,
        },
        "limitations": "Heuristic formula output; not trained-model prediction.",
    }


def _predict_one(model: Any, ordered_features: list[Any]) -> tuple[bool, Any, str | None]:
    try:
        if hasattr(model, "predict"):
            output = model.predict([ordered_features])
            if isinstance(output, (list, tuple)):
                return True, output[0], None
            try:
                return True, output[0], None
            except Exception:
                return True, output, None
        if callable(model):
            return True, model(ordered_features), None
        return False, None, "Model has no predict method and is not callable."
    except Exception as exc:
        return False, None, f"Model prediction failed: {exc}"


def predict_dc50_dmax(candidate: Any, backend: str = "auto") -> dict[str, Any]:
    selected = (backend or "auto").strip().lower()
    if selected == "heuristic_stub":
        return _heuristic_stub_prediction(candidate)

    feat = featurize_protac_for_degradation(candidate)
    if not feat["success"]:
        return {
            "status": STATUS_FEATURIZATION_FAILED,
            "backend_used": selected if selected != "auto" else "model_auto",
            "real_output_generated": False,
            "error": feat["error"],
            "predicted_dc50_nM": None,
            "predicted_dmax_percent": None,
            "model_metadata": None,
            "limitations": "Failed to featurize candidate.",
        }

    discover = discover_degradation_models()
    if selected != "auto":
        if selected == "model" and discover["status"] == STATUS_MODEL_MISSING:
            return {
                "status": STATUS_MODEL_MISSING,
                "backend_used": "model",
                "real_output_generated": False,
                "error": discover["error"],
                "predicted_dc50_nM": None,
                "predicted_dmax_percent": None,
                "model_metadata": None,
                "limitations": "Requested model backend but model files are missing.",
            }
        return {
            "status": STATUS_INCOMPATIBLE_MODEL,
            "backend_used": selected,
            "real_output_generated": False,
            "error": f"Unsupported backend selection: {backend}",
            "predicted_dc50_nM": None,
            "predicted_dmax_percent": None,
            "model_metadata": None,
            "limitations": "Supported backends are auto, model, heuristic_stub.",
        }

    if discover["status"] == STATUS_MODEL_MISSING:
        return _heuristic_stub_prediction(candidate)

    dc50_model = load_dc50_model(discover["dc50_candidates"][0]) if discover["dc50_candidates"] else {"success": False, "status": STATUS_MODEL_MISSING, "error": "DC50 model missing"}
    dmax_model = load_dmax_model(discover["dmax_candidates"][0]) if discover["dmax_candidates"] else {"success": False, "status": STATUS_MODEL_MISSING, "error": "Dmax model missing"}
    if not dc50_model.get("success") or not dmax_model.get("success"):
        return {
            "status": STATUS_MODEL_MISSING,
            "backend_used": "model_auto",
            "real_output_generated": False,
            "error": "; ".join(filter(None, [dc50_model.get("error"), dmax_model.get("error")])),
            "predicted_dc50_nM": None,
            "predicted_dmax_percent": None,
            "model_metadata": {"dc50": dc50_model.get("metadata"), "dmax": dmax_model.get("metadata")},
            "limitations": "At least one endpoint model is missing or failed to load.",
        }

    ok_dc50, error_dc50, ordered_dc50 = _validate_schema(dc50_model["metadata"], feat["feature_map"])
    ok_dmax, error_dmax, ordered_dmax = _validate_schema(dmax_model["metadata"], feat["feature_map"])
    if not ok_dc50 or not ok_dmax:
        return {
            "status": STATUS_INCOMPATIBLE_MODEL,
            "backend_used": "model_auto",
            "real_output_generated": False,
            "error": error_dc50 or error_dmax,
            "predicted_dc50_nM": None,
            "predicted_dmax_percent": None,
            "model_metadata": {"dc50": dc50_model["metadata"], "dmax": dmax_model["metadata"]},
            "limitations": "Feature schema validation failed.",
        }

    dc50_ok, dc50_pred, dc50_err = _predict_one(dc50_model["model"], ordered_dc50)
    dmax_ok, dmax_pred, dmax_err = _predict_one(dmax_model["model"], ordered_dmax)
    if not dc50_ok or not dmax_ok:
        return {
            "status": STATUS_INCOMPATIBLE_MODEL,
            "backend_used": "model_auto",
            "real_output_generated": False,
            "error": "; ".join(filter(None, [dc50_err, dmax_err])),
            "predicted_dc50_nM": None,
            "predicted_dmax_percent": None,
            "model_metadata": {"dc50": dc50_model["metadata"], "dmax": dmax_model["metadata"]},
            "limitations": "Model object could not produce predictions.",
        }

    return {
        "status": STATUS_MODEL_LOADED,
        "backend_used": "model_auto",
        "real_output_generated": True,
        "error": None,
        "predicted_dc50_nM": float(dc50_pred),
        "predicted_dmax_percent": float(dmax_pred),
        "model_metadata": {"dc50": dc50_model["metadata"], "dmax": dmax_model["metadata"]},
        "limitations": "Model prediction successful.",
    }


def predict_with_uncertainty(candidate: Any) -> dict[str, Any]:
    result = predict_dc50_dmax(candidate, backend="auto")
    if result["status"] != STATUS_MODEL_LOADED:
        result["uncertainty"] = {"available": False, "reason": "model_not_loaded"}
        return result

    discover = discover_degradation_models()
    dc50_model = load_dc50_model(discover["dc50_candidates"][0]) if discover["dc50_candidates"] else {"success": False}
    dmax_model = load_dmax_model(discover["dmax_candidates"][0]) if discover["dmax_candidates"] else {"success": False}
    feat = featurize_protac_for_degradation(candidate)
    if not feat["success"] or not dc50_model.get("success") or not dmax_model.get("success"):
        result["uncertainty"] = {"available": False, "reason": "preconditions_failed"}
        return result

    _, _, dc50_features = _validate_schema(dc50_model["metadata"], feat["feature_map"])
    _, _, dmax_features = _validate_schema(dmax_model["metadata"], feat["feature_map"])
    uncertainty: dict[str, Any] = {"available": False, "reason": "model_does_not_support_uncertainty"}
    if hasattr(dc50_model["model"], "predict_std") and hasattr(dmax_model["model"], "predict_std"):
        try:
            dc50_std = dc50_model["model"].predict_std([dc50_features])[0]
            dmax_std = dmax_model["model"].predict_std([dmax_features])[0]
            uncertainty = {"available": True, "dc50_std": float(dc50_std), "dmax_std": float(dmax_std)}
        except Exception as exc:
            uncertainty = {"available": False, "reason": f"predict_std_failed: {exc}"}
    result["uncertainty"] = uncertainty
    return result

