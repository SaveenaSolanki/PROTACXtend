"""ProtacCandidate Evaluator — unified pipeline for assessing PROTAC candidates.

Coverage path: target/E3 → ternary complex → degradation → hook effect →
ADMET/chameleonicity → neosubstrate risk → resistance → developability → ranking.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

@dataclass
class EvaluationReport:
    candidate_id: str
    passed: bool = False
    scores: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)


def evaluate_protac_candidate(candidate, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Unified evaluation of a ProtacCandidate through the full pipeline.
    Returns results dict with scores, flags, evidence, and ranking.
    """
    results = {
        "candidate_id": getattr(candidate, 'candidate_id', str(id(candidate))),
        "status": "evaluated",
        "scores": {},
        "flags": [],
        "evidence": {},
        "developability": "unknown",
    }

    try:
        # 1. Structural validation
        results["structurally_valid"] = getattr(candidate, 'rdkit_valid', False)

        # 2. Ternary complex feasibility
        ternary_score = getattr(candidate, 'ternary_plausibility_score', 0.0)
        results["ternary_score"] = ternary_score
        results["scores"]["ternary"] = ternary_score

        # 3. Degradation prediction
        dc50 = getattr(candidate, 'predicted_dc50_nM', None)
        dmax = getattr(candidate, 'predicted_dmax_percent', None)
        results["degradation"] = {"dc50_nM": dc50, "dmax_percent": dmax}
        results["scores"]["degradation"] = 1.0 - (dc50 / 1000.0) if dc50 else 0.5

        # 4. Hook effect (if available)
        hook_ec50 = getattr(candidate, 'hook_effect_EC50', None)
        results["hook_effect"] = {"EC50": hook_ec50}

        # 5. Chameleonicity
        try:
            from protacxtend.modules.chameleonicity_3d import compute_chameleonicity
            if candidate.canonical_smiles:
                ch = compute_chameleonicity(candidate.canonical_smiles)
                results["chameleonicity"] = ch
                if ch.get("chameleonicity_score", 0) > 0.5:
                    results["flags"].append("high_chameleonicity")
        except Exception:
            pass

        # 6. Neosubstrate risk
        try:
            from protacxtend.modules.neosubstrate_risk import flag_offtarget
            ns = flag_offtarget(getattr(candidate, 'e3_ligase', ''), getattr(candidate, 'warhead_smiles', ''))
            results["neosubstrate_risk"] = ns
            if ns.get("action") == "flag":
                results["flags"].append("neosubstrate_flagged")
        except Exception:
            pass

        # 7. Resistance mechanisms
        try:
            from protacxtend.modules.resistance_mechanisms import predict_resistance
            res = predict_resistance(getattr(candidate, 'e3_ligase', ''))
            results["resistance"] = res
            if res.get("e3_mutation_risk") == "high":
                results["flags"].append("resistance_risk_high")
        except Exception:
            pass

        # 8. Proteome selectivity (BRD/BET domain-aware)
        try:
            from protacxtend.tools.proteome_selectivity import score_proteome_context
            target_gene = (getattr(candidate, 'target_gene', '') or
                           getattr(candidate, 'target', '') or 'unknown')
            ps = score_proteome_context(
                target=target_gene,
                e3=getattr(candidate, 'e3_ligase', ''),
                cell_line=(config or {}).get('cell_line', 'default'),
                warhead=(config or {}).get('warhead'),
                warhead_smiles=getattr(candidate, 'warhead_smiles', '') or None,
            )
            results["selectivity"] = ps.model_dump() if hasattr(ps, 'model_dump') else ps
            if results["selectivity"].get("off_target_risk", 0) > 0.5:
                results["flags"].append("high_off_target_risk")
        except Exception:
            pass

        # 8b. E3 suitability in the requested cell/tissue context
        try:
            from protacxtend.modules.e3_opportunity import rank_e3_ligases
            target_gene = (getattr(candidate, 'target_gene', '') or
                           getattr(candidate, 'target', '') or '')
            ctx = config or {}
            if target_gene and (ctx.get('cell_line') or ctx.get('tissue')):
                rank = rank_e3_ligases(
                    target_gene, cell_line=ctx.get('cell_line'),
                    tissue=ctx.get('tissue'), top_k=5)
                results["e3_suitability"] = rank.get("candidates", [])
        except Exception:
            pass

        # 9. Developability (aggregate score)
        selectivity = results.get("selectivity", {}) or {}
        off_target = selectivity.get("off_target_risk", 0.0)
        brd = selectivity.get("brd_bet_evidence") or {}
        brd_score = brd.get("score")
        if brd_score is not None:
            # weight measured BRD/BET evidence fully, a proxy prior at half
            w = 0.5 if brd.get("evidence_level") == "measured" else 0.25
            selectivity_term = (1.0 - off_target + w * brd_score) / (1.0 + w)
        else:
            selectivity_term = 1.0 - off_target
        score = (
            ternary_score * 0.25 +
            (1.0 - (dc50 / 1000.0 if dc50 else 0.5)) * 0.25 +
            (1.0 - results.get("neosubstrate_risk", {}).get("neosubstrate_risk_score", 0)) * 0.15 +
            (1.0 - results.get("resistance", {}).get("overall_resistance_risk", 0)) * 0.10 +
            (1.0 - results.get("chameleonicity", {}).get("chameleonicity_score", 0)) * 0.15 +
            selectivity_term * 0.10
        )
        results["overall_score"] = round(score, 4)
        results["developability"] = "good" if score > 0.6 else "moderate" if score > 0.3 else "poor"

    except Exception as e:
        results["status"] = "error"
        results["error"] = str(e)

    return results


def evaluate_batch(candidates: List, config: Dict = None) -> List[Dict]:
    """Evaluate multiple candidates and rank by overall_score."""
    results = [evaluate_protac_candidate(c, config) for c in candidates]
    results.sort(key=lambda x: x.get("overall_score", 0), reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1
    return results
