"""TargetTherapeuticsAssessment execution API + design gates.

run_assessment(): gather -> assess -> persist -> typed record (always returns
conclusions with source ids, assay context, conflicts, missing, and the
experiment that would change the decision).

design_gate(): a design run must not bypass identity / chemistry /
therapeutic-window gates:
  - identity/chemistry gates are evaluated from the assessment record;
  - if an assessment exists and its verdict is degradation_unsuitable, design
    is blocked (fail closed, typed TherapeuticallyUnsuitable);
  - require_assessment=True additionally blocks when no assessment exists.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from protacxtend.therapeutics.decision import assess
from protacxtend.therapeutics.evidence import gather
from protacxtend.therapeutics.record import TargetTherapeuticsAssessment

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "assessments"
OUT.mkdir(parents=True, exist_ok=True)


class TherapeuticallyUnsuitable(Exception):
    """Raised when the design gate is blocked (no bypass allowed)."""


def _source_versions() -> dict[str, str]:
    """Per-source version/hash so an assessment is only reused for identical
    sources (stale/mismatched records are rejected, never silently used)."""
    import hashlib
    out: dict[str, str] = {}
    for key, path in {
        "curated_targets": "protacxtend/data/curated_targets.csv",
        "curated_e3": "protacxtend/data/curated_e3_ligands.csv",
        "context_joined": "protacxtend/modules/cell_context_selector/data/context_joined.csv",
        "disease_template": "protacxtend/data/therapeutics/disease_associations.json",
    }.items():
        p = ROOT / path
        if p.exists():
            out[key] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        else:
            out[key] = "missing"
    return out


def _symbol_of(ident: dict[str, Any]) -> str:
    sym = (ident.get("symbol") or "").replace(" ", "_")
    var = ident.get("variant") or ""
    return f"{sym}_{var}" if var else sym


def context_fingerprint(symbol: str, variant: str, disease: str, cell_line: str,
                        versions: dict[str, str], schema: str = "TargetTherapeuticsAssessment.v1") -> str:
    import hashlib
    payload = "|".join([symbol.upper(), variant or "", (disease or "").lower().strip(),
                        (cell_line or "").lower().strip(),
                        json.dumps(versions, sort_keys=True), schema])
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def _index_path() -> Path:
    return OUT / "index.json"


def _write_index(entry: dict) -> None:
    idx = {}
    if _index_path().exists():
        try:
            idx = json.loads(_index_path().read_text())
        except Exception:  # noqa: BLE001
            idx = {}
    idx[entry["context_key"]] = entry
    _index_path().write_text(json.dumps(idx, indent=1))


def run_assessment(spec: str, *, disease: str = "", cell_line: str = "",
                   offline: bool | None = None) -> TargetTherapeuticsAssessment:
    """Assessment is keyed to the EXACT context: target+variant+disease+cell+
    source versions + schema. Different context => different stored record."""
    ident, blocks = gather(spec, disease=disease, cell_line=cell_line, offline=offline)
    record = assess(ident, blocks, disease=disease, cell_line=cell_line)
    record.source_versions = _source_versions()
    symbol = (ident.get("symbol") or "").replace(" ", "_")
    var = ident.get("variant") or ""
    fp = context_fingerprint(symbol, var, disease, cell_line, record.source_versions,
                             record.schema_version)
    record.context_fingerprint = fp
    name = f"{symbol}_{var}".rstrip("_") + f"__{fp}"
    path = OUT / f"{name}.json"
    with open(path, "w") as f:
        json.dump(record.model_dump(), f, indent=1, default=str)
    record.artifact_path = str(path)
    _write_index({"context_key": f"{symbol}|{var}|{disease}|{cell_line}".lower(),
                  "path": str(path), "fingerprint": fp})
    return record


def mismatch_reason(symbol: str, variant: str = "", disease: str = "",
                    cell_line: str = "") -> str:
    """Why an existing assessment (if any) does NOT match the requested
    context / source versions / schema. Empty string == exact match."""
    symbol = symbol.upper().replace(" ", "_")
    versions = _source_versions()
    fp = context_fingerprint(symbol, variant, disease, cell_line, versions,
                             "TargetTherapeuticsAssessment.v1")
    idx = {}
    if _index_path().exists():
        try:
            idx = json.loads(_index_path().read_text())
        except Exception:  # noqa: BLE001
            idx = {}
    key = f"{symbol}|{variant}|{disease}|{cell_line}".lower()
    entry = idx.get(key)
    if entry is None:
        # context key not registered (no exact-context assessment)
        return f"no assessment for exact context (target={symbol}, variant={variant or '-'}, disease={disease or '-'}, cell={cell_line or '-'})"
    if entry.get("fingerprint") != fp:
        return (f"context/source mismatch: stored fingerprint {entry.get('fingerprint')} != current {fp} "
                "(disease, cell, variant, source versions or schema changed); stale record rejected")
    return ""


def load_assessment(symbol: str, *, disease: str = "", cell_line: str = "",
                    require_exact: bool = True) -> Optional[TargetTherapeuticsAssessment]:
    """Load only an exact-context, fresh, same-schema assessment; otherwise
    return None (stale/mismatched records are rejected, never silently used)."""
    var = ""
    m = re.search(r"([A-Z]{1,2}\d{2,4}[A-Z](?:del|ins|dup)?)", symbol or "")
    if m:
        var = m.group(1)
    base = re.sub(r"\s*[A-Z]{1,2}\d{2,4}[A-Z](?:del|ins|dup)?\s*$", "", symbol or "").strip().upper().replace(" ", "_")
    reason = mismatch_reason(base, var, disease, cell_line)
    if reason:
        return None
    idx = {}
    if _index_path().exists():
        try:
            idx = json.loads(_index_path().read_text())
        except Exception:  # noqa: BLE001
            idx = {}
    entry = idx.get(f"{base}|{var}|{disease}|{cell_line}".lower())
    if not entry:
        return None
    path = Path(entry["path"])
    if not path.exists():
        return None
    rec = TargetTherapeuticsAssessment(**json.loads(path.read_text()))
    if rec.schema_version != "TargetTherapeuticsAssessment.v1":
        return None
    return rec


def design_gate(spec: str, *, disease: str = "", cell_line: str = "",
                  require_assessment: bool = False,
                  allow_requires_review: bool = True) -> dict[str, Any]:
    """Check design gates (no bypass of identity/chemistry/blocked window).

    therapeutic_window == requires_review is NOT a pass: it flags missing
    window data. Default behaviour lets research design proceed with the flag
    visible; allow_requires_review=False makes it block too.
    """
    assessment = load_assessment(spec, disease=disease, cell_line=cell_line)
    if assessment is None:
        reason = mismatch_reason(spec.split(" ")[0].upper().replace(" ", "_"),
                                 (re.search(r"([A-Z]{1,2}\d{2,4}[A-Z](?:del|ins|dup)?)", spec) or [None, ""])[1] or "",
                                 disease, cell_line)
        if require_assessment:
            raise TherapeuticallyUnsuitable(
                f"no exact-context TargetTherapeuticsAssessment on file for '{spec}' ({reason}) "
                "and design requires one (run /therapeutics <target> first); design not allowed to bypass the therapeutic gate.")
        return {"gate": "therapeutic_window", "status": "not_run",
                "reason": f"no exact-context assessment; {reason}"}
    gates = dict(assessment.decision.gates)
    if gates.get("identity") == "block" or gates.get("chemistry") == "block" or gates.get("therapeutic_window") == "block":
        raise TherapeuticallyUnsuitable(
            f"design blocked for '{spec}': gates={gates}; mechanism={assessment.decision.verdict}; "
            f"rationale={assessment.decision.mechanism_rationale or assessment.decision.rationale}")
    if gates.get("therapeutic_window") == "requires_review":
        if not allow_requires_review:
            raise TherapeuticallyUnsuitable(
                f"design blocked for '{spec}': therapeutic-window requires_review "
                f"(data missing: {assessment.decision.suitability_reason}); strict mode forbids proceeding.")
        return {"gate": "therapeutic_window", "status": "pass_with_requires_review",
                "verdict": assessment.decision.verdict,
                "therapeutic_suitability": assessment.decision.therapeutic_suitability,
                "suitability_reason": assessment.decision.suitability_reason,
                "gates": gates, "artifact": assessment.artifact_path}
    return {"gate": "therapeutic_window", "status": "pass", "verdict": assessment.decision.verdict,
            "therapeutic_suitability": assessment.decision.therapeutic_suitability,
            "gates": gates, "artifact": assessment.artifact_path}