"""Optional adapters for web-only scientific services.

PROTACXtend never scrapes SwissADME and never requires a browser/account. These
adapters exist only to return a clear ``LICENSE_REQUIRED`` / ``web-only`` signal
if someone explicitly asks for them; the default policy excludes them.
"""

from __future__ import annotations

from typing import Any, Callable

from protacxtend.scientific_backends.evidence import ScientificResult
from protacxtend.scientific_backends.licenses import ACADEMIC_ONLY, WEB_SERVICE
from protacxtend.scientific_backends.registry import Capability, BackendSpec, register


def _web_handler(capability: Capability, name: str, reason: str) -> Callable[..., ScientificResult]:
    def handler(**_: Any) -> ScientificResult:
        return ScientificResult.license_required(capability.value, name, reason)
    return handler


def _register_web(name: str, capabilities: tuple[Capability, ...], reason: str,
                  license=WEB_SERVICE) -> None:
    register(BackendSpec(
        name=name, capabilities=capabilities, license=license, priority=1, optional=True,
        requires_network=True, description=reason,
        health_check=lambda: _web_health(name),
        handlers={cap: _web_handler(cap, name, reason) for cap in capabilities},
    ))


def _web_health(name: str):
    from protacxtend.scientific_backends.dispatch import Availability

    return Availability(available=False, detail=f"{name}: web-only (not automated)")


_register_web("cluspro", (Capability.PPI_DOCKING,),
              "ClusPro is a web service requiring submission; use LightDock/geometry locally")
_register_web("swissadme", (Capability.ADMET,),
              "SwissADME is a web service and is never scraped; use RDKit/local ADMET")
_register_web("admetlab3", (Capability.ADMET,),
              "ADMETlab 3.0 is a web platform; use local RDKit/local ADMET models")
_register_web("pkcsm", (Capability.ADMET,),
              "pkCSM is a web platform; use local RDKit/local ADMET models")
_register_web("protox_ii", (Capability.ADMET,),
              "ProTox-II is a web platform; use local RDKit/local ADMET models")
_register_web("haddock_web", (Capability.PPI_DOCKING, Capability.TERNARY_DOCKING),
              "HADDOCK web server requires account submission; use LightDock locally")
_register_web("patchdock_web", (Capability.PPI_DOCKING,),
              "PatchDock is a web service; use local LightDock/geometry")
_register_web("ibm_rxn", (Capability.CHEMISTRY,),
              "IBM RXN is a hosted API; use local RDKit/AiZynthFinder")
_register_web("openadmet_web", (Capability.ADMET,),
              "OpenADMET hosted endpoint; use local ADMET descriptors/models")


def _register_haddock_cns() -> None:
    # CNS-dependent HADDOCK modules are academic/CNS and must never be silently invoked
    reason = ("HADDOCK CNS modules require a CNS licence and manual acceptance; "
              "use LightDock locally")
    register(BackendSpec(
        name="haddock_cns",
        capabilities=(Capability.PPI_DOCKING, Capability.TERNARY_DOCKING),
        license=ACADEMIC_ONLY, priority=2, optional=True,
        description=reason, citation="HADDOCK / CNS",
        health_check=lambda: _web_health("haddock_cns"),
        handlers={cap: _web_handler(cap, "haddock_cns", reason)
                  for cap in (Capability.PPI_DOCKING, Capability.TERNARY_DOCKING)},
    ))


_register_haddock_cns()
