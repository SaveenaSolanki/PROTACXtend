"""Hook Effect Modeler (Module 1 of the PROTACXtend sequential build).

Public API: ``simulate_hook_effect(...)`` — mechanistic three-body
equilibrium simulation of PROTAC ternary-complex dose response (bell curve
with hook effect).

    from synglue_agent.modules.hook_effect_modeler import simulate_hook_effect

    result = simulate_hook_effect(poI_conc_nM=100.0, e3_conc_nM=100.0,
                                  kd_poi_protac_nM=50.0, kd_e3_protac_nM=50.0,
                                  alpha=10.0)
    result.metrics.hook_severity   # 0..1
    result.metrics.optimal_concentration_nM
    result.curve                   # typed curve points
"""

from synglue_agent.modules.hook_effect_modeler.config import (
    DEFAULT_CONFIG_PATH,
    ModelerConfig,
)
from synglue_agent.modules.hook_effect_modeler.core import (
    HookModelError,
    simulate_hook_effect,
    solve_ternary,
)
from synglue_agent.modules.hook_effect_modeler.schemas import (
    MODEL_VERSION,
    HookEffectInput,
    HookEffectResult,
)

__all__ = [
    "simulate_hook_effect",
    "solve_ternary",
    "HookModelError",
    "HookEffectInput",
    "HookEffectResult",
    "ModelerConfig",
    "DEFAULT_CONFIG_PATH",
    "MODEL_VERSION",
]
