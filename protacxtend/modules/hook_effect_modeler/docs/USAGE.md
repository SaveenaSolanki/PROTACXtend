# Usage — Hook Effect Modeler

Python
```python
from protacxtend.modules.hook_effect_modeler import simulate_hook_effect
r = simulate_hook_effect(
    poI_conc_nM=100.0, e3_conc_nM=100.0,
    kd_poi_protac_nM=50.0, kd_e3_protac_nM=50.0,
    alpha=30.0,
    uncertainty_pct={"kd": 15.0, "alpha": 20.0}, seed=42,
)
print(r.metrics.model_dump())
```

JSON tool (agent/LangGraph):
```python
from protacxtend.tools.hook_effect_modeler_tool import run_hook_effect_modeler
out = run_hook_effect_modeler({"alpha": 5.0, "points": 60})
assert out["success"]; out["result"]["metrics"]["hook_label"]
```

CLI demo: `python -m protacxtend.modules.hook_effect_modeler.examples.quickstart`
