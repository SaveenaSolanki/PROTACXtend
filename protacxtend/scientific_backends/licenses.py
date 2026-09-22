"""Licence classification and the default bundling policy.

The default PROTACXtend installation must be safe to redistribute and run with
no commercial, academic-only, or web-only dependency. This module encodes that
rule once and lets every backend declare its licence so the resolver can apply
it uniformly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class LicenseClass(str, Enum):
    OPEN_SOURCE_PERMISSIVE = "open_source_permissive"   # MIT/BSD/Apache
    OPEN_SOURCE_COPYLEFT = "open_source_copyleft"       # GPL/LGPL (local use only)
    ACADEMIC_ONLY = "academic_only"
    COMMERCIAL = "commercial"
    PROPRIETARY = "proprietary"
    WEB_SERVICE = "web_service"
    UNKNOWN = "unknown"


#: Classes that may never be bundled or auto-installed in the default profile.
RESTRICTED_CLASSES = {
    LicenseClass.ACADEMIC_ONLY,
    LicenseClass.COMMERCIAL,
    LicenseClass.PROPRIETARY,
    LicenseClass.WEB_SERVICE,
    LicenseClass.UNKNOWN,
}


@dataclass(frozen=True)
class LicenseInfo:
    name: str
    license_class: LicenseClass = LicenseClass.OPEN_SOURCE_PERMISSIVE
    redistributable: bool = True
    requires_manual_acceptance: bool = False
    requires_network: bool = False
    academic_only: bool = False
    commercial_use_restricted: bool = False
    url: str = ""

    @property
    def label(self) -> str:
        return self.license_class.value

    @property
    def open_source(self) -> bool:
        return self.license_class in {
            LicenseClass.OPEN_SOURCE_PERMISSIVE, LicenseClass.OPEN_SOURCE_COPYLEFT}


OPEN_SOURCE_PERMISSIVE = LicenseInfo("open-source permissive", LicenseClass.OPEN_SOURCE_PERMISSIVE)
OPEN_SOURCE_COPYLEFT = LicenseInfo("GPL/LGPL copyleft", LicenseClass.OPEN_SOURCE_COPYLEFT,
                                    redistributable=False)
ACADEMIC_ONLY = LicenseInfo("academic-only", LicenseClass.ACADEMIC_ONLY, redistributable=False,
                            academic_only=True, commercial_use_restricted=True,
                            requires_manual_acceptance=True)
COMMERCIAL = LicenseInfo("commercial/proprietary", LicenseClass.COMMERCIAL, redistributable=False,
                         commercial_use_restricted=True, requires_manual_acceptance=True)
PROPRIETARY = LicenseInfo("proprietary", LicenseClass.PROPRIETARY, redistributable=False,
                          commercial_use_restricted=True, requires_manual_acceptance=True)
WEB_SERVICE = LicenseInfo("web service (no redistribution)", LicenseClass.WEB_SERVICE,
                          redistributable=False, requires_network=True,
                          requires_manual_acceptance=True)


@dataclass
class LicensePolicy:
    """What the resolver is allowed to use by default."""

    allow_copyleft: bool = True
    allow_academic_only: bool = False
    allow_commercial: bool = False
    allow_web_service: bool = False
    allow_network: bool = False
    allow_unknown: bool = False
    require_redistributable: bool = False

    def allows(self, info: LicenseInfo) -> tuple[bool, str]:
        cls = info.license_class
        if cls is LicenseClass.OPEN_SOURCE_PERMISSIVE:
            return True, "permissive open source"
        if cls is LicenseClass.OPEN_SOURCE_COPYLEFT:
            return (self.allow_copyleft, "GPL/LGPL allowed locally" if self.allow_copyleft
                    else "copyleft disabled by policy")
        if cls is LicenseClass.ACADEMIC_ONLY:
            return (self.allow_academic_only, "academic-only backend requires explicit opt-in")
        if cls is LicenseClass.COMMERCIAL:
            return (self.allow_commercial, "commercial backend requires a licence")
        if cls is LicenseClass.PROPRIETARY:
            return (self.allow_commercial, "proprietary backend requires a licence")
        if cls is LicenseClass.WEB_SERVICE:
            allowed = self.allow_web_service and self.allow_network
            return allowed, "web-only backend requires network + opt-in"
        return (self.allow_unknown, "unknown licence")


DEFAULT_POLICY = LicensePolicy(
    allow_copyleft=True,
    allow_academic_only=False,
    allow_commercial=False,
    allow_web_service=False,
    allow_network=False,
    allow_unknown=False,
)


def policy_from_env(env: dict[str, str] | None = None) -> LicensePolicy:
    """Build a policy from ``PROTACXTEND_ALLOW_*`` environment flags."""
    import os

    env = env if env is not None else os.environ
    flags = {
        "academic": env.get("PROTACXTEND_ALLOW_ACADEMIC", "0") == "1",
        "commercial": env.get("PROTACXTEND_ALLOW_COMMERCIAL", "0") == "1",
        "web": env.get("PROTACXTEND_ALLOW_WEB", "0") == "1",
        "network": env.get("PROTACXTEND_ALLOW_NETWORK", "0") == "1",
        "unknown": env.get("PROTACXTEND_ALLOW_UNKNOWN_LICENSE", "0") == "1",
        "copyleft": env.get("PROTACXTEND_ALLOW_COPYLEFT", "1") != "0",
    }
    return LicensePolicy(
        allow_copyleft=flags["copyleft"],
        allow_academic_only=flags["academic"],
        allow_commercial=flags["commercial"],
        allow_web_service=flags["web"],
        allow_network=flags["network"],
        allow_unknown=flags["unknown"],
    )


def license_summary(info: LicenseInfo) -> dict[str, Any]:
    return {
        "name": info.name,
        "class": info.license_class.value,
        "redistributable": info.redistributable,
        "requires_manual_acceptance": info.requires_manual_acceptance,
        "requires_network": info.requires_network,
        "academic_only": info.academic_only,
        "commercial_use_restricted": info.commercial_use_restricted,
    }


__all__ = [
    "LicenseClass",
    "LicenseInfo",
    "LicensePolicy",
    "DEFAULT_POLICY",
    "policy_from_env",
    "RESTRICTED_CLASSES",
    "OPEN_SOURCE_PERMISSIVE",
    "OPEN_SOURCE_COPYLEFT",
    "ACADEMIC_ONLY",
    "COMMERCIAL",
    "PROPRIETARY",
    "WEB_SERVICE",
    "license_summary",
]
