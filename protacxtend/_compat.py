"""Compatibility shim: renamed package (synglue_agent -> protacxtend).

Committed model artifacts (pdc50_model.joblib, cell_context_model.joblib, ...)
were pickled while the package was named ``synglue_agent``, so their class
references point at ``synglue_agent.modules.*``. After the rename those imports
fail with ModuleNotFoundError. This finder transparently resolves any
``synglue_agent[.sub]`` import to the real ``protacxtend[.sub]`` module so
pickled artifacts keep loading — without retraining (audit provenance
preserved) and without ever re-executing the canonical module (which would
break pickle identity).

Design: find_spec only hands back a loader; the loader imports the canonical
module during exec_module (normal, cached import) and aliases its namespace.
Installed once from ``protacxtend/__init__.py``.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys

_PREFIX = "synglue_agent"
_REPLACEMENT = "protacxtend"
_INSTALLED = False


class _AliasLoader(importlib.abc.Loader):
    def __init__(self, new_name: str):
        self._new_name = new_name

    def create_module(self, spec):
        return None  # default new module; exec fills it

    def exec_module(self, module) -> None:
        target = importlib.import_module(self._new_name)
        # mirror the canonical namespace so getattr(alias, name) returns the
        # very same objects (pickle identity for classes defined there)
        module.__dict__.update(target.__dict__)


class _RenamedPackageFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == _PREFIX or fullname.startswith(_PREFIX + "."):
            new_name = _REPLACEMENT + fullname[len(_PREFIX):]
            return importlib.util.spec_from_loader(fullname, _AliasLoader(new_name))
        return None


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    # drop any stale real entries first (the renamed tree may linger locally)
    for name in [n for n in sys.modules if n == _PREFIX or n.startswith(_PREFIX + ".")]:
        del sys.modules[name]
    sys.meta_path.insert(0, _RenamedPackageFinder())
    _INSTALLED = True
