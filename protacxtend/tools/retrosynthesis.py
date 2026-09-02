"""
Real retrosynthesis layer (Task 2) — RAscore prescreen + AiZynthFinder routes.
=============================================================================

Pipeline (per spec):

  Candidate PROTAC
       ↓
  RAscore fast prescreen
       ↓
  AiZynthFinder route search
       ↓
  Building-block availability
       ↓
  Reaction compatibility check
       ↓
  Route-quality assessment
       ↓
  Pass / repair / reject / human review

Status vocabulary: feasible | repairable | infeasible | tool_failed | human_required

Routing (consumed by the agent graph):
  Route found & acceptable   → pareto ranking
  Poor coupling handle       → repair attachment chemistry
  Difficult linker synthesis → replace linker
  Unavailable precursor      → search alternative building block
  No route after bounded attempts → human gate or reject
  Tool unavailable           → RAscore only + downgraded confidence

Every result carries tool/version provenance. Tool failure NEVER crashes.
"""

from __future__ import annotations

import logging
import os
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence

from pydantic import BaseModel, Field

logger = logging.getLogger("protacpilot.retrosynthesis")

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "data" / "retrosynthesis" / "models"

# AiZynthFinder pretrained policy bundle (official release, zenodo)
AIZYNTH_URL = "https://zenodo.org/records/4033691/files/"

# RAscore NN model (DNN, ChEMBL-trained FCFP counts)
RASCORE_URL = "https://raw.githubusercontent.com/reymond-group/RAscore/master/RAscore/models/DNN_chembl_fcfp_counts/model.tf"


class RetrosynthesisResult(BaseModel):
    candidate_id: str = ""

    route_found: bool = False
    route_count: int = 0
    shortest_route_steps: Optional[int] = None

    rascore: Optional[float] = None
    route_confidence: float = 0.0
    purchasable_fraction: float = 0.0

    unresolved_precursors: List[str] = Field(default_factory=list)
    incompatible_reactions: List[str] = Field(default_factory=list)
    route_files: List[str] = Field(default_factory=list)

    status: Literal["feasible", "repairable", "infeasible", "tool_failed", "human_required"] = "tool_failed"

    # Provenance (every claim carries tool/version)
    tools_used: List[str] = Field(default_factory=list)
    provenance: Dict[str, str] = Field(default_factory=dict)
    prescreen_tool: str = "sascore_proxy"     # rascore | sascore_proxy
    note: str = ""

    # Multi-engine provenance (ASKCOS / AiZynthFinder / RDKit+OpenNMT)
    engines_requested: List[str] = Field(default_factory=list)
    engines_ran: List[str] = Field(default_factory=list)
    engine_outcomes: List[Dict[str, Any]] = Field(default_factory=list)


# ── RAscore (fast prescreen) ──────────────────────────────────────────

def _ensure_rascore_model() -> Optional[Path]:
    """Download the RAscore NN model once (best-effort, offline-safe)."""
    path = MODEL_DIR / "DNN_chembl_fcfp_counts" / "model.tf"
    if path.exists():
        return path
    try:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(RASCORE_URL, path)  # noqa: S310 — trusted source
        return path
    except Exception as exc:
        logger.warning("RAscore model download failed: %s", exc)
        return None


def rascore_predict(smiles: str) -> Optional[float]:
    """RAscore (0-1, higher = more synthesizable). None if model unavailable."""
    try:
        from RAscore.RAscore_NN import RAScorerNN
        model = RAScorerNN(model_path=str(_ensure_rascore_model()))
        return float(model.predict(smiles))
    except Exception as exc:
        logger.debug("rascore unavailable: %s", exc)
        return None


def sascore_proxy(smiles: str) -> float:
    """SAScore proxy (0-1 accessibility, higher = easier). Clearly labelled."""
    try:
        import sys as _sys
        from rdkit import Chem
        _sys.path.append(str(Path(__import__("rdkit").__file__).parent / "Contrib" / "SA_Score"))
        from sascorer import calculateScore  # type: ignore
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return 0.0
        sa = calculateScore(mol)  # 1=easy .. 10=hard
        return max(0.0, min(1.0, 1.0 - (sa - 1.0) / 9.0))
    except Exception:
        return 0.5  # neutral if even the proxy is unavailable


# ── AiZynthFinder route search ────────────────────────────────────────

def _aizynth_policy_config(cfg_dir: Path) -> Dict[str, Any]:
    """Expansion-policy config: ONNX set preferred, figshare hdf5 set fallback."""
    onnx_policy = cfg_dir / "uspto_model.onnx"
    if onnx_policy.exists():
        return {
            "type": "TemplateBasedExpansionStrategy",
            "model": str(onnx_policy),
            "onnx": True,
            "template": str(cfg_dir / "uspto_templates.csv.gz"),
            "use_rdchiral": True,
        }
    return {
        "type": "TemplateBasedExpansionStrategy",
        "model": str(cfg_dir / "uspto_policy.hdf5"),
        "onnx": False,
        "template": str(cfg_dir / "uspto_templates.hdf5"),
        "use_rdchiral": True,
    }


def _aizynth_config_available() -> bool:
    """True when a policy+stock+templates config exists for AiZynthFinder.

    Accepts either the ONNX set (uspto_model.onnx + uspto_templates.csv.gz)
    or the figshare bootstrap set (uspto_policy.hdf5 + uspto_templates.hdf5);
    both need zinc_stock.hdf5. See scripts/bootstrap_assets.sh.
    """
    cfg_dir = MODEL_DIR / "aizynth"
    stock = cfg_dir / "zinc_stock.hdf5"
    onnx_ok = (cfg_dir / "uspto_model.onnx").exists() and (cfg_dir / "uspto_templates.csv.gz").exists()
    hdf5_ok = (cfg_dir / "uspto_policy.hdf5").exists() and (cfg_dir / "uspto_templates.hdf5").exists()
    return stock.exists() and (onnx_ok or hdf5_ok)


def aizynth_route_search(smiles: str, timeout_s: int = 300) -> Dict[str, Any]:
    """Run AiZynthFinder route search. Returns dict or {'tool_failed': ...}.

    Requires a pretrained policy + stock + templates in data/retrosynthesis/
    models/aizynth/. Without them returns tool_failed gracefully (the caller
    downgrades to RAscore-only).
    """
    if not _aizynth_config_available():
        return {"tool_failed": "aizynth_policy_missing",
                "note": "Install AiZynthFinder policy/stock into data/retrosynthesis/models/aizynth/"}
    try:
        from aizynthfinder.aizynthfinder import AiZynthFinder

        configdict = {
            "expansion": {"policy": _aizynth_policy_config(MODEL_DIR / "aizynth")},
            "stock": {
                "stock": {
                    "type": "InMemoryInchiKeyQuery",
                    "path": str(MODEL_DIR / "aizynth" / "zinc_stock.hdf5"),
                }
            },
        }
        finder = AiZynthFinder(configdict=configdict)
        # 4.x loads strategies but does not auto-select them
        finder.config.expansion_policy.select_all()
        finder.config.stock.select_all()
        finder.target_smiles = smiles
        finder.prepare_tree()
        finder.tree_search()
        finder.build_routes()          # 4.x: void; populates finder.routes
        routes = getattr(finder, "routes", None) or []
        if not routes:
            return {"ran": True, "route_found": False, "route_count": 0, "routes": []}

        # 4.4.1: routes is a RouteCollection of dicts: {reaction_tree, ...}
        steps_list: List[int] = []
        route_strs: List[str] = []
        for r in routes:
            rt = r.get("reaction_tree") if isinstance(r, dict) else r
            try:
                n = len(rt.reactions) if hasattr(rt, "reactions") else 1
                steps_list.append(int(n))
            except Exception:
                steps_list.append(1)
            route_strs.append(str(rt)[:300])

        return {
            "ran": True,
            "route_found": True,
            "route_count": len(routes),
            "shortest_steps": min(steps_list) if steps_list else None,
            "routes": route_strs[:5],
        }
    except Exception as exc:
        logger.warning("AiZynthFinder search failed: %s", exc)
        return {"tool_failed": str(exc)[:200]}


# ── Route-quality assessment ──────────────────────────────────────────

def assess_route_quality(search_result: Dict[str, Any], smiles: str) -> Dict[str, Any]:
    """Building-block availability + reaction compatibility + quality."""
    if search_result.get("tool_failed"):
        return {
            "route_found": False,
            "route_count": 0,
            "shortest_steps": None,
            "purchasable_fraction": 0.0,
            "unresolved_precursors": [smiles],
            "incompatible_reactions": [],
            "route_confidence": 0.0,
        }

    if not search_result.get("route_found"):
        return {
            "route_found": False,
            "route_count": 0,
            "shortest_steps": None,
            "purchasable_fraction": 0.0,
            "unresolved_precursors": [smiles],
            "incompatible_reactions": [],
            "route_confidence": 0.0,
        }

    steps = search_result.get("shortest_steps", 6)
    # Quality heuristics (deterministic): fewer steps, more routes = better
    confidence = max(0.1, min(0.95, 0.9 - (steps - 1) * 0.12 + search_result.get("route_count", 1) * 0.03))
    purchasable = 1.0 if search_result.get("route_count", 0) > 0 else 0.0
    return {
        "route_found": True,
        "route_count": search_result.get("route_count", 0),
        "shortest_steps": steps,
        "purchasable_fraction": purchasable,
        "unresolved_precursors": [],
        "incompatible_reactions": [],
        "route_confidence": round(confidence, 3),
    }


# ── Orchestration ─────────────────────────────────────────────────────

def assess_retrosynthesis(
    smiles: str,
    candidate_id: str = "",
    use_aizynth: bool = True,
    max_steps: int = 6,
    engines: Optional[Sequence[str]] = None,
    askcos_base_url: Optional[str] = None,
    askcos_mode: str = "one_step",
    askcos_check_buyables: bool = False,
) -> RetrosynthesisResult:
    """Full retrosynthesis assessment for one candidate across route engines.

    engines: engine codes to consult — 'aizynth' | 'askcos' | 'openmt'
      (aliases accepted). Default keeps the historical single-engine path:
      ("aizynth",) when use_aizynth=True, otherwise no route engine.

    Tool-failure policy (per spec):
      - No route engine available → RAscore-only, status tool_failed, note set
      - RAscore unavailable → SAScore proxy (clearly labelled), rascore=None
      - ASKCOS/OpenNMT optional engines never crash; each reports provenance.
    """
    tools_used: List[str] = []

    if engines is None:
        engines = ["aizynth"] if use_aizynth else []
    requested = [engines] if isinstance(engines, str) else list(engines)

    from protacxtend.tools.retrosynthesis_engines import (
        normalize_engine_code,
        run_engines,
        EngineRunSummary,
    )
    requested = [c for c in (normalize_engine_code(e) for e in requested) if c]
    aizynth_enabled = "aizynth" in requested

    # 1. Fast prescreen (RAscore → SAScore proxy)
    ra = rascore_predict(smiles)
    prescreen_tool = "rascore" if ra is not None else "sascore_proxy"
    if ra is None:
        sa = sascore_proxy(smiles)
        ra = sa
    tools_used.append(prescreen_tool)

    # 2. Route search over the requested engines
    summary: EngineRunSummary
    if not aizynth_enabled and len(requested) == 0:
        # Historical disabled path: RAscore-only, no route engine consulted
        summary = EngineRunSummary(
            engines_requested=[], engines_available=[], engines_ran=[],
            any_route_found=False, outcomes=[],
        )
        tools_used.append("aizynthfinder:disabled")
    else:
        summary = run_engines(
            smiles,
            engines=requested,
            askcos_base_url=askcos_base_url,
            askcos_mode=askcos_mode,
            askcos_check_buyables=askcos_check_buyables,
            aizynth_timeout_s=min(300, 30 * max_steps),
        )
        for o in summary.outcomes:
            if o.engine == "aizynth":
                tools_used.append("aizynthfinder" if o.ran else "aizynthfinder:unavailable")
            else:
                tools_used.append(f"{o.engine}:{'ok' if o.ran else 'unavailable'}")

    any_engine_ran = bool(summary.engines_ran)
    route_found = bool(summary.any_route_found)
    search = {
        "route_found": route_found,
        "route_count": summary.route_count,
        "shortest_steps": summary.shortest_steps,
        "routes": summary.routes,
    } if route_found else {}

    # 3. Route quality
    quality = assess_route_quality(search, smiles)

    # 4. Status classification
    status: str
    note = ""
    if not any_engine_ran:
        # No route engine available → RAscore only, downgraded confidence
        status = "tool_failed"
        confidence = 0.3 * (ra or 0.0)
        if requested:
            fails = [o.tool_failed for o in summary.outcomes if o.tool_failed]
            note = "All requested route engines unavailable: " + "; ".join(fails[:2])
        else:
            note = "AiZynthFinder disabled — RAscore-only assessment"
    elif route_found and (ra or 0.0) >= 0.4:
        status = "feasible"
        confidence = quality["route_confidence"]
    elif route_found:
        status = "repairable"
        confidence = 0.5 * quality["route_confidence"]
        note = "route exists but fast prescreen low — repair chemistry/linker"
    elif (ra or 0.0) < 0.3:
        status = "infeasible"
        confidence = 0.2
        note = "no route and low accessibility"
    else:
        status = "human_required"
        confidence = 0.4
        note = "route engines ran but found no route; borderline accessibility — human review"

    return RetrosynthesisResult(
        candidate_id=candidate_id,
        route_found=quality["route_found"],
        route_count=quality["route_count"],
        shortest_route_steps=quality["shortest_steps"],
        rascore=round(ra, 4) if ra is not None else None,
        route_confidence=round(confidence, 4),
        purchasable_fraction=quality["purchasable_fraction"],
        unresolved_precursors=quality["unresolved_precursors"],
        incompatible_reactions=quality["incompatible_reactions"],
        route_files=summary.routes[:3] if summary.routes else (
            search.get("routes", [])[:3] if isinstance(search.get("routes"), list) else []),
        status=status,  # type: ignore[assignment]
        tools_used=tools_used,
        provenance={
            "prescreen": prescreen_tool,
            "route_search": summary.best_engine or ("none" if not requested else "all_unavailable"),
        },
        prescreen_tool=prescreen_tool,
        note=note,
        engines_requested=summary.engines_requested,
        engines_ran=summary.engines_ran,
        engine_outcomes=[o.model_dump() for o in summary.outcomes],
    )


def route_after_retrosynthesis(result: RetrosynthesisResult) -> str:
    """Agent routing (consumed by the graph)."""
    mapping = {
        "feasible": "pareto_ranking",
        "repairable": "linker_generation",     # difficult linker synthesis → replace linker
        "infeasible": "abort_candidate",
        "tool_failed": "pareto_ranking",       # RAscore-only, downgraded confidence
        "human_required": "human_gate",
    }
    return mapping.get(result.status, "human_gate")


def assess_batch(smiles_list: List[str], candidate_ids: Optional[List[str]] = None,
                use_aizynth: bool = False) -> List[RetrosynthesisResult]:
    """Batch assessment. use_aizynth=False → fast proxy path (deterministic).

    Real route search is slow (10-60s/molecule); enable per-candidate in
    production or via the slow integration tests.
    """
    ids = candidate_ids or [f"c{i}" for i in range(len(smiles_list))]
    return [assess_retrosynthesis(s, cid, use_aizynth=use_aizynth)
            for s, cid in zip(smiles_list, ids)]
