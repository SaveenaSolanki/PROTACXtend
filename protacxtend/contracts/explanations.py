"""Corrected, source-backed scientific explanations.

These are the authoritative in-repo statements; they are used in reports and
the run page so a model's imprecise phrasing cannot become the record.
"""

from __future__ import annotations

#: MZ1 is a KNOWN compound, used here only as a reconstruction reference.
MZ1_ATTRIBUTION = (
    "MZ1 BRD4-VHL degrader (known compound): Zengerle, Chan & Ciulli, "
    "ACS Chem. Biol. 2015, 10(8):1770-1777, DOI 10.1021/acschembio.5b00216; "
    "ternary crystal structure PDB 5T35: Gadd et al., Nat. Chem. Biol. 2017, "
    "DOI 10.1038/nchembio.2329. The BRD4-binding moiety is the JQ1 "
    "triazolodiazepine; the E3 recruiter is VH032 (VHL); the linker is PEG3."
)

#: Correct hook-effect mechanism (the earlier model answer was wrong).
HOOK_EFFECT_EXPLANATION = (
    "The PROTAC hook effect is a ternary-complex equilibrium phenomenon: "
    "forming the POI:PROTAC:E3 ternary complex requires PROTAC to engage the "
    "target and the E3 simultaneously. At high PROTAC concentration both "
    "binary complexes (POI:PROTAC and PROTAC:E3) are saturated, which depletes "
    "the free partner available to complete the ternary complex, so ternary "
    "abundance — and degradation — falls as dose rises. "
    "Source: Douglass et al., J. Am. Chem. Soc. 2013, 135, 6092 "
    "(DOI 10.1021/ja4010379); mechanism implemented in "
    "protacxtend/modules/hook_effect_modeler/core.py. "
    "It is NOT caused by 'cooperative binding of the E3 ligand' and NOT by "
    "'E3 saturation'; cooperativity (alpha) modulates ternary affinity and is "
    "not itself the hook mechanism."
)
