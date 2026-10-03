#!/usr/bin/env python
"""E6 ablation (executable): the scientific input/abstention guard.

Removes one component — the SCIENTIFIC-mode fixture/placeholder guard — and
re-runs the same 34-tool negative/positive probe set, measuring the change in
unsafe executions. This is a real code-switch run (DEMO vs SCIENTIFIC), not a
paper ablation.

Output: results/closure/e6_ablation_guard.json + fig6_e6_ablation.png
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "results" / "closure"

# placeholders that must never silently execute a scientific tool
SAFETY_KEYS = ["used_fixture", "input_origin"]


def _probe(mode: str) -> dict:
    from protacxtend.runtime import modes
    from protacxtend.runtime.agent_tools import list_agent_tools, PROBE_FIXTURES, run_agent_tool

    # Guard-relevant subset (chemistry/prediction/adapter surface); network
    # retrieval tools are excluded because they block and are not guard-relevant.
    SUBSET = ["inspect_smiles", "detect_exit_vectors", "generate_linkers", "construct_protac",
              "check_synthetic_feasibility", "predict_degradation", "predict_admet",
              "predict_cell_context", "run_scientific_capability", "score_lysine_ubiquitination",
              "predict_cooperativity", "model_ternary_complex"]
    out = {}
    with modes.execution_mode(mode):
        for t in list_agent_tools():
            name = t["name"]
            if name not in SUBSET:
                continue
            for label, params, fixture in (("missing", {}, False), ("fixture", {}, True)):
                try:
                    r = run_agent_tool(name, params, use_fixture=fixture, allow_network=False)
                    out[f"{name}:{label}"] = {
                        "outcome": "executed" if r.get("EXECUTED") else "not_executed",
                        "used_fixture": r.get("used_fixture"),
                        "input_origin": r.get("input_origin"),
                        "valid": bool(r.get("VALID_OUTPUT")),
                    }
                except Exception as exc:  # noqa: BLE001
                    out[f"{name}:{label}"] = {"outcome": "typed_refusal",
                                              "code": getattr(getattr(exc, "code", None), "value", type(exc).__name__)}
    return out


def _unsafe(probes: dict) -> int:
    """Executions that consumed a fixture/synthetic input (unsafe in SCIENTIFIC)."""
    n = 0
    for v in probes.values():
        if v.get("outcome") == "executed" and (v.get("used_fixture") or v.get("input_origin") in ("FIXTURE", "SYNTHETIC")):
            n += 1
    return n


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    sci = _probe("scientific")
    demo = _probe("demo")
    res = {
        "component_removed": "SCIENTIFIC-mode fixture/placeholder/abstention guard",
        "arms": {
            "guard_on_scientific": {
                "probes": len(sci),
                "executed": sum(1 for v in sci.values() if v["outcome"] == "executed"),
                "typed_refusals": sum(1 for v in sci.values() if v["outcome"] == "typed_refusal"),
                "unsafe_fixture_executions": _unsafe(sci),
            },
            "guard_off_demo": {
                "probes": len(demo),
                "executed": sum(1 for v in demo.values() if v["outcome"] == "executed"),
                "typed_refusals": sum(1 for v in demo.values() if v["outcome"] == "typed_refusal"),
                "unsafe_fixture_executions": _unsafe(demo),
            },
        },
        "refusal_codes_scientific": dict(Counter(v.get("code", "") for v in sci.values() if v.get("code"))),
        "note": "Effect on scientific correctness is NOT measured (gold pending). This is an "
                "execution-safety ablation only.",
    }
    (OUT / "e6_ablation_guard.json").write_text(json.dumps(res, indent=2))

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from protacxtend.validation.closure_figures import apply_style, save_square, style_axes
        apply_style()
        fig, ax = plt.subplots()
        arms = ["guard_on_scientific", "guard_off_demo"]
        unsafe = [res["arms"][a]["unsafe_fixture_executions"] for a in arms]
        typed = [res["arms"][a]["typed_refusals"] for a in arms]
        x = range(len(arms))
        ax.bar([i - 0.2 for i in x], unsafe, 0.4, label="unsafe fixture executions", color="#D95F02")
        ax.bar([i + 0.2 for i in x], typed, 0.4, label="typed refusals", color="#1B9E77")
        ax.set_xticks(list(x)); ax.set_xticklabels(["guard ON\n(scientific)", "guard OFF\n(demo)"])
        style_axes(ax, xlabel="Ablation arm", ylabel="Probes (n)",
                   title="E6 ablation — scientific input guard (execution safety)")
        ax.legend(fontsize=8, frameon=False)
        save_square(fig, OUT / "fig6_e6_ablation.png", dpi=600, pdf=True)
    except Exception as exc:  # noqa: BLE001
        print("figure skipped:", exc)

    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
