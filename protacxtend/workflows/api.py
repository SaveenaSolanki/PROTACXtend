"""Per-command execution API: one distinct behaviour per command.

/plan        build a goal-typed task graph (no design execution)
/investigate retrieve target biology + degradation rationale into the evidence graph
/reason      competing mechanistic explanations + discriminating tests
/compare     descriptor/dimension comparison across molecules
/design      source-backed assembly (deterministic pipeline contract)
/optimize    series-driven change proposals with ternary-loss risk
/structure   score-level ternary feasibility (DockQ NOT_VALIDATED stated)
/selectivity E3 tissue/paralog evidence (expression never recommends)
/degradation trained-model predictions (predicted label enforced)
/admet       physicochemical risk flags (no PK)
/synthesis   retrosynthesis engine availability + honest routes
/experiment  discriminating assay selection with controls
/evidence    shared evidence graph query (incl. conflicts)
/run         execute the goal graph; replan on conflict/failure
"""

from __future__ import annotations

import os, time
from typing import Any, Optional

from protacxtend.evidence.graph import EvidenceGraph, make_claim
from protacxtend.request.controller import RequestController
from protacxtend.workflows.contracts import CONTRACTS, build_goal_plan, classify_goal
from protacxtend.workflows.reasoner import reason_about
from protacxtend.workflows.experimenter import design as design_tests


OUT_ROOT = "outputs/workflows"


def _graph_path(command: str, run_id: str) -> str:
    p = os.path.join(OUT_ROOT, command, f"{run_id}_evidence.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def _is_design(text: str) -> bool:
    import re as _re
    t = _re.sub(r"^(?:\\/)?(?:run|design)\\s+", "", (text or "").lower())
    return "design" in t or "protac" in t or "degrader" in t


def _design_run_id(text: str) -> str:
    import hashlib, re as _re
    key = _re.sub(r"^(?:\\/)?(?:run|design)\\s+", "", (text or "").lower())[:60]
    return "design_" + hashlib.sha1(key.encode()).hexdigest()[:10]




def run_command(command: str, text: str, *,
                offline: bool = True,
                series_path: str = "",
                smiles_arg: str = "",
                candidate_claims: Optional[dict] = None,
                resume_from: str = "") -> dict[str, Any]:
    """Execute one command contract; returns a structured payload."""
    t0 = time.time()
    u = RequestController(offline=offline).understand(text, default_action=command)
    run_id = f"{command}_{int(time.time())}"
    graph = EvidenceGraph()
    payload: dict[str, Any] = {
        "command": command, "run_id": run_id, "raw_request": text,
        "state": u.to_snapshot(),
        "scientific_question": CONTRACTS[command].scientific_question,
        "label": "workflow output — see contract; predictions are never measured",
    }

    # ------------------------------------------------------------- /design and /run design goal
    if command == "design" or (command == "run" and (_is_design(text) or resume_from)):
        # Target/intent routing: an UNRESOLVABLE target must ask for the exact
        # symbol BEFORE the engine runs (request-understanding rule: unknown ->
        # one exact-symbol question). A clarified-but-resolved target proceeds;
        # an unspecified E3 never blocks design (evaluated inside the engine).
        if (not resume_from) and u.clarification.pending and not (u.primary_target and u.primary_target.symbol \
                                            and u.primary_target.status in ("verified", "tentative", "resolved")):
            payload.update({"status": "clarification_needed",
                            "question": u.clarification.question,
                            "final": False})
            payload["evidence_graph"] = _graph_path(command, run_id)
            graph.to_json(payload["evidence_graph"])
            return payload
        # TargetTherapeuticsAssessment design gate (identity / chemistry /
        # therapeutic-window). Applies on fresh runs AND resume paths: a
        # blocked gate must not be bypassed by resuming a partially-run design.
        from protacxtend.agents.runtime import _target_spec_from_request
        from protacxtend.therapeutics.api import design_gate, TherapeuticallyUnsuitable
        spec = _target_spec_from_request(text or resume_from) or (u.primary_target and u.primary_target.symbol) or ""
        try:
            gate_out = design_gate(spec, allow_requires_review=True) if spec else None
        except TherapeuticallyUnsuitable as gate_err:
            payload.update({"status": "blocked", "gate": "therapeutics",
                            "error": str(gate_err), "final": True})
            payload["evidence_graph"] = _graph_path(command, run_id)
            graph.to_json(payload["evidence_graph"])
            return payload
        from protacxtend.workflows.designer import run_design
        payload.update(run_design(text, offline=offline, run_id=_design_run_id(text or resume_from),
                                  resume_from=resume_from))
        if gate_out:
            payload["therapeutic_assessment"] = gate_out
        payload["final"] = True
        return payload

    if u.clarification.pending and command not in ("plan", "reason", "experiment", "compare", "optimize",
                                                   "structure", "admet", "synthesis", "degradation"):
        # target-less commands (reason/experiment/compare/optimize) manage their
        # own input needs; only target-gated commands block on clarification.
        payload.update({"status": "clarification_needed", "question": u.clarification.question,
                        "final": False})
        payload["evidence_graph"] = _graph_path(command, run_id)
        graph.to_json(payload["evidence_graph"])
        return payload

    # ------------------------------------------------------------- /design
    # E3 preference is OPTIONAL: an explicit E3 is honored; an unspecified or
    # delegated E3 runs an evidence comparison over supported E3 options and
    # cell-context limitations — it never blocks a resolved target. The
    # deterministic design engine then executes source-backed assembly.
    if command == "design":
        from protacxtend.request.controller import _target_e3_precedent, _e3_library
        t = u.primary_target
        precedent = _target_e3_precedent(t.symbol) if t else None
        pairs = (precedent or {}).get("pairs") or {}
        families, _non_demo, _n_rows = _e3_library()

        if u.e3.mode == "explicit":
            e3_named = u.e3.named_e3
            e3_mode = "explicit"
            rows_n = (pairs.get(e3_named) or {}).get("n", 0)
            options = [{
                "e3": e3_named, "origin": "user_explicit", "precedent_rows": rows_n,
                "source": (precedent or {}).get("source", "") or "user choice",
            }]
            recommendation = (f"user-chosen E3 {e3_named} honored; "
                              f"{rows_n} measured degradation row(s) in the packaged context set"
                              if rows_n else f"user-chosen E3 {e3_named} honored; no measured "
                                             "degradation precedent in the packaged context set")
        else:
            e3_mode = "evaluate" if u.e3.mode == "unspecified" else "delegated"
            options = [{
                "e3": k, "origin": "measured_precedent", "precedent_rows": v["n"],
                "source": (precedent or {}).get("source", ""),
            } for k, v in sorted(pairs.items())]
            seen = {o["e3"] for o in options}
            for fam in sorted(families):
                if fam not in seen:
                    options.append({"e3": fam, "origin": "ligand_available",
                                    "precedent_rows": 0,
                                    "source": "curated_e3_ligands.csv (DOI-cited)"})
            if not pairs:
                recommendation = ("abstained — no measured per-E3 degradation precedent in the "
                                  "packaged context set; rank by ligand evidence + tissue context")
            else:
                recommendation = ("rank by measured degradation rows (%s); cell-context "
                                  "(expression) evidence may override — E3 to be evaluated"
                                  % ", ".join(sorted(pairs)))

        # execute the deterministic engine (E3 optional; never blocks)
        from protacxtend.workflows.designer import run_design as _run_design
        req_text = f"Design PROTACs for {t.symbol}"
        if u.e3.mode == "explicit":
            req_text += f" using {u.e3.named_e3}"
        if u.mutation:
            req_text += f" ({u.mutation})"
        design = _run_design(req_text, offline=offline)
        payload.update({
            **design,
            "raw_request": text,
            "e3_mode": e3_mode,
            "e3_preference_given": u.e3.mode == "explicit",
            "e3_options": options,
            "e3_recommendation": recommendation,
            "cell_context_limitations": (
                "no cell line/tissue supplied — E3 tissue-expression ranking deferred"
                if not u.cell_line else
                f"cell line {u.cell_line} — context-aware ranking possible via e3_context_engine"),
            "state": {
                "e3": {"mode": u.e3.mode, "named_e3": u.e3.named_e3 if u.e3.mode == "explicit" else ""},
                "target": t.symbol,
            },
            "gold_access": False,
            "note": ("E3 unspecified never blocks design; engine executed source-backed assembly "
                      "with its evidence-based E3 selection"),
        })
        payload["evidence_graph"] = _graph_path(command, run_id)
        graph.to_json(payload["evidence_graph"])
        return payload


    # ------------------------------------------------------------- /plan
    if command == "plan":
        from protacxtend.planning.contract import execute_plan_contract

        contract_payload = execute_plan_contract(
            text,
            conversation_id=f"workflow-{run_id}",
            offline=offline,
            emit_event=None,
            use_llm_planner=False,
        )
        payload.update(contract_payload)
        payload.setdefault("note", "plan only — no design path is executed to display a plan")
        return payload

    # ------------------------------------------------------------- /reason
    if command == "reason":
        smiles = smiles_arg or (u.supplied_ligands.get("warhead_smiles") or "")
        claims = candidate_claims or {"binding": {"statement": "strong binary binding (biochemical)",
                                                  "observed": True, "source_ids": ["user-measured"],
                                                  "assay": "SPR/ITC", "tool": "user-supplied"},
                                      "degradation": {"statement": "no cellular degradation observed",
                                                      "kind": "observed"}}
        hypotheses, g, summary = reason_about(
            smiles or "(no candidate SMILES)",
            binding_claim=claims.get("binding"), degradation_claim=claims.get("degradation"))
        tests, g = design_tests(hypotheses, graph=g)
        payload.update({
            "status": "ok", "final": True, "candidate": smiles or "(no candidate SMILES)",
            "hypotheses": [h.__dict__ for h in hypotheses],
            "tests": [t.__dict__ for t in tests],
            "summary": summary,
        })
        payload["evidence_graph"] = _graph_path(command, run_id)
        g.to_json(payload["evidence_graph"])
        return payload

    # ------------------------------------------------------------- /optimize
    if command == "optimize":
        from protacxtend.workflows.optimizer import load_series, propose, render
        src = series_path or _series_from_text(text)
        if not src:
            payload.update({"status": "needs_input", "final": False,
                            "question": "supply a series CSV path (series:path) with columns "
                                        "smiles,name,dc50_nM,dmax_pct,permeability"})
            payload["evidence_graph"] = _graph_path(command, run_id)
            graph.to_json(payload["evidence_graph"])
            return payload
        rows = load_series(src)
        props, opt_graph = propose(rows, graph=graph)
        payload.update({"status": "ok", "final": True,
                        "series": [r.__dict__ for r in rows],
                        "proposals": [p.__dict__ for p in props],
                        "rendered": render(rows, props)})
        payload["evidence_graph"] = _graph_path(command, run_id)
        opt_graph.to_json(payload["evidence_graph"])
        return payload

    # ------------------------------------------------------------- /experiment
    if command == "experiment":
        hypotheses = _hypotheses_from_text(text)
        tests, exp_graph = design_tests(hypotheses, graph=graph)
        payload.update({"status": "ok", "final": True,
                        "tests": [t.__dict__ for t in tests],
                        "note": "protocol only; nothing executed"})
        payload["evidence_graph"] = _graph_path(command, run_id)
        exp_graph.to_json(payload["evidence_graph"])
        return payload

    # ------------------------------------------------------------- /degradation
    if command == "degradation":
        smiles = smiles_arg or (u.supplied_ligands.get("warhead_smiles") or "")
        if not smiles:
            payload.update({"status": "needs_input", "final": False,
                            "question": "supply a candidate SMILES (smiles:...) or request with warhead_smiles"})
            return payload
        from protacxtend.tools.degradation_endpoint import predict_degradation_endpoint
        try:
            raw = predict_degradation_endpoint(smiles)
            out = raw.model_dump() if hasattr(raw, "model_dump") else (raw if isinstance(raw, dict) else {"raw": str(raw)[:200]})
        except Exception as exc:  # noqa: BLE001
            payload.update({"status": "tool_failed", "final": False, "error": str(exc)})
            return payload
        graph.add(make_claim(command="degradation", dimension="degradation", kind="computed",
                             statement="trained-model degradation prediction",
                             value=out.get("dc50_nM") if isinstance(out, dict) else None,
                             unit="nM", tool="degradation_endpoint",
                             version=str((out or {}).get("model_version", "")),
                             params={"smiles": smiles[:40]}, artifact=payload.get("evidence_graph", "")))
        payload.update({"status": "ok", "final": True, "smiles": smiles,
                        "prediction": out if isinstance(out, dict) else {"raw": str(out)[:200]},
                        "label": "computational prediction; not measured"})
        payload["evidence_graph"] = _graph_path(command, run_id)
        graph.to_json(payload["evidence_graph"])
        return payload

    # ------------------------------------------------------------- /admet
    if command == "admet":
        smiles = smiles_arg or (u.supplied_ligands.get("warhead_smiles") or "")
        if not smiles:
            payload.update({"status": "needs_input", "final": False, "question": "supply a SMILES"})
            return payload
        from protacxtend.tools.admet_predictors import predict_admet
        try:
            out = predict_admet(smiles)
        except Exception as exc:  # noqa: BLE001
            payload.update({"status": "tool_failed", "final": False, "error": str(exc)})
            return payload
        payload.update({"status": "ok", "final": True, "smiles": smiles,
                        "flags": out if isinstance(out, dict) else {"raw": str(out)[:200]},
                        "scope": "physicochemical risk flags only; no PK model"})
        return payload

    # ------------------------------------------------------------- /structure
    if command == "structure":
        smiles = smiles_arg or (u.supplied_ligands.get("warhead_smiles") or "")
        note = "score-level ternary feasibility only; predicted-structure DockQ NOT_VALIDATED; no coordinates emitted"
        if not smiles:
            payload.update({"status": "needs_input", "final": False,
                            "question": "supply a candidate SMILES to run score-level ternary feasibility", "note": note})
            return payload
        try:
            from protacxtend.tools.ternary_engine import ternary_feasibility
            out = ternary_feasibility(smiles)
        except Exception as exc:  # noqa: BLE001
            payload.update({"status": "tool_failed", "final": False, "error": str(exc), "note": note})
            return payload
        payload.update({"status": "ok", "final": True, "smiles": smiles,
                        "ternary_scores": out if isinstance(out, dict) else {"raw": str(out)[:200]},
                        "note": note})
        return payload

    # ------------------------------------------------------------- /synthesis
    if command == "synthesis":
        from protacxtend.tools.retrosynthesis_engines import render_engine_status_report
        status = render_engine_status_report(skip_network=offline)
        payload.update({"status": "ok", "final": True,
                        "engines": status if isinstance(status, (list, dict)) else {"raw": str(status)[:400]},
                        "note": "route proposals are computational; none are tested routes"})
        return payload

    # ------------------------------------------------------------- /evidence
    if command == "evidence":
        from protacxtend.workflows.api_helpers import load_latest_graphs
        claims = load_latest_graphs()
        payload.update({"status": "ok", "final": True, "claims": claims[:200],
                        "n_claims": len(claims),
                        "note": "shared evidence graph snapshot (per-command files under outputs/workflows/)"})
        return payload

    # ------------------------------------------------------------- /selectivity
    if command == "selectivity":
        import csv
        e3_rows = []
        e3_path = "protacxtend/data/curated_e3_ligands.csv"
        if os.path.exists(e3_path):
            with open(e3_path, newline="") as f:
                for r in csv.DictReader(f):
                    if "demo" not in (r.get("source") or ""):
                        e3_rows.append(r.get("e3_ligase"))
        payload.update({"status": "ok", "final": True,
                        "e3_families_with_cited_ligands": sorted(set(e3_rows)),
                        "note": "expression-only never recommends an E3; selectivity claims require measured evidence"})
        return payload

    # ------------------------------------------------------------- /compare
    if command == "compare":
        smiles_list = _smiles_list_from_text(text)
        if len(smiles_list) < 2:
            payload.update({"status": "needs_input", "final": False,
                            "question": "supply >=2 candidate SMILES to compare (e.g. 'compare smiles:A smiles:B')"})
            return payload
        from protacxtend.workflows.api_helpers import compare_molecules
        cmp = compare_molecules(smiles_list, graph=graph)
        payload.update({"status": "ok", "final": True, "comparison": cmp})
        payload["evidence_graph"] = _graph_path(command, run_id)
        graph.to_json(payload["evidence_graph"])
        return payload

    # ------------------------------------------------------------- /investigate
    if command == "investigate":
        from protacxtend.request.controller import _target_e3_precedent, _curated_record, _e3_library
        t = u.primary_target
        curated = _curated_record(t.symbol) if t else None
        precedent = _target_e3_precedent(t.symbol) if t else None
        families, non_demo, n_rows = _e3_library() if False else ({}, 0, 0)
        target_supported = bool(t and t.symbol and t.uniprot_id and t.status in ("verified", "tentative", "resolved"))
        findings = {
            "target": t.symbol if t else None,
            "uniprot": t.uniprot_id if t else None,
            "target_resolution": t.__dict__ if t else None,
            "interpretation": (
                f"{t.symbol} is a resolved target identity ({t.uniprot_id}); investigation is evidence-bounded "
                "and reports missing binder/degradation evidence rather than inventing it."
                if target_supported else "target identity unresolved; no scientific investigation result is supported"
            ),
            "known_binder_count": curated.get("known_binder_count") if curated else None,
            "measured_precedent_rows": precedent["total"] if precedent else 0,
            "e3_precedent": {k: v["n"] for k, v in precedent["pairs"].items()} if precedent else {},
            "e3_family_cited_rows": _e3_family_census(),
            "missing": [],
            "evidence_gaps": [],
        }
        if not curated or not curated.get("known_binder_count") or str(curated.get("known_binder_count")).strip() in ("", "0"):
            findings["missing"].append("source-backed binder/warhead records with attachment vectors")
            findings["evidence_gaps"].append({"field": "binder_evidence", "status": "missing",
                                               "needed": "DOI/source-backed binder rows with SMILES, potency, and exit vector"})
        if not precedent or not precedent["total"]:
            findings["missing"].append("measured degradation precedent for this target")
            findings["evidence_gaps"].append({"field": "degradation_precedent", "status": "missing",
                                               "needed": "measured target-loss rows for the target/E3/cell context"})
            payload["status"] = "plan_with_limitation"
        tl = []
        if t:
            tl.append(make_claim(command="investigate", dimension="target_engagement", kind="computed",
                                 statement=f"known binder census for {t.symbol}",
                                 value=float(curated["known_binder_count"]) if curated and curated.get("known_binder_count") else None,
                                 unit="count", tool="curated_targets.csv"))
            if precedent and precedent["total"]:
                tl.append(make_claim(command="investigate", dimension="degradation", kind="observed",
                                     statement=f"{precedent['total']} measured degradation rows for {t.symbol}",
                                     value=float(precedent["total"]), unit="rows",
                                     tool="context_joined.csv", source_ids=precedent.get("source_ids", []),
                                     assay="HiBiT/western (per row DOI)"))
        for c in tl:
            try:
                graph.add(c)
            except ValueError:
                graph.add(make_claim(command=c.command, dimension=c.dimension, kind="computed",
                                     statement=c.statement, value=c.value, unit=c.unit, tool=c.provenance.get("tool", "")))
        status = payload.get("status") or "ok"
        supported = bool(target_supported and findings.get("interpretation") and "evidence_gaps" in findings)
        payload.update({"status": status, "final": True, "findings": findings,
                        "request_completed": True, "plan_generated": False,
                        "scientific_answer_supported": supported})
        payload["evidence_graph"] = _graph_path(command, run_id)
        graph.to_json(payload["evidence_graph"])
        return payload

    # ------------------------------------------------------------- /run
    if command == "run":
        from protacxtend.workflows.executor import execute_plan
        # interpret the underlying goal (design -> design graph), not the /run wrapper
        if smiles_arg:
            u.supplied_ligands["warhead_smiles"] = smiles_arg
        import re as _re
        goal_text = _re.sub(r"^(?:\/)?run\s+", "", text).strip() or "design"
        u2 = RequestController(offline=offline).understand(goal_text, default_action="design")
        if smiles_arg:
            u2.supplied_ligands["warhead_smiles"] = smiles_arg
        plan = build_goal_plan(u2)
        trace = execute_plan(u2, plan, run_id=run_id,
                             out_dir=os.path.join(OUT_ROOT, "run"))
        trace.evidence_graph.to_json(os.path.join(OUT_ROOT, "run", f"{run_id}_evidence.json"))
        payload.update({
            "status": trace.status, "final": True,
            "stages": [s.__dict__ for s in trace.stages],
            "replans": trace.replans,
            "evidence_graph": os.path.join(OUT_ROOT, "run", f"{run_id}_evidence.json"),
            "signature": plan.signature,
        })
        return payload

    payload.update({"status": "unsupported", "final": False})
    return payload


def _series_from_text(text: str) -> str:
    import re
    m = re.search(r"series:\s*([^\s]+)", text)
    return m.group(1).strip() if m else ""


def _smiles_list_from_text(text: str) -> list[str]:
    import re
    return re.findall(r"smiles:(\S+)", text)


def _hypotheses_from_text(text: str) -> list[Any]:
    """Accept 'H1,H2,...' or reuse the full reasoner bank."""
    import re
    ids = re.findall(r"H(\d)", text)
    if ids:
        from protacxtend.workflows.reasoner import HYPOTHESIS_BANK
        out = []
        for i in ids:
            idx = int(i) - 1
            if 0 <= idx < len(HYPOTHESIS_BANK):
                h = HYPOTHESIS_BANK[idx]
                out.append(type("H", (), {"axis": h["axis"], "hypothesis_id": f"H{idx+1}",
                                          "discriminating_tests": h["tests"],
                                          "expected_if_true": h["expected"]})())
        return out
    from protacxtend.workflows.reasoner import HYPOTHESIS_BANK
    return [type("H", (), {"axis": h["axis"], "hypothesis_id": f"H{i+1}",
                           "discriminating_tests": h["tests"],
                           "expected_if_true": h["expected"]})()
            for i, h in enumerate(HYPOTHESIS_BANK)]


def _e3_family_census() -> dict[str, int]:
    import csv
    path = "protacxtend/data/curated_e3_ligands.csv"
    if not os.path.exists(path):
        return {}
    counts: dict[str, int] = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            if "demo" not in (r.get("source") or ""):
                fam = (r.get("e3_ligase") or "").strip()
                if fam:
                    counts[fam] = counts.get(fam, 0) + 1
    return counts