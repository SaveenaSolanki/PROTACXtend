"""Module 1 quickstart — Hook Effect Modeler demo.

Usage:  python -m synglue_agent.modules.hook_effect_modeler.examples.quickstart
"""

from __future__ import annotations

from synglue_agent.modules.hook_effect_modeler import simulate_hook_effect
from synglue_agent.tools.hook_effect_modeler_tool import run_hook_effect_modeler


def main() -> None:
    # Balanced stoichiometry, strong cooperativity -> pronounced hook
    r = simulate_hook_effect(poI_conc_nM=100.0, e3_conc_nM=100.0,
                             kd_poi_protac_nM=50.0, kd_e3_protac_nM=50.0,
                             alpha=30.0, max_dose_nM=10_000.0,
                             uncertainty_pct={"kd": 15.0, "alpha": 20.0})
    m = r.metrics
    u = r.uncertainty
    print("Hook Effect Modeler demo (alpha=30, balanced T/E, Kds=50 nM)")
    print("  DETERMINISTIC (nominal parameters, sub-grid refined):")
    print("    Cmax (PROTAC dose at peak), nM   :", m.cmax_nM)
    print("    ternary max (nM at Cmax)         :", m.ternary_max_nM)
    print("    max occupancy fraction           :", m.max_occupancy_fraction)
    print("    hook-90 nM (<=90% on desc limb)  :", m.hook_90_nM)
    print("    hook-50 nM (<=50% on desc limb)  :", m.hook_50_nM)
    print("    hook/Cmax ratio (cmax/hook50)    :", m.hook_cmax_ratio)
    print("    hook severity (0..1, tested win.) :", m.hook_severity, f"({m.hook_label})")
    print("    severity reference (max dose nM) :", m.severity_reference_max_dose_nM)
    print("    occupancy window (fold)          :", m.occupancy_window_fold)
    print("  MONTE-CARLO (Kds/alpha lognormal, median = nominal):")
    print("    Cmax p5/med/p95 (nM)             :", u.optimal_concentration_nM)
    print("    ternary max p5/med/p95 (nM)      :", u.peak_ternary_nM)
    print("    hook severity p95                :", u.hook_severity_p95)
    print(f"    Cmax within +-25% of nominal ({u.reference_optimum_nM or m.cmax_nM:g} nM): "
          f"{u.fraction_within_25pct:.1%}")
    print("  warnings                                    :", r.warnings)
    print("  sample curve rows:")
    for p in r.curve[:: max(1, len(r.curve) // 5)]:
        print(f"    dose={p.dose_nM:>10.3f} ternary={p.ternary_nM:>10.4f} "
              f"occupancy={p.occupancy_fraction:.4f}")

    # Agent-tool path (JSON in/out)
    tool = run_hook_effect_modeler({"alpha": 5.0, "points": 60})
    print("\nAgent tool call success:", tool["success"],
          "| error:", tool["error"] or "none",
          "| hook label:", tool["result"]["metrics"]["hook_label"])


if __name__ == "__main__":
    main()
