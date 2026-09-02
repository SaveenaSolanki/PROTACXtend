# Architecture — Hook Effect Modeler

```
configs/hook_effect_modeler.json  →  ModelerConfig (env-overridable path)
schemas.py                        →  HookEffectInput / CurvePoint / HookMetrics /
                                     UncertaintySummary / HookEffectResult (pydantic,
                                     versioned model id hook_effect_modeler-v1.0.0)
core.py                           →  _solve_one()  bounded least-squares (log10-space,
                                     relative mass-balance residuals, positivity bounds)
                                     solve_ternary()  single-dose wrapper (public)
                                     simulate_hook_effect()  full dose sweep + metrics
                                     _compute_metrics()  peak/onset/severity/window
                                     _monte_carlo_uncertainty()  seeded lognormal MC
examples/quickstart.py            →  demo
tests/test_hook_effect.py         →  validation suite
tools/hook_effect_modeler_tool.py →  agent-facing JSON tool (graph-safe)
```

Pipeline: typed input → log-spaced dose grid → per-dose equilibrium solve →
curve → deterministic metrics → optional MC uncertainty → versioned result.

Failure handling: invalid inputs raise `HookModelError` (wrapped as structured
tool errors in the agent wrapper); solver non-convergence raises rather than
silently returning a heuristic; L0=0 returns the exact analytic zero-complex
state. No hidden heuristic substitutes for the solved equilibrium.
