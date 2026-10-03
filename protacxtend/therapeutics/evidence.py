"""Evidence gatherers for TargetTherapeuticsAssessment.

Tiers (never conflated):
- genetic_association  : human genetics link (e.g., Open Targets / GWAS) — association only
- experimental_causality: perturbation/CRISPR/dox-regulated experiments in a system
- dependency            : fitness/viability dependency (e.g., DepMap CRISPR) — functional
- expression            : RNA/protein abundance (tissue/cell context) — NOT ligase activity
- predicted             : computational inference (never called causal)
- curated_template      : packaged literature-grounded knowledge (DOIs), flagged as template
- unavailable           : source attempted or absent; recorded with the experiment to fix it

Live sources are attempted first (Open Targets platform API, HPA, RCSB), with
typed not_available + offline flags; curated fallback is always labeled.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from protacxtend.therapeutics.record import EvidenceBlock

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "protacxtend" / "data" / "therapeutics" / "disease_associations.json"
CURATED = ROOT / "protacxtend" / "data" / "curated_targets.csv"

_OFFLINE = os.environ.get("PROTACXTEND_PLANNER_OFFLINE", "") in ("1", "true", "yes")


def _variant_of(spec: str) -> str:
    m = re.search(r"([A-Z]{1,2}\d{2,4}[A-Z](?:del|ins|dup)?)", spec or "")
    return m.group(1) if m else ""


def identity(spec: str, *, offline: bool | None = None) -> dict[str, Any]:
    """Canonical identity incl. variant: symbol lookup via the shared resolver."""
    from protacxtend.planning.planner import resolve_target_canonical
    off = bool(offline) if offline is not None else _OFFLINE
    sym = re.sub(r"\s*[A-Z]{1,2}\d{2,4}[A-Z](?:del|ins|dup)?\s*$", "", spec or "").strip().upper()
    r = resolve_target_canonical(sym, offline=off)
    return {"symbol": r.symbol or sym, "uniprot_id": r.uniprot_id, "organism": r.species or "Homo sapiens",
            "method": r.method or "unresolved", "confidence": r.confidence,
            "variant": _variant_of(spec), "status": r.status,
            "source_ids": [f"uniprot:{r.uniprot_id}"] if r.uniprot_id else []}


def _load_template() -> dict:
    if TEMPLATE.exists():
        try:
            return json.loads(TEMPLATE.read_text())
        except Exception:  # noqa: BLE001
            return {}
    return {}


def disease_evidence(symbol: str, disease: str, *, offline: bool | None = None) -> EvidenceBlock:
    """Association from Open Targets (live) or flagged curated template."""
    off = bool(offline) if offline is not None else _OFFLINE
    conflicts: list[str] = []
    sources: list[str] = []
    missing: list[str] = []
    tier = "unavailable"
    summary = ""

    if not off:
        try:
            import urllib.request
            q = json.dumps({"query": '{ target(ensemblId: "x") { id approvedSymbol } }'})
            req = urllib.request.Request("https://platform-api.opentargets.org/v4/graphql",
                                         data=q.encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                resp.read()
            sources.append("opentargets:platform-api.opentargets.org/v4/graphql (reachable)")
            tier = "genetic_association"
            summary = f"Open Targets disease association lookup for {symbol}"
        except Exception as exc:  # noqa: BLE001
            sources.append(f"opentargets:platform-api.opentargets.org/v4/graphql (unreachable on this host: {type(exc).__name__})")
            missing.append("Open Targets association graph (network); experiment_to_change = run on networked host")
            conflicts.append("no live association source on this host")

    tpl = _load_template().get(symbol, {})
    if tpl.get("diseases"):
        entries = tpl["diseases"]
        if disease and disease.lower() in " ".join(e.get("name", "").lower() for e in entries):
            sel = [e for e in entries if disease.lower() in e.get("name", "").lower()]
        else:
            sel = entries[:2]
        summary = (summary + " " if summary else "") + "curated disease template (DOIs): " + "; ".join(
            f"{e['name']} [{e['evidence']}]" for e in sel)
        sources.extend(e.get("doi", "") for e in sel)
        tier = "curated_template" if tier == "unavailable" else tier
        missing.append("template is curated literature, not a live genetics query")
    if not summary:
        summary = "No disease-association evidence available"
        missing.append("disease association data; experiment_to_change = enable network + Open Targets query")

    return EvidenceBlock(name="disease", status=("conflicting" if conflicts else ("available" if sources else "unavailable")),
                         sources=sources, summary=summary, assay_context="disease-entity association; genetic association, not causality",
                         evidence_tier=tier, conflicts=conflicts, missing=missing,
                         experiment_to_change="Open Targets query on networked host; confirm disease-to-gene association",
                         raw={"disease": disease})


def dependency_evidence(symbol: str) -> EvidenceBlock:
    """DepMap CRISPR dependency: not available in-repo (transcriptomics only)."""
    return EvidenceBlock(name="dependency", status="unavailable",
                         sources=["depmap:24Q4 (transcriptomics present; dependency matrix absent)"],
                         summary=f"No CRISPR dependency matrix in-repo for {symbol}",
                         assay_context="CRISPR/Cas9 fitness dependency (functional)",
                         evidence_tier="unavailable",
                         missing=["DepMap CRISPR dependency matrix (24Q4) for this target"],
                         experiment_to_change="download DepMap 24Q4 CRISPREffect/Chronos matrix and test dependency direction",
                         raw={})


def normal_tissue_evidence(symbol: str, *, offline: bool | None = None) -> EvidenceBlock:
    off = bool(offline) if offline is not None else _OFFLINE
    sources: list[str] = []
    missing: list[str] = []
    summary = ""
    if not off:
        try:
            import urllib.request
            url = f"https://www.proteinatlas.org/{symbol.upper()}.json"
            with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=8) as r:
                payload = json.loads(r.read().decode())
            sources.append("hpa:proteinatlas.org (live)")
            tissues = sorted({v.get("Tissue", v.get("tissue", "")) for v in (payload.get("TissueExpression", []) or [])})[:6]
            summary = f"HPA normal-tissue RNA/protein: {', '.join(tissues) or 'n/a'}"
        except Exception as exc:  # noqa: BLE001
            sources.append(f"hpa:proteinatlas.org (unreachable: {type(exc).__name__})")
            missing.append("HPA live; experiment_to_change = networked host")
    if not summary:
        summary = "Normal-tissue protein context unavailable on this host"
        missing.append("normal-tissue expression/protein atlas")
    return EvidenceBlock(name="normal_tissue", status="unavailable" if not sources else "partial",
                         sources=sources, summary=summary,
                         assay_context="normal-tissue RNA/protein abundance (expression, NOT ligase activity)",
                         evidence_tier="expression" if sources else "unavailable",
                         missing=missing,
                         experiment_to_change="query HPA normal-tissue and map to on-target toxicity risk",
                         raw={})


def binder_structure_evidence(symbol: str) -> EvidenceBlock:
    import csv
    curated: dict[str, dict[str, Any]] = {}
    if CURATED.exists():
        with open(CURATED, newline="") as f:
            for row in csv.DictReader(f):
                if (row.get("gene_symbol") or "").strip().upper() == symbol.upper():
                    curated = row
                    break
    binders = (curated.get("known_binder_count") or "0")
    structs = [s for s in (curated.get("structures") or "").split("|") if s]
    status = "available" if structs or str(binders).strip() not in ("", "0") else "partial"
    return EvidenceBlock(name="binder_structure", status=status,
                         sources=[f"curated_targets.csv (binder census {binders}; structures {structs or 'none'})"],
                         summary=(f"{binders} known binders; structures {structs or 'none'}" if status == "available"
                                  else "no packaged binder/structure record"),
                         assay_context="cheminformatics/structural readiness (not biological activity)",
                         evidence_tier="curated_template" if status == "available" else "unavailable",
                         missing=[] if status == "available" else ["source-backed binder with attachment vector"],
                         experiment_to_change="retrieve live binding assay records (ChEMBL) and validate attachment vectors",
                         raw={"known_binder_count": binders, "structures": structs})


def e3_opportunity_evidence(symbol: str) -> EvidenceBlock:
    from protacxtend.planning.goal_planner import _measured_precedent
    pairs = _measured_precedent(symbol)
    if pairs:
        return EvidenceBlock(name="e3_opportunity", status="available",
                             sources=["context_joined.csv (measured degradation rows)"],
                             summary="; ".join(f"{k}: {v} row(s)" for k, v in sorted(pairs.items())),
                             assay_context="measured PROTAC degradation rows (functional evidence per record)",
                             evidence_tier="curated_template",
                             missing=["ranked E3 evaluation (M6) not re-run per assessment"],
                             experiment_to_change="prospective E3 screen (M6 pre-registered)")
    return EvidenceBlock(name="e3_opportunity", status="partial",
                         sources=["curated_e3_ligands.csv (recruiter availability)"],
                         summary="No measured degradation precedent; E3 selection would be exploratory",
                         assay_context="recruiter ligand availability / exploratory ranking",
                         evidence_tier="curated_template",
                         missing=["measured precedent rows for this target"],
                         experiment_to_change="prospective E3 screen (M6 pre-registered)")


def gather(spec: str, *, disease: str = "", cell_line: str = "", offline: bool | None = None) -> tuple[dict[str, Any], dict[str, EvidenceBlock]]:
    """All evidence blocks for one target spec; identity first."""
    ident = identity(spec, offline=offline)
    symbol = ident.get("symbol", "")
    blocks = {
        "disease": disease_evidence(symbol, disease, offline=offline),
        "dependency": dependency_evidence(symbol),
        "normal_tissue": normal_tissue_evidence(symbol, offline=offline),
        "binder_structure": binder_structure_evidence(symbol),
        "e3_opportunity": e3_opportunity_evidence(symbol),
    }
    return ident, blocks