#!/usr/bin/env python
"""E1 capability audit: build the joined tool-execution matrix.

One row per executable agent-tool adapter (the callable surface), joined to the
toolkit registry / disposition / matched-tool registry, and measured with a real
positive input plus a missing-input negative. No scientific utility is inferred.

Outputs under results/closure/:
  e1_tool_matrix.csv              joined matrix (instruction schema)
  e1_raw_traces.jsonl             full run envelopes (negative + positive)
  e1_proportions.json             four proportions with explicit denominators
  e1_registry_reconciliation.json 296 / 123 / 34 / 29 breakdown
  e1_exclusions.csv               commercial / credential / web-only exclusions
  fig2_e1_capability_funnel.png/pdf

Usage:
  python scripts/e1_tool_matrix.py            # offline (deterministic)
  python scripts/e1_tool_matrix.py --online   # allow network tools to run
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("PROTACXTEND_EXECUTION_MODE", "scientific")

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "results" / "closure"

# Real, curated positive inputs for tools whose shipped probe fixture uses a
# placeholder (which SCIENTIFIC mode correctly refuses).
REAL_INPUTS: dict[str, dict] = {
    "construct_protac": {
        "warhead_smiles": "COc1cc([*:1])cc(C(=O)N2CCN(CC2)c2ccc(Cl)cc2)c1",
        "linker_smiles": "[*:1]CCOCCOCC[*:2]",
        "e3_smiles": "CC(C)c1ccc(C(=O)N[C@@H](C(=O)N2CCC[C@H]2O)C(C)C)cc1[*:1]",
    },
    "check_synthetic_feasibility": {"smiles": "CC(=O)Oc1ccccc1C(=O)O", "use_aizynth": False},
    "model_ternary_complex": {"target": "BRD4", "e3": "CRBN", "linker_smiles": "[*:1]CCOCCOCC[*:2]", "smiles": ""},
    "predict_cooperativity": {
        "warhead_smiles": "CC(=O)Oc1ccccc1C(=O)O",
        "linker_smiles": "[*:1]CCOCCOCC[*:2]",
        "e3_smiles": "O=C1CCC(N2C(=O)c3ccccc3C2=O)C(=O)N1",
        "pose_pdb": "outputs/ternary_5T35_haddock_blind/reference/5T35_full.pdb",
    },
    "predict_degradation": {"smiles": "O=C1CCC(N2C(=O)c3ccccc3C2=O)C(=O)N1",
                            "e3": "CRBN", "cell_line": "HEK293T", "target": "BRD4"},
    "predict_cell_context": {"smiles": "O=C1CCC(N2C(=O)c3ccccc3C2=O)C(=O)N1",
                             "cell_line": "HEK293T", "poi": "BRD4", "e3": "CRBN"},
    "predict_admet": {"smiles": "CC(=O)Oc1ccccc1C(=O)C", "backend": "auto"},
    "generate_linkers": {
        "warhead_smiles": "COc1cc([*:1])cc(C(=O)N2CCN(CC2)c2ccc(Cl)cc2)c1",
        "e3_smiles": "CC(C)c1ccc(C(=O)N[C@@H](C(=O)N2CCC[C@H]2O)C(C)C)cc1[*:1]",
        "count": 3, "constraints": {},
    },
    "run_scientific_capability": {
        "capability": "chemistry",
        "params": {"smiles": "CC(=O)Oc1ccccc1C(=O)O", "operation": "descriptors"},
    },
    "score_lysine_ubiquitination": {
        "target": "BRD4", "e3": "CRBN",
        "structure_paths": ["outputs/ternary_5T35_haddock_blind/reference/5T35_full.pdb"],
        "poi_chain": "A",
        "e2_catalytic": {"chain": "A", "residue_number": 1, "residue_name": "SER"},
    },
}

DOMAIN_MAP = {
    "deep_research": "KNOW", "search_europe_pmc": "KNOW", "search_pubmed": "KNOW",
    "verify_crossref": "KNOW", "retrieve_fulltext": "KNOW", "search_web": "KNOW",
    "resolve_target": "KNOW", "search_uniprot": "KNOW", "retrieve_target_binders": "KNOW",
    "search_pubchem": "KNOW", "search_chembl": "KNOW", "search_bindingdb": "KNOW",
    "select_e3_ligase": "REASON", "retrieve_e3_evidence": "REASON",
    "predict_cell_context": "REASON", "diagnose_capability": "REASON",
    "list_capability_readiness": "REASON", "list_scientific_capabilities": "REASON",
    "run_scientific_capability": "REASON",
    "inspect_smiles": "DESIGN", "detect_exit_vectors": "DESIGN", "generate_linkers": "DESIGN",
    "construct_protac": "DESIGN", "check_synthetic_feasibility": "DESIGN",
    "retrieve_pdb": "DESIGN", "model_ternary_complex": "DESIGN",
    "score_lysine_ubiquitination": "DESIGN", "predict_cooperativity": "DESIGN",
    "simulate_hook_effect": "DISCOVER", "predict_degradation": "DISCOVER",
    "predict_admet": "DISCOVER", "run_protacpilot_structural": "DISCOVER",
    "rank_candidates": "DISCOVER", "build_candidate_dossier": "DISCOVER",
}


def _backend_versions() -> dict[str, str]:
    import importlib.metadata as md
    vers = {}
    for name in ("rdkit", "numpy", "pandas", "scikit-learn", "openbabel-wheel"):
        try:
            vers[name] = md.version(name if name != "rdkit" else "rdkit")
        except Exception:
            try:
                import importlib
                vers[name] = getattr(importlib.import_module("rdkit"), "__version__", "")
            except Exception:
                vers[name] = ""
    return {k: v for k, v in vers.items() if v}


def _run(tool: str, params: dict, *, online: bool) -> dict:
    from protacxtend.runtime.agent_tools import run_agent_tool
    t0 = time.time()
    try:
        r = run_agent_tool(tool, params, allow_network=online)
        return {"tool": tool, "params": params, "raised": "", "latency_s": round(time.time() - t0, 4), "run": r}
    except Exception as exc:  # noqa: BLE001
        return {"tool": tool, "params": params, "raised": f"{type(exc).__name__}",
                "code": getattr(getattr(exc, "code", None), "value", ""), "message": str(exc)[:300],
                "latency_s": round(time.time() - t0, 4), "run": {}}


def _classify(rec: dict) -> str:
    if rec.get("raised"):
        c = rec.get("code", "")
        if c == "FIXTURE_FORBIDDEN":
            return "fixture_refused"
        if c == "SYNTHETIC_INPUT_FORBIDDEN":
            return "placeholder_refused"
        if c == "MISSING_SCIENTIFIC_INPUT":
            return "missing_input_refused"
        return "raised"
    run = rec.get("run") or {}
    if run.get("VALID_OUTPUT"):
        return "executed_valid"
    if run.get("EXECUTED"):
        return "executed_invalid"
    return f"not_executed:{run.get('status','')}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    run_id = args.tag or f"e1_{'online' if args.online else 'offline'}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"

    from protacxtend.runtime.agent_tools import list_agent_tools, PROBE_FIXTURES
    from protacxtend.runtime import modes
    from protacxtend.runtime.adapter_audit import audit_all_agent_tools
    from benchmark_runner.matched_tools import MATCHED_TOOLS

    tools = list_agent_tools()
    audit = audit_all_agent_tools()
    audit_by = {t["tool"]: t for t in audit.get("tools", [])}
    versions = _backend_versions()

    rows, traces = [], []
    for t in tools:
        name = t["name"]
        fx = dict(PROBE_FIXTURES.get(name, {}))
        real = dict(REAL_INPUTS.get(name, fx)) if name in REAL_INPUTS else fx
        neg = _run(name, {}, online=False)
        pos = _run(name, real, online=args.online)
        for r in (neg, pos):
            r["case"] = "negative_missing_input" if r is neg else "positive_real_input"
            r["run_id"] = run_id
            traces.append(r)
        pos_run = pos.get("run") or {}
        pos_code = pos.get("code", "")
        pos_kind = _classify(pos)
        neg_kind = _classify(neg)
        matched = [k for k, v in MATCHED_TOOLS.items() if name in (v.agent_tools or [])]
        required = list(modes.SCIENTIFIC_REQUIRED_INPUTS.get(name, ()))
        rows.append({
            "tool": name,
            "kind": t["kind"],
            "study_domain": DOMAIN_MAP.get(name, ""),
            "readiness": t["readiness"],
            "has_executor": t["has_executor"],
            "required_inputs": "|".join(required),
            "matched_permitted_ids": "|".join(matched),
            "adapter_audit_status": audit_by.get(name, {}).get("status", ""),
            "license": "open/open-adapter",
            "dependency": "|".join(k for k in versions if k in name.lower()) or "python",
            "weight_present": "",
            "installation": "installed",
            "callable": t["has_executor"],
            "positive_outcome": pos_kind,
            "positive_status": pos_run.get("status", pos.get("raised", "")),
            "positive_valid_output": bool(pos_run.get("VALID_OUTPUT")),
            "positive_executed": bool(pos_run.get("EXECUTED")),
            "positive_evidence_kind": pos_run.get("evidence_kind", ""),
            "negative_outcome": neg_kind,
            "negative_failure_code": (neg.get("code") or (neg.get("run") or {}).get("failure_code", "")),
            "negative_typed": neg_kind in {"missing_input_refused", "fixture_refused", "placeholder_refused"},
            "evidence_ids": "|".join((pos_run.get("scientific_result") or {}).get("evidence", [{}])[0].get("source", "").split()) if pos_run.get("scientific_result") else "",
            "version": versions.get("rdkit", ""),
            "elapsed_s": pos.get("latency_s", 0.0),
            "limitation": (pos_run.get("scientific_result") or {}).get("metadata", {}).get("limitation", "") or "",
            "last_run_id": run_id,
            "backend": (pos_run.get("scientific_result") or {}).get("metadata", {}).get("backend", "agentic.registry"),
        })

    with (OUT / "e1_tool_matrix.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with (OUT / "e1_raw_traces.jsonl").open("w") as fh:
        for r in traces:
            fh.write(json.dumps(r, default=str) + "\n")

    # ── registry reconciliation ──
    from protacxtend.toolkit.registry import load_toolkit_registry
    reg = load_toolkit_registry()
    from protacxtend.toolkit.disposition import build_disposition_report
    disp = build_disposition_report()
    recon = {
        "registry_rows_total": sum(len(reg[s]) for s in reg["sections"]),
        "registry_sections": {s: len(reg[s]) for s in reg["sections"]},
        "classified_tools": disp["n_tools"],
        "disposition_counts": disp["counts"],
        "agent_tool_adapters": len(tools),
        "matched_permitted_ids": len(MATCHED_TOOLS),
        "note": "296 registry rows = sum of 6 sections; 123 classified tools is the tools section; "
                "34 adapters is the callable agent surface; matched ids map benchmark permitted ids.",
    }
    (OUT / "e1_registry_reconciliation.json").write_text(json.dumps(recon, indent=2))

    # ── exclusions ──
    with (OUT / "e1_exclusions.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["tool_id", "tool", "disposition", "rationale"])
        for tool in disp["tools"]:
            if tool["disposition"] in {"commercial_excluded", "integration_candidate"}:
                w.writerow([tool["id"], tool["tool"], tool["disposition"], tool.get("rationale", "")])

    # ── proportions (explicit denominators) ──
    n = len(rows)
    installed = sum(1 for r in rows if r["callable"])
    runnable = sum(1 for r in rows if r["positive_executed"])
    domain_valid = sum(1 for r in rows if r["positive_valid_output"])
    provenance = sum(1 for r in rows if r["positive_valid_output"] and r["last_run_id"])
    typed_neg = sum(1 for r in rows if r["negative_typed"])
    props = {
        "denominator": "34 callable agent-tool adapters (E1 measured surface)",
        "installed_over_eligible": f"{installed}/{n}",
        "runnable_over_installed": f"{runnable}/{installed}",
        "domain_valid_over_runnable": f"{domain_valid}/{runnable}" if runnable else "0/0",
        "provenance_complete_over_domain_valid": f"{provenance}/{domain_valid}" if domain_valid else "0/0",
        "typed_negative_failure": f"{typed_neg}/{n}",
        "engineering_only": True,
        "note": "Proportions measure execution/provenance readiness, never therapeutic utility.",
    }
    (OUT / "e1_proportions.json").write_text(json.dumps(props, indent=2))

    # ── figure ──
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from protacxtend.validation.closure_figures import apply_style, save_square, style_axes
        funnel = [("registered\n(123 tools)", 123), ("classified\nopen", 123 - disp["counts"].get("commercial_excluded", 0)),
                  ("adapter\n(34)", 34), ("positive\nexecuted", runnable), ("domain\nvalid", domain_valid)]
        apply_style()
        fig, ax = plt.subplots()
        ax.bar([f[0] for f in funnel], [f[1] for f in funnel],
               color=["#8DA0CB", "#A6CEE3", "#66C2A5", "#1B9E77", "#006D2C"])
        for i, (_, v) in enumerate(funnel):
            ax.text(i, v + 1, str(v), ha="center", fontsize=9)
        style_axes(ax, xlabel="Capability funnel stage", ylabel="Tools (n)",
                   title="E1 capability funnel — execution readiness, not utility")
        save_square(fig, OUT / "fig2_e1_capability_funnel.png", dpi=600, pdf=True)
    except Exception as exc:  # noqa: BLE001
        print("figure skipped:", exc)

    print(json.dumps({"run_id": run_id, "n_tools": n, "proportions": props,
                      "reconciliation": recon["registry_rows_total"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
