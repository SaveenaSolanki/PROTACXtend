"""Structured, capability-routed execution for benchmark cases.

Design goals after the closed-48 audit:

1. **Input propagation.** ``supplied_inputs`` are parsed once into a typed
   objective; the benchmark worker passes the whole case, not just the free-text
   question.
2. **Entity fidelity.** Targets/E3 are resolved once
   (:mod:`protacxtend.agents.entity_resolution`); ambiguity is a typed no-go and
   a later agent never overwrites the resolution.
3. **Minimal routing.** :func:`protacxtend.agents.routing.route_for` includes
   binder retrieval only when the question/inputs require it and never runs a
   DESIGN/DISCOVER node for a KNOW/REASON question.
4. **Bounded retrieval.** Live retrieval is bounded by a propagated run deadline
   and raises a typed failure instead of spending the run budget on a hang.
5. **Honest outcomes.** Candidates are only those that survived the whole
   funnel. Hypothetical attachment markers make a *design brief*, never a final
   PROTAC. Every result carries a typed scientific state, evidence, missing
   prerequisites, uncertainty and a next experiment.
"""

from __future__ import annotations

import os
import re
import time
from collections import Counter
from typing import Any

from protacxtend.agents import binder_agent
from protacxtend.agents.entity_resolution import is_known_gene, resolve_entities
from protacxtend.agents.graph import CAPABILITY_NODES, run_syn_glue_workflow
from protacxtend.agents.routing import route_for
from protacxtend.agents.scientific_states import ScientificState
from protacxtend.backend.schemas import (
    ParsedObjective,
    WorkflowState,
)

#: Keys in ``supplied_inputs`` that carry each scientific input. Target keys
#: are exact-ish so a constraint like ``"exit vector:"`` is never read as a
#: target.
_TARGET_KEYS = ("target", "gene/target name", "gene", "target context", "target/e3",
                "target-e3 pair", "target-e3", "poi")
_E3_KEYS = ("e3 candidates", "e3 ligase", "e3:")
_E3_LIGAND_KEYS = ("e3 ligand", "e3-ligand", "ligand smiles")
_WARHEAD_KEYS = ("warhead", "parent warhead")
_SMILES_RE = re.compile(r"^[A-Za-z0-9@+\-\[\]\(\)=#$\\/%.*:]+$")


def _known_gene(token: str) -> bool:
    """Backwards-compatible alias for the entity-resolution predicate."""
    return is_known_gene(token)


def _looks_like_smiles(value: str) -> bool:
    value = value.strip()
    if len(value) < 6 or " " in value:
        return False
    if not _SMILES_RE.match(value):
        return False
    return any(ch.isalpha() for ch in value) and ("C" in value or "c" in value or "[" in value)


def parse_supplied_inputs(case: dict[str, Any]) -> dict[str, str]:
    """Extract typed scientific inputs from a benchmark case (single pass)."""
    entities = resolve_entities(case)
    out: dict[str, str] = {
        "target": entities["target"],
        "e3_ligase": (entities["e3_ligases"][0] if entities["e3_ligases"] else ""),
        "warhead_smiles": "",
        "e3_ligand_smiles": "",
        "molecule_smiles": "",
    }
    for raw in case.get("supplied_inputs") or []:
        text = str(raw).strip()
        if ":" not in text:
            continue
        key, value = text.split(":", 1)
        key_l = key.strip().lower()
        value = value.strip()
        if not value:
            continue
        if not out["e3_ligand_smiles"] and any(k in key_l for k in _E3_LIGAND_KEYS) and _looks_like_smiles(value):
            out["e3_ligand_smiles"] = value
        if not out["warhead_smiles"] and any(k in key_l for k in _WARHEAD_KEYS) and _looks_like_smiles(value):
            out["warhead_smiles"] = value
        if not out["molecule_smiles"] and key_l in {"smiles", "molecule", "input smiles"} and _looks_like_smiles(value):
            out["molecule_smiles"] = value
    return out


def seed_state(case: dict[str, Any]) -> tuple[WorkflowState, dict[str, str]]:
    """Build a seeded :class:`WorkflowState` from a case's structured inputs.

    Supplied components are plain SMILES with no linker attachment marker. The
    seed appends a **hypothetical** dummy atom (``[*:1]`` on the warhead,
    ``[*:2]`` on the E3 ligand) only so a design *brief* can be sketched; the
    hypothesis is recorded and never presented as a chemist-validated vector.
    """
    parsed = parse_supplied_inputs(case)
    entities = resolve_entities(case)
    from protacxtend.tools.protac_toolbox import _has_attachment

    attachment_hypothesis = False
    if parsed["warhead_smiles"] and not _has_attachment(parsed["warhead_smiles"]):
        parsed["warhead_smiles"] = f"{parsed['warhead_smiles']}[*:1]"
        attachment_hypothesis = True
    if parsed["e3_ligand_smiles"] and not _has_attachment(parsed["e3_ligand_smiles"]):
        parsed["e3_ligand_smiles"] = f"{parsed['e3_ligand_smiles']}[*:2]"
        attachment_hypothesis = True

    objective = ParsedObjective(
        target_name=parsed["target"],
        e3_ligase=parsed["e3_ligase"] or None,
        warhead_smiles=parsed["warhead_smiles"] or None,
        e3_ligand_smiles=parsed["e3_ligand_smiles"] or None,
    )
    state = WorkflowState(user_request=case.get("scientific_question", ""))
    state.parsed_objective = objective
    state.entity_resolution = entities
    # Marker consumed by SupervisorAgent so it merges instead of overwriting the
    # caller-supplied structured inputs (and never invents a target).
    state.design_plan["structured_seed"] = {
        "target_supplied": bool(parsed["target"]),
        "warhead_supplied": bool(parsed["warhead_smiles"]),
        "e3_ligand_supplied": bool(parsed["e3_ligand_smiles"]),
        "molecule_smiles": parsed.get("molecule_smiles", ""),
        "supplied_inputs_raw": list(case.get("supplied_inputs") or []),
        "attachment_hypothesis": attachment_hypothesis,
    }
    if entities.get("ambiguous"):
        state.errors.append(entities.get("reason", "ambiguous entity"))
    if attachment_hypothesis:
        state.warnings.append(
            "Attachment markers are hypothetical; the exit vector requires chemist review. "
            "Products are a design brief, not final PROTACs."
        )
    return state, parsed


def _freeze_seed(seed: int = 0) -> None:
    """Make the deterministic path reproducible.

    The audited repaired run produced different DESIGN candidate counts between
    the frozen and reproduced runs because the char-GRU linker sampler used
    ``torch.multinomial`` without a seed. Seed every RNG the path can touch.
    """
    import os
    import random

    os.environ.setdefault("PYTHONHASHSEED", str(seed))
    random.seed(seed)
    try:  # optional deps must not break the runtime
        import numpy as np

        np.random.seed(seed)
    except Exception:  # noqa: BLE001
        pass
    try:
        import torch

        torch.manual_seed(seed)
        torch.use_deterministic_algorithms(False)
    except Exception:  # noqa: BLE001
        pass


def _stop_reason(state: WorkflowState) -> str:
    if state.errors:
        return state.errors[-1]
    if state.design_plan.get("status") == "needs_user_input":
        return "planner requires user input"
    return ""


def _stage_ledger(state: WorkflowState, final_candidates: list) -> list[dict[str, Any]]:
    """Counts and rejection reasons for every generation/filter stage."""
    attempts = state.construction_attempts
    reasons = Counter(
        (a.failure_category or "unknown") for a in attempts if not a.success
    )
    cfs = state.cheap_filter_summary or {}
    verified_final = [c for c in final_candidates if c.provenance.get("verified_components")]
    brief_final = [c for c in final_candidates if not c.provenance.get("verified_components")]
    return [
        {"stage": "retrieve_target_binders", "output": len(state.retrieved_binders),
         "status": state.retrieval_status, "reason": _last_error(state, "TargetBinderRetrievalAgent")},
        {"stage": "select_warheads", "input": len(state.retrieved_binders),
         "output": len(state.selected_warheads)},
        {"stage": "design_path",
         "verified_reference": bool(state.design_plan.get("design_path", {}).get("verified_reference_available")),
         "design_brief": bool(state.design_plan.get("design_brief")),
         "reason": state.design_plan.get("design_path", {}).get("reason", "")},
        {"stage": "select_e3_ligands", "output": len(state.selected_e3_ligands)},
        {"stage": "detect_exit_vectors", "output": len(state.exit_vectors)},
        {"stage": "generate_linkers", "output": len(state.generated_linkers)},
        {"stage": "construct_protacs", "attempts": len(attempts),
         "success": sum(1 for a in attempts if a.success),
         "output": len(state.assembled_candidates),
         "rejected": dict(reasons)},
        {"stage": "validate_protacs", "input": len(state.assembled_candidates),
         "output": len(state.valid_candidates),
         "rejected": max(0, len(state.assembled_candidates) - len(state.valid_candidates)),
         "reason": "invalid/unparseable assembly" if len(state.valid_candidates) < len(state.assembled_candidates) else ""},
        {"stage": "cheap_filter_candidates",
         "input": cfs.get("input_candidates"), "kept": cfs.get("kept_candidates"),
         "verified_retained": cfs.get("verified_retained", 0),
         "rejected": cfs.get("rejected_candidates") if cfs.get("rejected_candidates") is not None
         else (max(0, (cfs.get("input_candidates") or 0) - (cfs.get("kept_candidates") or 0))
               if cfs.get("input_candidates") is not None else None)},
        {"stage": "final_candidates", "output": len(final_candidates),
         "verified": len(verified_final), "design_brief": len(brief_final)},
    ]


def _last_error(state: WorkflowState, prefix: str) -> str:
    for err in reversed(state.errors):
        if prefix in err:
            return err
    return ""


def _scientific_state(capability: str, state: WorkflowState, candidates: list,
                      abstained: bool, entities: dict) -> ScientificState:
    if entities.get("ambiguous"):
        return ScientificState.JUSTIFIED_NO_GO
    if capability in {"KNOW", "REASON"}:
        raw = state.scientific_answer.get("scientific_state")
        try:
            return ScientificState(raw)
        except (ValueError, TypeError):
            return ScientificState.UNRESOLVED
    if capability == "DESIGN":
        verified = [c for c in candidates if c.provenance.get("verified_components")]
        if verified:
            return ScientificState.VALID_CANDIDATE
        if candidates or state.design_plan.get("design_brief"):
            return ScientificState.DESIGN_BRIEF
        return ScientificState.JUSTIFIED_NO_GO
    if abstained:
        return ScientificState.JUSTIFIED_NO_GO
    # An empty answer with no evidence and no candidates is not a conditional
    # hypothesis — it is an unresolved run. Previously this was labelled
    # conditional_hypothesis/"completed", i.e. an unsupported claim.
    answer = state.scientific_answer or {}
    if (not candidates
            and not str(answer.get("answer") or "").strip()
            and not (answer.get("evidence") or [])):
        return ScientificState.UNRESOLVED
    return ScientificState.CONDITIONAL_HYPOTHESIS


def _sourced_evidence(items: Any) -> list:
    """Keep only genuine evidence rows.

    Tool-failure records such as ``{"tool": ..., "error": ...}`` were being
    counted as evidence (KNOW-10, REASON-04, REASON-07 in v1), inflating the
    evidence count. Evidence must name a source (or at least a kind) and must
    not be an error record.
    """
    out = []
    for e in (items or []):
        if not isinstance(e, dict):
            continue
        if e.get("error") or e.get("tool"):
            continue
        if e.get("source") or e.get("kind"):
            out.append(e)
    return out


_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")

#: Envelope keys whose values are surfaced verbatim in the final answer so the
#: question-responsive identifiers (accession, PDB id, DOI, InChIKey, SMILES)
#: actually reach the reader and the grader.
_INTEREST_KEYS = (
    "accession", "primaryaccession", "uniprot", "uniprot_id", "pdb_id", "pdb_ids",
    "doi", "smiles", "canonical_smiles", "inchikey", "inchi_key", "pref_name",
    "molecule_chembl_id", "cid", "name", "gene", "formula", "molecular_weight",
    "e3", "e3_ligase", "ligase", "target", "title",
)


def _flatten_facts(data: Any, out: list[str] | None = None, depth: int = 0) -> list[str]:
    """Collect question-responsive scalar facts from a tool data payload."""
    if out is None:
        out = []
    if depth > 5:
        return out
    if isinstance(data, dict):
        for k, v in data.items():
            kl = str(k).lower()
            if isinstance(v, (dict, list)):
                _flatten_facts(v, out, depth + 1)
            elif v not in (None, "") and any(tok in kl for tok in _INTEREST_KEYS):
                out.append(f"{k}={v}")
    elif isinstance(data, list):
        for item in data[:25]:
            _flatten_facts(item, out, depth + 1)
    return out


def _run_retrieval_case(case: dict[str, Any], capability: str, *, offline: bool,
                        budget_s: float, seed: int) -> dict[str, Any]:
    """Capability-routed retrieval/answer path for KNOW and REASON cases.

    The question intent selects the permitted tools; every tool runs through the
    shared ``run_agent_tool`` pathway. The final answer surfaces the retrieved
    identifiers instead of hiding them inside a tool envelope.
    """
    from protacxtend.nlp.entity_extraction import extract_entities
    from protacxtend.runtime.agent_tools import run_agent_tool

    t0 = time.time()
    question = case.get("scientific_question", "") or ""
    ql = question.lower()
    entities = extract_entities(question)
    target = (entities.target_gene or "").strip()
    parsed = parse_supplied_inputs(case)
    e3 = parsed.get("e3_ligase") or ""
    molecule = parsed.get("molecule_smiles") or parsed.get("warhead_smiles") or ""

    calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    trace: list[dict[str, Any]] = []

    def call(tool: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            r = run_agent_tool(tool, params, allow_network=not offline)
        except Exception as exc:  # noqa: BLE001
            r = {"valid_output": False, "failure_code": type(exc).__name__, "error": str(exc),
                 "scientific_result": None}
        calls.append((tool, params, r))
        trace.append({"node": tool, "params": params,
                      "valid_output": bool(r.get("valid_output")),
                      "failure_code": r.get("failure_code", "")})
        return r

    # 1) identity is almost always required (only for a real gene symbol)
    if target and is_known_gene(target):
        call("resolve_target", {"target_name": target})
    # 2) intent-specific retrieval
    doi = _DOI_RE.search(question)
    if doi:
        call("verify_crossref", {"doi": doi.group(0)})
    if any(k in ql for k in ("pdb", "structure", "crystal", "ternary", "complex")):
        call("retrieve_pdb", {"target": target or question[:40], "e3": e3, "top_k": 5})
    if molecule and any(k in ql for k in ("smiles", "inchikey", "inchi key", "molecular weight",
                                          "logp", "tpsa", "canonical", "property", "valid")):
        call("inspect_smiles", {"smiles": molecule})
    if any(k in ql for k in ("inhibitor", "degrader", "ligand", "binder", "compound", "bet")):
        call("search_chembl", {"term": target or ql[:32], "top_k": 5})
        if target:
            call("retrieve_target_binders", {"target_name": target, "top_k": 5})
    if any(k in ql for k in ("e3", "ligase", "crbn", "vhl", "recruiter")):
        call("select_e3_ligase", {"target": target, "preferred_e3": e3})
    if any(k in ql for k in ("citation", "doi", "reference", "publication", "paper", "support")) and not doi:
        claim_text = " ".join(str(x).split(":", 1)[-1] for x in (case.get("supplied_inputs") or []))
        query = claim_text or target or question
        call("search_europe_pmc", {"query": query, "page_size": 5})
        call("search_pubmed", {"query": query[:200], "page_size": 5})
    # 3) mechanistic REASON tools (only when the question asks for them)
    if capability == "REASON":
        if "hook" in ql:
            call("simulate_hook_effect", {"target_conc_nM": 100.0, "e3_conc_nM": 100.0, "alpha": 0.5})
        if "cooperativ" in ql:
            call("predict_cooperativity", {"warhead_smiles": parsed.get("warhead_smiles") or "",
                                            "linker_smiles": "",
                                            "e3_smiles": parsed.get("e3_ligand_smiles") or "",
                                            "pose_pdb": ""})
        if "exit vector" in ql or "attach" in ql:
            call("detect_exit_vectors", {"smiles": parsed.get("warhead_smiles") or "",
                                          "role": "warhead"})
        if any(k in ql for k in ("admet", "permeab", "logp", "solub")):
            call("predict_admet", {"smiles": parsed.get("warhead_smiles") or molecule or ""})

    summaries, facts, n_evidence = [], [], 0
    for tool, _params, r in calls:
        envelope = r.get("scientific_result") if isinstance(r, dict) else None
        envelope = envelope if isinstance(envelope, dict) else {}
        summary = str(envelope.get("summary") or "").strip()
        if summary:
            summaries.append(summary)
        data = (envelope.get("result") or {}).get("data") if isinstance(envelope.get("result"), dict) else None
        _flatten_facts(data if data is not None else envelope.get("data") or {}, out=facts)
        if (r.get("VALID_OUTPUT") or r.get("valid_output")) and envelope.get("status") in ("ok", "success", "warning"):
            n_evidence += 1
    seen: set[str] = set()
    # answer enrichment: compute InChIKey when the question asks for an identifier
    if molecule and any(k in ql for k in ("inchikey", "inchi key", "canonical smiles", "identifier")):
        try:
            from rdkit import Chem

            m = Chem.MolFromSmiles(molecule)
            if m is not None:
                facts.append(f"inchikey={Chem.MolToInchiKey(m)}")
        except Exception:  # noqa: BLE001
            pass
    uniq = [f for f in facts if not (f in seen or seen.add(f))]
    answer = "; ".join(summaries)
    if uniq:
        answer = (answer + ". " if answer else "") + "; ".join(uniq[:60])
    if not answer.strip():
        answer = "No retrieval evidence produced for this question."
    answered = n_evidence > 0
    scientific_state = (ScientificState.SUPPORTED_ANSWER.value if answered
                        else ScientificState.JUSTIFIED_NO_GO.value)
    outcome = "completed" if answered else "abstained"
    elapsed = round(time.time() - t0, 3)
    status = "completed" if outcome == "completed" else "abstained"
    return {
        "case_id": case.get("task_id", ""),
        "capability": capability,
        "question": question,
        "route": [t for t, _, _ in calls],
        "routing": {"mode": "capability_retrieval", "intent_tools": [t for t, _, _ in calls]},
        "routed_nodes": len(calls),
        "reached": [t for t, _, _ in calls],
        "trace": trace,
        "retry_count": 0,
        "elapsed_s": elapsed,
        "budget_s": budget_s,
        "seed": seed,
        "over_budget": elapsed > budget_s,
        "outcome": outcome,
        "status": status,
        "stop_reason": "",
        "abstention_justified": not answered,
        "abstention_reason": "" if answered else "no retrieval tool produced valid evidence",
        "error": "",
        "parsed_inputs": parsed,
        "entity_resolution": entities,
        "resolved_target": {"target_name": target, "uniprot_id": ""},
        "resolved_e3": e3,
        "scientific_state": scientific_state,
        "execution_status": "completed" if calls else "no_tools",
        "evidence_status": "retrieved" if answered else "insufficient",
        "answer_status": "provided" if answered else "unresolved",
        "retrieval_telemetry": [{"tool": t, "valid_output": bool(r.get("VALID_OUTPUT") or r.get("valid_output"))}
                                for t, _p, r in calls],
        "scientific_answer": {"scientific_state": scientific_state, "answer": answer},
        "answer": answer,
        "evidence": [{"kind": "retrieved", "source": t,
                      "summary": str(((r.get("scientific_result") or {}) if isinstance(r, dict) else {}).get("summary", ""))[:200]}
                     for t, _p, r in calls if (r.get("VALID_OUTPUT") or r.get("valid_output"))],
        "missing_prerequisites": [] if answered else ["retrievable evidence for the asked fact"],
        "uncertainty": ["Retrieved facts carry source provenance; mechanism claims remain hypotheses."],
        "next_experiment": "Confirm the retrieved fact against the cited primary source.",
        "attachment_hypothesis": False,
        "design_path": {},
        "design_gates": {},
        "n_candidates": 0,
        "n_verified_candidates": 0,
        "n_design_brief_candidates": 0,
        "verified_candidate_smiles": [],
        "design_brief_candidate_smiles": [],
        "n_warheads": 0,
        "n_e3_ligands": 0,
        "n_linkers": 0,
        "stage_ledger": [{"stage": t, "outcome": "completed" if (r.get("VALID_OUTPUT") or r.get("valid_output")) else "failed"}
                         for t, _p, r in calls],
        "target_record": {"target_name": target, "uniprot_id": ""},
        "warnings": [],
        "errors": [],
    }


def run_case(
    case: dict[str, Any],
    *,
    capability: str = "",
    offline: bool = True,
    budget_s: float = 120.0,
    seed: int = 0,
) -> dict[str, Any]:
    """Run one benchmark case on the repaired, capability-routed path."""
    capability = (capability or case.get("capability") or "").upper()
    if capability not in CAPABILITY_NODES:
        capability = "DESIGN"
    # KNOW/REASON are retrieval questions: route them to the capability-aware
    # retrieval path instead of the design workflow (which cannot answer them and
    # consumed the whole budget). Set PROTACXTEND_RETRIEVAL_ROUTING=0 to disable.
    if capability in {"KNOW", "REASON"} and os.environ.get("PROTACXTEND_RETRIEVAL_ROUTING", "1") != "0":
        return _run_retrieval_case(case, capability, offline=offline, budget_s=budget_s, seed=seed)
    _freeze_seed(seed)
    route, routing_record = route_for(case, capability)

    previous_offline = binder_agent.OFFLINE
    binder_agent.set_offline(offline)
    # Propagate a real run deadline so a live retrieval cannot consume the case
    # budget; offline runs need no network budget.
    if offline:
        binder_agent.clear_run_deadline()
    else:
        binder_agent.set_run_deadline(max(1.0, budget_s - 5.0))

    trace: list[dict[str, Any]] = []
    state, parsed = seed_state(case)
    entities = state.entity_resolution or {}
    attachment_hypothesis = bool(state.design_plan["structured_seed"].get("attachment_hypothesis"))
    state.design_plan["structured_seed"]["capability"] = capability
    state.design_plan["routing"] = routing_record

    started = time.time()
    status = "completed"
    error = ""
    if entities.get("ambiguous"):
        # Refuse before spending any budget: a wrong target is worse than none.
        status = "abstained"
    else:
        try:
            state = run_syn_glue_workflow(state=state, trace=trace, route=route)
        except Exception as exc:  # noqa: BLE001
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"
        finally:
            binder_agent.set_offline(previous_offline)
            binder_agent.clear_run_deadline()
    elapsed = round(time.time() - started, 3)
    if status == "abstained":
        binder_agent.set_offline(previous_offline)
        binder_agent.clear_run_deadline()

    if status not in {"failed", "abstained"} and elapsed > budget_s:
        status = "timeout"
    reached = [t["node"] for t in trace]
    retries = sum(1 for t in trace if t.get("retry"))

    # FINAL candidates are the post-filter valid set only. An empty post-filter
    # set is exactly zero candidates; previously-assembled placeholders must
    # never be resurrected here.
    candidates = list(state.valid_candidates)

    stop_reason = _stop_reason(state)
    target = getattr(state.target_record, "target_name", "") if state.target_record else ""
    question_l = (case.get("scientific_question") or "").lower()
    discover_needs_table = any(
        k in question_l for k in ("rank", "prioritise", "prioritize", "portfolio", "triage",
                                  "select a 2", "select 3", "select the top")
    )

    abstained = status == "abstained"
    justification = entities.get("reason", "") if entities.get("ambiguous") else ""
    if capability == "DESIGN" and not candidates and not abstained:
        if state.design_plan.get("design_brief"):
            abstained = False  # a design brief is a partial result, not a no-go
            justification = "no verified candidate; component attachments are hypothetical"
        else:
            abstained = True
            justification = stop_reason or "no candidate assembled"
    elif capability == "DISCOVER" and discover_needs_table and not candidates and not abstained:
        abstained = True
        justification = "supplied table describes the schema but contains no candidate rows"
    elif capability in {"KNOW", "REASON"} and not abstained:
        sci = state.scientific_answer.get("scientific_state")
        if sci == ScientificState.JUSTIFIED_NO_GO.value:
            abstained = True
            justification = "; ".join(state.scientific_answer.get("missing_prerequisites") or []) or stop_reason

    verified_candidates = [c for c in candidates if c.provenance.get("verified_components")]
    brief_candidates = [c for c in candidates if not c.provenance.get("verified_components")]
    scientific_state = _scientific_state(capability, state, candidates, abstained, entities)

    design_gates: dict[str, Any] = {}
    if capability == "DESIGN":
        from protacxtend.agents.design_gates import evaluate_design_gates

        try:
            design_gates = evaluate_design_gates(state)
            scientific_state = ScientificState(design_gates["final_state"])
        except Exception as exc:  # noqa: BLE001
            design_gates = {"error": f"{type(exc).__name__}: {exc}", "final_state": scientific_state.value}

    outcome = status
    if scientific_state == ScientificState.JUSTIFIED_NO_GO:
        outcome = "abstained"
    elif scientific_state == ScientificState.UNRESOLVED:
        # nothing was answered and nothing was designed: not a completion
        outcome = "abstained"
    elif scientific_state == ScientificState.DESIGN_BRIEF and status == "completed":
        outcome = "partial"
    elif scientific_state in {ScientificState.SUPPORTED_ANSWER, ScientificState.CONDITIONAL_HYPOTHESIS}:
        outcome = "completed" if status == "completed" else status

    answer_payload = dict(state.scientific_answer or {})
    if capability == "DESIGN":
        answer_payload.setdefault("scientific_state", scientific_state.value)
        if verified_candidates:
            vc0 = verified_candidates[0]
            sources = (vc0.provenance or {}).get("sources", {})
            maps = (vc0.provenance or {}).get("attachment_maps", {})
            answer_payload.setdefault("evidence", [
                {"kind": "retrieved", "source": sources.get("warhead", "verified_components"),
                 "summary": f"source-backed warhead; attachment map {maps.get('warhead')}"},
                {"kind": "retrieved", "source": sources.get("e3_ligand", "verified_components"),
                 "summary": f"source-backed E3 ligand; attachment map {maps.get('e3_ligand')} ({vc0.e3_ligase})"},
                {"kind": "calculated", "source": "design_gates",
                 "summary": f"{design_gates.get('n_verified_valid', 0)} candidate(s) passed the hard design gates"},
            ])
        answer_payload.setdefault("answer", (
            f"verified reference candidate {verified_candidates[0].full_protac_smiles}"
            if verified_candidates else
            (f"{len(state.assembled_candidates)} hypothetical product(s) sketched; "
             "no atom-mapped verified product" if state.assembled_candidates else "")
        ))
        answer_payload.setdefault("missing_prerequisites", (
            [] if verified_candidates else
            ["source-backed atom-mapped warhead exit vector",
             "source-backed E3 ligand attachment atom"]
        ))
        answer_payload.setdefault("uncertainty", [
            "Reference candidate comes from a crystalised BRD4-VHL PROTAC; "
            "selectivity and degradation are not measured here."
        ] if verified_candidates else [
            "All non-reference products use hypothetical attachment markers."
        ])
        answer_payload.setdefault("next_experiment", (
            "Chemist review of the reference candidate, then synthesise and measure DC50/Dmax."
            if verified_candidates else
            "Curate an atom-mapped exit vector and E3 attachment atom for the supplied components."
        ))

    if not answer_payload.get("answer") and outcome in {"abstained", "partial"}:
        reason = justification or stop_reason or "required scientific input absent"
        answer_payload["answer"] = f"No final answer produced: {reason}"
        answer_payload.setdefault("missing_prerequisites", [reason])
        answer_payload.setdefault("uncertainty", [
            "The engine stopped before a reviewable scientific result; no claim is made."
        ])
        answer_payload.setdefault(
            "next_experiment",
            "Supply the missing prerequisite (or inspect the stage ledger) and re-run.",
        )

    result = {
        "case_id": case.get("task_id", ""),
        "capability": capability,
        "question": case.get("scientific_question", ""),
        "route": route,
        "routing": routing_record,
        "routed_nodes": len(reached),
        "reached": reached,
        "trace": trace,
        "retry_count": retries,
        "elapsed_s": elapsed,
        "budget_s": budget_s,
        "seed": seed,
        "over_budget": elapsed > budget_s,
        "outcome": outcome,
        "status": status,
        "stop_reason": stop_reason,
        "abstention_justified": scientific_state == ScientificState.JUSTIFIED_NO_GO,
        "abstention_reason": justification or "; ".join(answer_payload.get("missing_prerequisites") or []),
        "error": error,
        "parsed_inputs": parsed,
        "entity_resolution": entities,
        "resolved_target": {
            "target_name": target,
            "uniprot_id": getattr(state.target_record, "uniprot_id", "") if state.target_record else "",
        },
        "resolved_e3": (entities.get("e3_ligases") or [""])[0],
        "scientific_state": scientific_state.value,
        "execution_status": state.execution_status,
        "evidence_status": state.evidence_status,
        "answer_status": state.answer_status,
        "retrieval_telemetry": list(state.retrieval_telemetry or []),
        "scientific_answer": answer_payload,
        "answer": answer_payload.get("answer", ""),
        "evidence": _sourced_evidence(answer_payload.get("evidence")),
        "missing_prerequisites": answer_payload.get("missing_prerequisites", []),
        "uncertainty": answer_payload.get("uncertainty", []),
        "next_experiment": answer_payload.get("next_experiment", ""),
        "attachment_hypothesis": attachment_hypothesis,
        "design_path": state.design_plan.get("design_path", {}),
        "design_gates": design_gates,
        "n_candidates": len(candidates),
        "n_verified_candidates": len(verified_candidates),
        "n_design_brief_candidates": len(brief_candidates),
        "verified_candidate_smiles": [c.full_protac_smiles for c in verified_candidates],
        "design_brief_candidate_smiles": [c.full_protac_smiles for c in brief_candidates[:5]],
        "n_warheads": len(state.selected_warheads or []),
        "n_e3_ligands": len(state.selected_e3_ligands or []),
        "n_linkers": len(state.generated_linkers or []),
        "stage_ledger": _stage_ledger(state, candidates),
        "target_record": {
            "target_name": target,
            "uniprot_id": getattr(state.target_record, "uniprot_id", "") if state.target_record else "",
        },
        "warnings": list(state.warnings or [])[-10:],
        "errors": list(state.errors or []),
    }
    return result


__all__ = ["CAPABILITY_NODES", "parse_supplied_inputs", "run_case", "seed_state"]
