"""
Real ternary ensemble (Task 3) — at least two independent structural methods.
=============================================================================

Staged escalation (budget-controlled — never run expensive methods on every
candidate):

    geometric_score < 0.30 → reject_or_repair
    0.30 ≤ geometric < 0.60 → run_p4ward
    candidate is top-ranked → run_p4ward AND se3_protacs
    ensemble disagrees        → human_review

Methods (independent):
  1. geometric_proxy — deterministic reachability (our tool; cheap)
  2. p4ward          — full PROTAC-induced ternary docking (Docker; expensive)
  3. se3_protacs     — SE(3)-equivariant GNN with pretrained weights (real ML)

Consensus:
  - scores normalized to 0-1 (per-method min-max or provided)
  - agreement = fraction of methods agreeing on pass/fail vs 0.5
  - uncertainty from the spread of normalized scores
  - no method treated as ground truth; provenance kept per method

Schema: TernaryConsensusResult (see below).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("protacpilot.ternary.ensemble")


class TernaryConsensusResult(BaseModel):
    candidate_id: str = ""

    methods_run: List[str] = Field(default_factory=list)
    normalized_scores: Dict[str, float] = Field(default_factory=dict)
    agreement: float = 0.0
    consensus_score: float = 0.0

    interface_area: Optional[float] = None
    linker_strain: Optional[float] = None
    steric_clash_score: Optional[float] = None
    lysine_accessibility: Optional[float] = None

    uncertainty: float = 0.0
    status: Literal["supported", "ambiguous", "unsupported", "out_of_domain"] = "ambiguous"

    provenance: Dict[str, str] = Field(default_factory=dict)
    note: str = ""


# Escalation thresholds
GEOMETRIC_REJECT = 0.30
GEOMETRIC_P4WARD = 0.60
AGREEMENT_THRESHOLD = 0.66
CONSENSUS_PASS = 0.55


# ── Method adapters ───────────────────────────────────────────────────

def geometric_proxy_score(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Method 1: deterministic geometric reachability (real call)."""
    from synglue_agent.tools.ternary_feasibility import compute_ternary_feasibility_score
    try:
        # The toolbox expects a CandidateRecord; build one from the dict
        from synglue_agent.backend.schemas import CandidateRecord
        rec = CandidateRecord(**{k: v for k, v in candidate.items()
                                 if k in CandidateRecord.model_fields})
        score = compute_ternary_feasibility_score(rec)
        return {"score": max(0.0, min(1.0, float(score))), "ok": True, "tool": "geometric_proxy"}
    except Exception as exc:
        logger.warning("geometric proxy failed: %s", exc)
        return {"score": None, "ok": False, "tool": "geometric_proxy", "error": str(exc)[:120]}


def p4ward_score(candidate: Dict[str, Any], timeout_hours: float = 4.0) -> Dict[str, Any]:
    """Method 2: P4ward full ternary docking (Docker; expensive — budget-gated).

    The caller (escalation policy) decides when this runs. Returns the
    pass-rate as normalized score (0-1) when results exist.
    """
    from synglue_agent.tools.p4ward_wrapper import P4wardWrapper
    try:
        wrapper = P4wardWrapper()
        # In production this reads the p4ward run output; here we invoke the
        # wrapper's screen entry if input files are present in the candidate.
        run_dir = candidate.get("p4ward_run_dir")
        if not run_dir:
            return {"score": None, "ok": False, "tool": "p4ward", "error": "no_run_dir"}
        result = wrapper.run(
            receptor_pdb=candidate["receptor_pdb"],
            ligase_pdb=candidate["ligase_pdb"],
            receptor_ligand_mol2=candidate["receptor_ligand_mol2"],
            ligase_ligand_mol2=candidate["ligase_ligand_mol2"],
            protac_smiles=[candidate.get("full_protac_smiles", "")],
            e3=candidate.get("e3_ligase", "CRBN"),
            output_dir=run_dir,
            skip_prep=True,
        )
        pass_rate = getattr(result, "pass_rate", None) or getattr(result, "top_pass_rate", None)
        if pass_rate is None:
            return {"score": None, "ok": False, "tool": "p4ward", "error": "no_pass_rate"}
        return {"score": max(0.0, min(1.0, float(pass_rate))), "ok": True, "tool": "p4ward"}
    except Exception as exc:
        logger.warning("p4ward failed: %s", exc)
        return {"score": None, "ok": False, "tool": "p4ward", "error": str(exc)[:120]}


_SE3_CACHE: Dict[str, Any] = {}


def se3_protacs_score(
    candidate: Dict[str, Any],
    model_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Method 3: SE(3)-equivariant GNN with pretrained weights (real ML).

    Needs: SE3-PROTACs.pt weights + esm + se3_transformer_pytorch.
    Gracefully unavailable when the model or deps are missing.
    """
    import os
    if model_dir is None:
        model_dir = os.environ.get(
            "SE3_PROTACS_DIR",
            "data/protac_repos/repos/SE3-protacs",
        )
    model_path = os.path.join(model_dir, "model", "SE(3)-PROTACs.pt")
    if not os.path.exists(model_path):
        return {"score": None, "ok": False, "tool": "se3_protacs", "error": "weights_missing"}

    try:
        import sys as _sys
        import torch
        if "model" not in _SE3_CACHE:
            _sys.path.insert(0, model_dir)
            from model import Model, ESMWrapper, GraphTransformer  # type: ignore
            from utils import ESMEmbedder as _ESM  # type: ignore

            target_ligand_model = GraphTransformer(num_embeddings=10)
            ligase_ligand_model = GraphTransformer(num_embeddings=10)
            linker_model = GraphTransformer(num_embeddings=10)
            ligase_model = ESMWrapper()
            target_model = ESMWrapper()
            model = Model(
                ligase_ligand_model=ligase_ligand_model,
                ligase_model=ligase_model,
                target_ligand_model=target_ligand_model,
                target_model=target_model,
                linker_model=linker_model,
            )
            ckpt = torch.load(model_path, map_location="cpu")
            model.load_state_dict(ckpt["model_state_dict"])
            model.eval()
            _SE3_CACHE["model"] = model
            _SE3_CACHE["esm"] = _ESM(device="cuda" if torch.cuda.is_available() else "cpu")

        model = _SE3_CACHE["model"]
        esm = _SE3_CACHE["esm"]

        # Graph helpers live in casestudy.py (which imports model+utils safely)
        import casestudy  # type: ignore
        mol2graph = casestudy.mol2graph
        LIGAND_ATOM_TYPE = casestudy.LIGAND_ATOM_TYPE

        target_seq = candidate.get("target_sequence", "")
        ligase_seq = candidate.get("ligase_sequence", "")
        if not target_seq or not ligase_seq:
            return {"score": None, "ok": False, "tool": "se3_protacs", "error": "sequences_missing"}
        if not candidate.get("warhead_smiles") or not candidate.get("e3_ligand_smiles"):
            return {"score": None, "ok": False, "tool": "se3_protacs", "error": "ligand_smiles_missing"}

        ligase_ligand = mol2graph(candidate["e3_ligand_smiles"], LIGAND_ATOM_TYPE)
        warhead = mol2graph(candidate["warhead_smiles"], LIGAND_ATOM_TYPE)
        linker = mol2graph(candidate.get("linker_smiles", "CCOCC"), LIGAND_ATOM_TYPE)
        e3_emb = esm.embed_sequence(ligase_seq)
        target_emb = esm.embed_sequence(target_seq)

        # Match the model's device (model may be on GPU)
        dev = next(model.parameters()).device
        ligase_ligand = ligase_ligand.to(dev)
        warhead = warhead.to(dev)
        linker = linker.to(dev)
        e3_emb = e3_emb.to(dev)
        target_emb = target_emb.to(dev)

        with torch.no_grad():
            logits, _, _ = model(
                ligase_ligand, e3_emb.unsqueeze(0),
                warhead, target_emb.unsqueeze(0),
                linker,
            )
        probs = torch.softmax(logits, dim=1)
        prob = float(probs[:, 1].item())
        return {"score": max(0.0, min(1.0, prob)), "ok": True, "tool": "se3_protacs"}
    except Exception as exc:
        logger.warning("se3_protacs unavailable: %s", exc)
        return {"score": None, "ok": False, "tool": "se3_protacs", "error": str(exc)[:120]}


# ── Escalation policy (budget-controlled) ─────────────────────────────

def escalation_plan(
    candidate: Dict[str, Any],
    top_ranked: bool = False,
    budget: Dict[str, bool] | None = None,
) -> List[str]:
    """Decide which methods run for this candidate (deterministic)."""
    budget = budget or {"p4ward": True, "se3": True}
    geom = geometric_proxy_score(candidate)
    g = geom.get("score") if geom.get("ok") else None

    plan: List[str] = ["geometric_proxy"]
    if g is None:
        plan.append("se3_protacs" if budget.get("se3") else "p4ward")
        return plan
    if g < GEOMETRIC_REJECT:
        return plan                      # reject/repair — no expensive compute
    if g < GEOMETRIC_P4WARD and budget.get("p4ward"):
        plan.append("p4ward")
    elif top_ranked and budget.get("p4ward"):
        plan.append("p4ward")
        if budget.get("se3"):
            plan.append("se3_protacs")
    elif top_ranked and budget.get("se3"):
        plan.append("se3_protacs")
    return plan


def run_ensemble(
    candidate: Dict[str, Any],
    methods: Optional[List[str]] = None,
    top_ranked: bool = False,
    budget: Optional[Dict[str, bool]] = None,
) -> TernaryConsensusResult:
    """Run the ensemble for one candidate and aggregate consensus."""
    methods = methods or escalation_plan(candidate, top_ranked=top_ranked, budget=budget)

    runners = {
        "geometric_proxy": geometric_proxy_score,
        "p4ward": p4ward_score,
        "se3_protacs": se3_protacs_score,
    }

    scores: Dict[str, float] = {}
    provenance: Dict[str, str] = {}
    details: Dict[str, Any] = {}
    for m in methods:
        if m not in runners:
            continue
        res = runners[m](candidate)
        if res.get("ok") and res.get("score") is not None:
            scores[m] = float(res["score"])
            provenance[m] = "ok"
        else:
            provenance[m] = f"failed:{res.get('error', 'unknown')[:60]}"

    if not scores:
        return TernaryConsensusResult(
            candidate_id=candidate.get("candidate_id", ""),
            methods_run=methods,
            status="out_of_domain",
            note="all ternary methods failed — no consensus possible",
            provenance=provenance,
        )

    # ── Consensus on RAW scores (0-1 from each method) ──
    # Agreement must be computed on raw values: min-max normalization would
    # make two close scores look maximally disagreeing (0 and 1).
    vals = list(scores.values())
    consensus = float(sum(vals) / len(vals))

    # Agreement: fraction of methods on the same side of CONSENSUS_PASS
    passes = sum(1 for v in vals if v >= CONSENSUS_PASS)
    agreement = passes / len(vals) if vals else 0.0

    # Uncertainty: spread of raw scores, scaled 0-1
    spread = (max(vals) - min(vals)) if len(vals) > 1 else 0.0
    uncertainty = min(1.0, spread)

    # Normalized scores for display only (min-max to 0-1)
    lo, hi = min(vals), max(vals)
    normalized = {
        k: round(((v - lo) / (hi - lo) if hi > lo else 0.5), 4) for k, v in scores.items()
    }

    if agreement >= AGREEMENT_THRESHOLD:
        status = "supported" if consensus >= CONSENSUS_PASS else "unsupported"
    else:
        status = "ambiguous" if len(normalized) > 1 else (
            "supported" if consensus >= CONSENSUS_PASS else "unsupported"
        )

    note = ""
    if status == "ambiguous" and len(normalized) > 1:
        note = "ensemble disagrees — human review required"

    return TernaryConsensusResult(
        candidate_id=candidate.get("candidate_id", ""),
        methods_run=[m for m in methods if m in scores or provenance.get(m, "").startswith("failed")],
        normalized_scores={k: round(v, 4) for k, v in normalized.items()},
        agreement=round(agreement, 3),
        consensus_score=round(consensus, 4),
        interface_area=candidate.get("interface_area"),
        linker_strain=candidate.get("linker_strain"),
        steric_clash_score=candidate.get("steric_clash_score"),
        lysine_accessibility=candidate.get("lysine_accessibility"),
        uncertainty=round(uncertainty, 4),
        status=status,  # type: ignore[assignment]
        provenance=provenance,
        note=note,
    )


def route_after_ternary_consensus(result: TernaryConsensusResult) -> str:
    """Graph routing from the consensus verdict."""
    mapping = {
        "supported": "degradation_prediction",
        "unsupported": "repair_controller",
        "ambiguous": "human_gate",
        "out_of_domain": "human_gate",
    }
    return mapping.get(result.status, "human_gate")
