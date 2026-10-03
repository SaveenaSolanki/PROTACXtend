"""challenge_scorecard.py — map a PROTACXtend candidate onto the 10 development
challenge dimensions and emit typed, JSON-serializable evidence rows.

This tool is the canonical implementation of the 10-dimension scorecard
(see challenge/outputs/PROTAC_CHALLENGES_AGENT_TOOLKIT.md). It consumes either:

  * a full workflow-state dict (protacxtend/outputs/candidates/<stem>.json:
    assembled_candidates, admet_predictions, ternary_feasibility_results,
    e3_context_predictions, degradation_predictions, novelty_results,
    applicability_domain_results), or
  * a single candidate row dict (e.g., one row of a candidates CSV parsed
    manually by the CLI).

Evidence levels (never invent numbers; each dimension carries its provenance):

  ml_model         -> trained-ML prediction (TACK-style/chemprop/ADMET-AI)
  rule_descriptor  -> RDKit descriptors / curated rules / curated evidence
  geometry_stub    -> deterministic geometry proxy (no real docking yet)
  docking          -> real docking/ternary engine output
  no_evidence      -> gap; must be marked (never filled in)

Dimensions flagged `requires_experiment` keep that flag in the row even when
in-silico evidence exists.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

TOOL_VERSION = "challenge_scorecard-v1.0"
DIMENSIONS = [
    ("cell_permeability", "Cell permeability"),
    ("metabolic_stability", "Metabolic stability"),
    ("solubility", "Solubility"),
    ("selectivity", "Selectivity (target / E3 / neosubstrate)"),
    ("ternary_complex", "Ternary complex formation"),
    ("e3_choice", "E3 ligase choice"),
    ("synthesis_feasibility", "Synthesis feasibility"),
    ("in_vivo_efficacy", "In vivo efficacy (PK/PD translation)"),
    ("safety", "Safety / tox"),
    ("developability", "Developability (bRo5, formulation, delivery)"),
]


@dataclass
class DimensionEvidence:
    dimension: str
    label: str
    evidence_level: str          # ml_model | rule_descriptor | geometry_stub | docking | no_evidence
    summary: str
    value: Optional[Any] = None
    flags: List[str] = field(default_factory=list)
    sources: str = ""            # exact key paths in the workflow JSON
    requires_experiment: bool = False
    tool_version: str = TOOL_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# extraction helpers
# ---------------------------------------------------------------------------

def _pick(rows: List[Any], candidate_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not rows:
        return None
    if candidate_id:
        for r in rows:
            if isinstance(r, dict) and r.get("candidate_id") == candidate_id:
                return r
    return rows[0] if isinstance(rows[0], dict) else None


def _num(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# per-dimension builders
# ---------------------------------------------------------------------------

def _cell_permeability(ac: Optional[Dict], am: Optional[Dict]) -> DimensionEvidence:
    parts: List[str] = []
    value: Optional[Any] = None
    ai = (am or {}).get("admet_ai") or {}
    flags = (am or {}).get("admet_ai_flags") or {}
    level = "no_evidence"
    if ac:
        tpsa = _num(ac.get("tpsa"))
        rotors = _num(ac.get("rotatable_bonds"))
        if tpsa is not None:
            value = tpsa
            parts.append(f"TPSA={tpsa:.0f} Å² ({'<220 bRo5-permissive proxy' if tpsa < 220 else '≥220 red flag'})")
        if rotors is not None:
            parts.append(f"rotors={rotors:.0f}")
        level = "rule_descriptor"
    if flags.get("Caco2_log_cm_s") is not None:
        parts.append(f"Caco-2={flags['Caco2_log_cm_s']:.2f} log cm/s ({flags.get('Caco2_flag')})")
        level = "ml_model"
    if flags.get("PAMPA_prob") is not None:
        parts.append(f"PAMPA={flags['PAMPA_prob']:.2f} ({flags.get('PAMPA_flag')})")
        level = "ml_model"
    if flags.get("HIA_prob") is not None:
        parts.append(f"HIA={flags['HIA_prob']:.2f} ({flags.get('HIA_flag')})")
        level = "ml_model"
    if flags.get("efflux_risk") is not None:
        parts.append(f"P-gp efflux={flags['efflux_risk']} (prob {flags.get('Pgp_substrate_prob', 0):.2f})")
        level = "ml_model"
    if am and am.get("Pgp_risk") is not None and "P-gp" not in " ".join(parts):
        parts.append(f"P-gp (rule)={am['Pgp_risk']}")
    if not parts:
        parts.append("no evidence")
        level = "no_evidence"
    return DimensionEvidence(
        dimension="cell_permeability", label="Cell permeability",
        evidence_level=level, summary="; ".join(parts), value=value,
        sources="assembled_candidates.tpsa/rotatable_bonds, admet_ai_flags.*",
    )


def _metabolic_stability(am: Optional[Dict]) -> DimensionEvidence:
    parts: List[str] = []
    ai = (am or {}).get("admet_ai") or {}
    flags = (am or {}).get("admet_ai_flags") or {}
    level = "no_evidence"
    if am and am.get("CYP_risk") is not None:
        parts.append(f"CYP (rule)={am['CYP_risk']}")
        level = "rule_descriptor"
    if flags.get("Clearance_Hepatocyte_drugbank_pct") is not None:
        parts.append(f"hepatocyte clearance pct={flags['Clearance_Hepatocyte_drugbank_pct']:.0f} ({flags.get('hepatocyte_clearance_flag')})")
        level = "ml_model"
    if flags.get("Clearance_Microsome_drugbank_pct") is not None:
        parts.append(f"microsome clearance pct={flags['Clearance_Microsome_drugbank_pct']:.0f} ({flags.get('microsome_clearance_flag')})")
        level = "ml_model"
    if flags.get("Half_Life_Obach_h") is not None:
        parts.append(f"half-life(Obach)={flags['Half_Life_Obach_h']:.1f} h ({flags.get('half_life_flag')})")
        level = "ml_model"
    if level == "no_evidence":
        parts.append("no explicit microsomal/plasma stability endpoint in this run")
    return DimensionEvidence(
        dimension="metabolic_stability", label="Metabolic stability",
        evidence_level=level, summary="; ".join(parts),
        value=flags.get("Half_Life_Obach_h"),
        sources="admet_predictions.CYP_risk, admet_ai_flags.Clearance_*/Half_Life_Obach_h",
    )


def _solubility(am: Optional[Dict]) -> DimensionEvidence:
    parts: List[str] = []
    flags = (am or {}).get("admet_ai_flags") or {}
    level = "no_evidence"
    value: Optional[Any] = None
    if am and am.get("solubility_risk") is not None:
        parts.append(f"solubility risk (rule)={am['solubility_risk']}")
        value = am["solubility_risk"]
        level = "rule_descriptor"
    if flags.get("Solubility_AqSolDB_logS") is not None:
        parts.append(f"AqSolDB logS={flags['Solubility_AqSolDB_logS']:.2f} ({flags.get('solubility_flag')})")
        value = flags["Solubility_AqSolDB_logS"]
        level = "ml_model"
    if not parts:
        parts.append("no evidence")
    return DimensionEvidence(
        dimension="solubility", label="Solubility",
        evidence_level=level, summary="; ".join(parts), value=value,
        sources="admet_predictions.solubility_risk, admet_ai_flags.Solubility_AqSolDB_logS",
    )


def _selectivity(ac: Optional[Dict], ec: Optional[Dict], nv: Optional[Dict],
                 neosub: Optional[Dict]) -> DimensionEvidence:
    parts: List[str] = []
    level = "no_evidence"
    value: Optional[Any] = None
    if ec and ec.get("resistance_risk") is not None:
        parts.append(f"E3 context resistance-safety={ec['resistance_risk']}")
        value = ec["resistance_risk"]
        level = "rule_descriptor"
    if neosub:
        hits = neosub.get("neosubstrate_targets") or []
        if neosub.get("neosubstrate_risk_score") is not None:
            parts.append(f"neosubstrate risk={neosub['neosubstrate_risk_score']} ({', '.join(hits) if hits else 'none curated'})")
            level = "rule_descriptor"
    if ac and ac.get("warhead_name"):
        parts.append(f"warhead={ac['warhead_name']}")
    if nv and nv.get("top_similarity") is not None:
        parts.append(f"novelty top-1 Tanimoto={nv['top_similarity']:.3f} (proxy only)")
        value = nv["top_similarity"]
    if not parts:
        parts.append("no evidence (proteome_selectivity module not run)")
    return DimensionEvidence(
        dimension="selectivity", label="Selectivity (target / E3 / neosubstrate)",
        evidence_level=level, summary="; ".join(parts), value=value,
        sources="e3_context_predictions.resistance_risk, neosubstrate_risk, novelty_results",
        flags=["requires_experiment: proteome-wide degradation phenotype cannot be predicted"],
        requires_experiment=True,
    )


def _ternary_complex(tc: Optional[Dict]) -> DimensionEvidence:
    parts: List[str] = []
    level = "no_evidence"
    value: Optional[Any] = None
    if tc:
        for k in ("ternary_plausibility_score", "fast_geometry_feasibility_score",
                  "linker_reachability_score", "linker_strain_score"):
            v = tc.get(k)
            if v is not None:
                parts.append(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}")
                if value is None:
                    value = v
        parts.append(f"backend={tc.get('structural_backend', '?')}")
        level = "geometry_stub"
        ds = tc.get("docking_status") or ""
        if "p4ward" in str(ds).lower() or "docked" in str(ds).lower():
            level = "docking"
        if tc.get("proceed_to_expensive_modeling"):
            parts.append("gated: proceed_to_expensive_modeling=True")
    if level == "no_evidence":
        parts.append("no evidence")
    return DimensionEvidence(
        dimension="ternary_complex", label="Ternary complex formation",
        evidence_level=level, summary="; ".join(parts), value=value,
        sources="ternary_feasibility_results.*",
        flags=["requires_experiment: cooperative binding rate constants and crystal structure"],
        requires_experiment=True,
    )


def _e3_choice(ec: Optional[Dict]) -> DimensionEvidence:
    parts: List[str] = []
    level = "no_evidence"
    value: Optional[Any] = None
    if ec:
        value = ec.get("total_context_score")
        if value is not None:
            parts.append(f"total_context_score={value:.3f} (E3={ec.get('e3_ligase')}, conf={ec.get('confidence')})")
            parts.append(
                f"components: expression={ec.get('expression_score')}, "
                f"colocalization={ec.get('colocalization_score')}, "
                f"ligand_avail={ec.get('ligand_availability_score')}, "
                f"structural={ec.get('structural_support_score')}, "
                f"resistance={ec.get('resistance_risk')}"
            )
        level = "rule_descriptor"
    if not parts:
        parts.append("no evidence (e3 context engine not run)")
    return DimensionEvidence(
        dimension="e3_choice", label="E3 ligase choice",
        evidence_level=level, summary="; ".join(parts), value=value,
        sources="e3_context_predictions.*",
    )


def _synthesis_feasibility(ac: Optional[Dict]) -> DimensionEvidence:
    parts: List[str] = []
    level = "no_evidence"
    value: Optional[Any] = None
    if ac and ac.get("synthetic_feasibility_score") is not None:
        parts.append(f"assembly score={ac['synthetic_feasibility_score']} (component-join heuristic, NOT a route)")
        value = ac["synthetic_feasibility_score"]
        level = "rule_descriptor"
    if ac and ac.get("reaction_class"):
        parts.append(f"reaction class={ac['reaction_class']}")
    parts.append("GAP: retrosynthesis engines (ASKCOS/AiZynth/OpenNMT) must run on shortlist")
    return DimensionEvidence(
        dimension="synthesis_feasibility", label="Synthesis feasibility",
        evidence_level=level, summary="; ".join(parts), value=value,
        sources="assembled_candidates.synthetic_feasibility_score, tools/retrosynthesis_engines.py",
    )


def _in_vivo_efficacy(dg: Optional[Dict]) -> DimensionEvidence:
    parts: List[str] = []
    level = "no_evidence"
    value: Optional[Any] = None
    if dg:
        dc = dg.get("predicted_dc50_nM")
        dm = dg.get("predicted_dmax_percent")
        if dc is not None:
            parts.append(f"DC50={dc} nM (model={dg.get('result_source', '?')}, conf={dg.get('model_confidence')})")
            value = dc
            level = "ml_model"
        if dm is not None:
            parts.append(f"Dmax={dm}%")
            level = "ml_model"
        if dg.get("chemprop_dc50_nM") is not None:
            parts.append(f"chemprop cross-check DC50={dg['chemprop_dc50_nM']} nM")
    parts.append("GAP: dose-response/hook simulation + PK/PD proxies exist but PK-PD translation REQUIRES EXPERIMENT")
    return DimensionEvidence(
        dimension="in_vivo_efficacy", label="In vivo efficacy (PK/PD translation)",
        evidence_level=level, summary="; ".join(parts), value=value,
        sources="degradation_predictions.*, tools/dose_response_simulator.py, tools/kinetics.py",
        flags=["requires_experiment: in vivo efficacy cannot be predicted"],
        requires_experiment=True,
    )


def _safety(am: Optional[Dict]) -> DimensionEvidence:
    parts: List[str] = []
    ai = (am or {}).get("admet_ai") or {}
    level = "no_evidence"
    value: Optional[Any] = None
    if am:
        for k in ("hERG_risk", "AMES_risk", "DILI_risk", "CYP_risk"):
            if am.get(k) is not None:
                parts.append(f"{k}={am[k]} (rule)")
                level = "rule_descriptor"
        value = am.get("overall_admet_penalty")
        for k in ("hERG", "AMES", "DILI", "LD50_Zhu", "ClinTox"):
            if k in ai and ai[k] is not None:
                parts.append(f"{k} (ML)={ai[k]:.3f}" if isinstance(ai[k], float) else f"{k} (ML)={ai[k]}")
                level = "ml_model"
    if not parts:
        parts.append("no evidence")
    return DimensionEvidence(
        dimension="safety", label="Safety / tox",
        evidence_level=level, summary="; ".join(parts), value=value,
        sources="admet_predictions.hERG/AMES/DILI/CYP/Pgp, admet_ai.hERG/AMES/DILI/LD50_Zhu/ClinTox",
        flags=["requires_experiment: tox panel, teratogenicity (cereblon ligands), immunogenicity"],
        requires_experiment=True,
    )


def _developability(ac: Optional[Dict], am: Optional[Dict], ad: Optional[Dict]) -> DimensionEvidence:
    parts: List[str] = []
    level = "no_evidence"
    value: Optional[Any] = None
    if ac:
        mw = ac.get("mw"); logp = ac.get("logp"); tpsa = ac.get("tpsa")
        hbd = ac.get("hbd"); hba = ac.get("hba"); rot = ac.get("rotatable_bonds")
        parts.append(f"bRo5: MW={mw}, logP={logp}, TPSA={tpsa}, HBD={hbd}, HBA={hba}, rotors={rot}")
        level = "rule_descriptor"
    if am:
        if am.get("qed") is not None:
            parts.append(f"QED={am['qed']:.3f}")
        if am.get("sa_score_proxy") is not None:
            parts.append(f"SA-proxy={am['sa_score_proxy']}")
        if am.get("overall_admet_penalty") is not None:
            parts.append(f"ADMET penalty={am['overall_admet_penalty']}")
            value = am["overall_admet_penalty"]
    if ad and ad.get("applicability_domain_score") is not None:
        parts.append(f"applicability-domain={ad['applicability_domain_score']}")
    parts.append("GAP: PROTAC bRo5 filter + Pareto front over objectives")
    return DimensionEvidence(
        dimension="developability", label="Developability (bRo5, formulation, delivery)",
        evidence_level=level, summary="; ".join(parts), value=value,
        sources="assembled_candidates.*, admet_predictions.qed/sa_score_proxy/penalty, applicability_domain_results, tools/pareto_ranking.py",
        flags=["requires_experiment: crystallizability, formulation, long-term stability"],
        requires_experiment=True,
    )


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# optional live ML enrichment
# ---------------------------------------------------------------------------

def _maybe_enrich_admet(am: Optional[Dict[str, Any]], smiles: Optional[str]) -> Dict[str, Any]:
    """If the stored admet row has no ADMET-AI ML layer, call it live (once).

    Uses the isolated-venv subprocess so the main env stays torch-free.
    Cost is roughly model-load + prediction per candidate (~5-10 s on GPU).
    Returns the original row unchanged when ML is present or unavailable.
    """
    if not smiles:
        return am or {}
    if (am or {}).get("admet_ai") or (am or {}).get("admet_ai_flags"):
        return am or {}
    try:
        from protacxtend.tools.admet_integration import predict_admet_properties
        r = predict_admet_properties(smiles)
        out = dict(am or {})
        if r.get("admet_ai"):
            out["admet_ai"] = r["admet_ai"]
        if r.get("admet_ai_flags"):
            out["admet_ai_flags"] = r["admet_ai_flags"]
        out["prediction_source"] = r.get("prediction_source", "rules")
        return out
    except Exception as exc:  # pragma: no cover - best-effort
        logger = __import__("logging").getLogger("protacpilot.challenge_scorecard")
        logger.debug("ADMET-AI enrichment failed: %s", exc)
        return am or {}


def scorecard_from_workflow(workflow: Dict[str, Any],
                            candidate_id: Optional[str] = None,
                            enrich_admet_ai: bool = False) -> List[DimensionEvidence]:
    """Build the 10-dimension evidence list from a workflow-state dict.

    Set ``enrich_admet_ai=True`` to fill missing ADMET-AI ML rows by a live
    call to the isolated ADMET-AI backend (per candidate, ~5-10 s on GPU).
    """
    ac = _pick(workflow.get("assembled_candidates") or [], candidate_id)
    am = _pick(workflow.get("admet_predictions") or [], candidate_id)
    if enrich_admet_ai:
        am = _maybe_enrich_admet(am, (ac or {}).get("full_protac_smiles"))
    tc = _pick(workflow.get("ternary_feasibility_results") or [], candidate_id)
    ec = _pick(workflow.get("e3_context_predictions") or [], candidate_id)
    dg = _pick(workflow.get("degradation_predictions") or [], candidate_id)
    nv = _pick(workflow.get("novelty_results") or [], candidate_id)
    ad = _pick(workflow.get("applicability_domain_results") or [], candidate_id)
    neosub = _pick(workflow.get("neosubstrate_risk_results") or [], candidate_id)

    rows = [
        _cell_permeability(ac, am),
        _metabolic_stability(am),
        _solubility(am),
        _selectivity(ac, ec, nv, neosub),
        _ternary_complex(tc),
        _e3_choice(ec),
        _synthesis_feasibility(ac),
        _in_vivo_efficacy(dg),
        _safety(am),
        _developability(ac, am, ad),
    ]
    return rows


def scorecard_from_candidate_dict(cand: Dict[str, Any],
                                  enrich_admet_ai: bool = False) -> List[DimensionEvidence]:
    """Build the scorecard from a single flat candidate dict (CSV-style row)."""
    ac = cand if any(k in cand for k in ("full_protac_smiles", "candidate_id", "mw")) else None
    am = cand if any(k in cand for k in ("overall_admet_penalty", "hERG_risk", "AMES_risk")) else None
    if enrich_admet_ai:
        am = _maybe_enrich_admet(am, (ac or {}).get("full_protac_smiles"))
    tc = cand if any(k in cand for k in ("ternary_plausibility_score", "fast_geometry_feasibility_score")) else None
    ec = cand if any(k in cand for k in ("total_context_score", "expression_score")) else None
    dg = cand if any(k in cand for k in ("predicted_dc50_nM", "predicted_dmax_percent")) else None
    nv = cand if any(k in cand for k in ("top_similarity", "novelty_score")) else None
    ad = cand if any(k in cand for k in ("applicability_domain_score",)) else None
    neosub = cand if any(k in cand for k in ("neosubstrate_risk_score", "neosubstrate_targets")) else None

    rows = [
        _cell_permeability(ac, am),
        _metabolic_stability(am),
        _solubility(am),
        _selectivity(ac, ec, nv, neosub),
        _ternary_complex(tc),
        _e3_choice(ec),
        _synthesis_feasibility(ac),
        _in_vivo_efficacy(dg),
        _safety(am),
        _developability(ac, am, ad),
    ]
    return rows


def aggregate(rows: List[DimensionEvidence]) -> Dict[str, Any]:
    """Coverage, level counts and gap list across the 10 dimensions."""
    levels: Dict[str, int] = {}
    gaps: List[str] = []
    experimental: List[str] = []
    for r in rows:
        levels[r.evidence_level] = levels.get(r.evidence_level, 0) + 1
        if r.evidence_level == "no_evidence":
            gaps.append(r.label)
        if r.requires_experiment:
            experimental.append(r.label)
    return {
        "n_dimensions": len(rows),
        "covered": sum(1 for r in rows if r.evidence_level != "no_evidence"),
        "level_counts": levels,
        "gaps": gaps,
        "requires_experiment": experimental,
    }


def rows_to_dicts(rows: List[DimensionEvidence]) -> List[Dict[str, Any]]:
    return [r.to_dict() for r in rows]


def scorecard_markdown(rows: List[DimensionEvidence], candidate_id: str,
                       meta: Optional[Dict[str, Any]] = None) -> str:
    """Render the 10-dimension scorecard as a compact evidence table."""
    meta = meta or {}
    lines = [
        f"## Challenge scorecard — `{candidate_id}`",
        "",
        f"Tool: {TOOL_VERSION} · campaign={meta.get('campaign', '?')} · target={meta.get('target', '?')}",
        "",
        "| # | dimension | evidence | value |",
        "|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        val = (r.value if r.value is not None else "—")
        if isinstance(val, float):
            val = f"{val:.3g}"
        lines.append(f"| {i} | {r.label} | {r.evidence_level} | {val} |")
    agg = aggregate(rows)
    lines += [
        "",
        f"**Coverage:** {agg['covered']}/{agg['n_dimensions']} dimensions with in-silico evidence "
        f"({', '.join(f'{k}={v}' for k, v in agg['level_counts'].items())}).",
    ]
    if agg["gaps"]:
        lines += ["", f"**Gaps (no evidence):** {', '.join(agg['gaps'])}."]
    if agg["requires_experiment"]:
        lines += ["", f"**Requires experiment:** {', '.join(agg['requires_experiment'])}."]
    return "\n".join(lines)


def scorecard_report_json(rows: List[DimensionEvidence], candidate_id: str,
                          meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "tool_version": TOOL_VERSION,
        "candidate_id": candidate_id,
        "meta": meta or {},
        "dimensions": rows_to_dicts(rows),
        "aggregate": aggregate(rows),
    }


# ---------------------------------------------------------------------------
# CLI-adjacent helpers
# ---------------------------------------------------------------------------

def load_workflow_json(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_workflow_scorecard(path: str | Path, candidate_id: Optional[str] = None,
                           enrich_admet_ai: bool = False) -> Dict[str, Any]:
    """One-call entry: workflow JSON path -> full scorecard report dict."""
    workflow = load_workflow_json(path)
    rows = scorecard_from_workflow(workflow, candidate_id, enrich_admet_ai=enrich_admet_ai)
    cid = candidate_id or (workflow.get("assembled_candidates") or [{}])[0].get("candidate_id", "?")
    meta = {
        "campaign": str(Path(path).stem),
        "target": (workflow.get("target_record") or {}).get("name") or workflow.get("parsed_objective", {}).get("target", "?"),
        "enrich_admet_ai": enrich_admet_ai,
    }
    return scorecard_report_json(rows, cid, meta=meta)


if __name__ == "__main__":  # pragma: no cover - convenience CLI
    import sys
    path = sys.argv[1]
    cid = sys.argv[2] if len(sys.argv) > 2 else None
    report = run_workflow_scorecard(path, cid)
    print(json.dumps(report, indent=2, default=str))