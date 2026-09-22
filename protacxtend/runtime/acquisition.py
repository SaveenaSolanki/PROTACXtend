"""Controlled on-demand capability acquisition.

Resolution order (never skips a step, always explains itself):

    1. READY            local backend already installed and healthcheck-verified
    2. INSTALLABLE      an approved, pinned recipe exists and can be provisioned
    3. FALLBACK         a validated alternative backend/tool for the capability
    4. REMOTE           an approved public web service/API for the capability
    5. BLOCKED          nothing approved is available (explicit reason recorded)

Security rules
--------------
* The agent/LLM surface exposes **no** install action. Only the human CLI
  ``protacxtend install <name>`` can reach :func:`install`.
* Only :data:`protacxtend.runtime.recipes.RECIPES` entries are installable.
* Commands are argument lists; ``shell=True`` is never used and user input is
  never interpolated into a command line.
* A recipe is registered READY only after version verification **and** a passing
  smoke test inside the isolated environment.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from protacxtend.runtime.recipes import RECIPES, Recipe, find_recipe, recipes_for_capability

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "results" / "audit"
ACQUIRED_ROOT = Path.home() / ".protacxtend" / "acquired"
LEDGER = AUDIT / "installation_ledger.jsonl"
_SAFE = re.compile(r"^[A-Za-z0-9._+=<>!~\[\],:/-]+$")

# Approved remote services (public REST APIs already used by the adapters).
APPROVED_REMOTE: dict[str, list[str]] = {
    "literature_mining": ["europepmc", "pubmed", "crossref", "uniprot"],
    "structure_preparation": ["rcsb_pdb", "alphafold"],
    "cheminformatics": ["pubchem"],
    "admet_toxicity": ["chembl"],
    "binding_energy": ["bindingdb"],
    "degradation_prediction": ["protacdb", "protacpedia"],
}


@dataclass
class Resolution:
    query: str
    capability: str
    state: str                      # READY | INSTALLABLE | FALLBACK | REMOTE | BLOCKED
    backend: str = ""
    version: str = ""
    recipe: str = ""
    reason: str = ""
    attempts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── live detection helpers ──────────────────────────────────────────────
def module_version(module: str) -> str:
    if importlib.util.find_spec(module) is None:
        return ""
    try:
        mod = __import__(module)
    except Exception:
        return "import-error"
    v = getattr(mod, "__version__", None)
    if isinstance(v, (tuple, list)):
        return ".".join(str(x) for x in v)
    if v:
        return str(v)
    try:
        import importlib.metadata as md
        return md.version(module)
    except Exception:
        return "installed"


def venv_python(recipe: Recipe) -> Path:
    base = ACQUIRED_ROOT / recipe.name
    return base / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def recipe_installed(recipe: Recipe) -> tuple[bool, str]:
    """Check the isolated env first, then the host env."""
    vpy = venv_python(recipe)
    if vpy.exists():
        try:
            out = subprocess.run(
                [str(vpy), "-c",
                 f"import importlib.metadata as m; print(m.version({recipe.import_name!r}))"],
                capture_output=True, text=True, timeout=60)
            if out.returncode == 0:
                return True, out.stdout.strip()
        except Exception:
            pass
    v = module_version(recipe.import_name)
    return (bool(v) and v != "import-error"), v


def _record(entry: dict) -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": _utc(), **entry}, default=str) + "\n")


# ── resolution ──────────────────────────────────────────────────────────
def resolve(query: str) -> Resolution:
    """Resolve a capability/tool name through the ordered acquisition policy."""
    from protacxtend.runtime import registry as reg

    recs = reg.build_registry()
    matches = reg.find(recs, query)
    cap = matches[0].name if matches else query
    res = Resolution(query=query, capability=cap, state="BLOCKED")

    # 1. READY local backend -------------------------------------------------
    from protacxtend.escalation.capabilities import capability_for
    from protacxtend.scientific_backends.registry import Capability, REGISTRY
    candidate_caps: list[str] = []
    for r in matches:
        for cand in (r.name, r.category, r.primary_backend, capability_for(r.name)):
            if cand and cand not in candidate_caps:
                candidate_caps.append(cand)
    for cand in (cap, query):
        if cand and cand not in candidate_caps:
            candidate_caps.append(cand)
    for cval in candidate_caps:
        try:
            species = REGISTRY.resolve_one(Capability(cval))
        except Exception:
            species = None
        if species is not None and species.health().available:
            res.state, res.backend, res.version = "READY", species.name, species.health().version
            res.capability = cval
            res.reason = f"local backend '{species.name}' healthy for capability '{cval}'"
            res.attempts.append({"step": "READY", "backend": species.name, "capability": cval, "ok": True})
            return res
    for r in matches:
        if r.kind == "toolkit_tool" and r.maturity_status == "installed":
            res.state, res.backend = "READY", r.name
            res.reason = "toolkit tool installed"
            res.attempts.append({"step": "READY", "backend": r.name, "ok": True})
            return res
        if r.kind == "agent_tool" and r.maturity_status == "ready":
            res.state, res.backend = "READY", r.name
            res.reason = "agent tool ready"
            res.attempts.append({"step": "READY", "backend": r.name, "ok": True})
            return res
    res.attempts.append({"step": "READY", "ok": False, "reason": "no healthy local backend"})

    # 2. INSTALLABLE approved recipe ----------------------------------------
    names = {cap, query} | {r.name for r in matches}
    recipe = next((find_recipe(n) for n in names if find_recipe(n)), None)
    if recipe and recipe.approved:
        installed, version = recipe_installed(recipe)
        if installed and version.split(".")[0] == recipe.pinned_version.split(".")[0]:
            res.state, res.backend, res.version, res.recipe = "READY", recipe.name, version, recipe.name
            res.reason = "approved recipe already provisioned"
            res.attempts.append({"step": "INSTALLABLE", "recipe": recipe.name, "ok": True})
            return res
        res.state, res.recipe = "INSTALLABLE", recipe.name
        res.reason = f"approved pinned recipe {recipe.spec}"
        res.attempts.append({"step": "INSTALLABLE", "recipe": recipe.name, "ok": True})
        return res
    res.attempts.append({"step": "INSTALLABLE", "ok": False, "reason": "no approved recipe"})

    # 3. validated FALLBACK --------------------------------------------------
    for r in matches:
        if r.ordered_fallbacks:
            res.state, res.backend = "FALLBACK", r.ordered_fallbacks[0]
            res.reason = "validated fallback chain"
            res.attempts.append({"step": "FALLBACK", "backend": res.backend, "ok": True})
            return res
    res.attempts.append({"step": "FALLBACK", "ok": False, "reason": "no declared fallback"})

    # 4. approved REMOTE -----------------------------------------------------
    for remote in APPROVED_REMOTE.get(cap, []):
        res.state, res.backend = "REMOTE", remote
        res.reason = f"approved remote service '{remote}'"
        res.attempts.append({"step": "REMOTE", "backend": remote, "ok": True})
        return res
    res.attempts.append({"step": "REMOTE", "ok": False, "reason": "no approved remote service"})

    # 5. BLOCKED -------------------------------------------------------------
    res.reason = "no READY/INSTALLABLE/FALLBACK/REMOTE path; capability not approved"
    _record({"action": "resolve", "query": query, "state": "BLOCKED", "reason": res.reason})
    return res


# ── installation ────────────────────────────────────────────────────────
def plan(name: str) -> dict:
    recipe = find_recipe(name)
    if recipe is None:
        return {"name": name, "approved": False, "state": "BLOCKED",
                "reason": "not in allow-listed recipes; arbitrary installs are forbidden"}
    return {
        "name": recipe.name, "approved": recipe.approved, "state": "INSTALLABLE",
        "capability": recipe.capability, "spec": recipe.spec, "manager": recipe.manager,
        "isolated_env": str(ACQUIRED_ROOT / recipe.name),
        "checksum_applicable": bool(recipe.url),
        "checksum_sha256": recipe.checksum_sha256,
        "smoke": recipe.smoke, "timeout_s": recipe.timeout_s,
        "argv": [sys.executable, "-m", "venv", str(ACQUIRED_ROOT / recipe.name)],
        "pip_argv": [str(venv_python(recipe)), "-m", "pip", "install", "--no-input", recipe.spec],
    }


def install(name: str, allow: bool = False, dry_run: bool = True) -> dict:
    """Install an approved, pinned recipe into an isolated environment.

    Never executes arbitrary commands: the only argv used are derived from the
    matched :class:`Recipe`. Non-allow-listed names are BLOCKED.
    """
    recipe = find_recipe(name)
    if recipe is None or not recipe.approved:
        result = {"name": name, "state": "BLOCKED", "success": False,
                  "reason": "not in allow-listed approved recipes"}
        _record({"action": "install", **result})
        return result

    if dry_run or not allow:
        _p = plan(recipe.name)
        result = {"name": recipe.name, "state": "PLANNED", "success": False,
                  "reason": "dry-run (pass allow=True to execute)", **_p}
        result["state"] = "PLANNED"
        _record({"action": "install_plan", "name": recipe.name})
        return result

    # build argv exclusively from the recipe (defence in depth)
    for token in [recipe.spec, recipe.import_name]:
        if not _SAFE.match(token):
            result = {"name": recipe.name, "state": "BLOCKED", "success": False,
                      "reason": f"recipe token failed safety check: {token!r}"}
            _record({"action": "install", **result})
            return result

    env_dir = ACQUIRED_ROOT / recipe.name
    vpy = venv_python(recipe)
    t0 = time.time()
    log: list[str] = []
    before = recipe_installed(recipe)[1]

    if recipe.url:
        # direct artifact: checksum is mandatory
        if not recipe.checksum_sha256:
            return _fail(recipe, "direct URL recipe without checksum", before, log, t0)
        try:
            import urllib.request
            with urllib.request.urlopen(recipe.url, timeout=120) as r:
                blob = r.read()
        except Exception as exc:
            return _fail(recipe, f"download failed: {exc}", before, log, t0)
        digest = hashlib.sha256(blob).hexdigest()
        if digest != recipe.checksum_sha256:
            return _fail(recipe, f"checksum mismatch {digest[:12]} != {recipe.checksum_sha256[:12]}",
                         before, log, t0)
        artifact = env_dir / Path(recipe.url).name
        env_dir.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(blob)
        pip_target = str(artifact)
    else:
        pip_target = recipe.spec

    try:
        env_dir.parent.mkdir(parents=True, exist_ok=True)
        if not vpy.exists():
            r = subprocess.run([sys.executable, "-m", "venv", str(env_dir)],
                               capture_output=True, text=True, timeout=300)
            log.append(f"venv rc={r.returncode}")
            if r.returncode != 0:
                return _fail(recipe, "venv creation failed", before, log, t0)
        r = subprocess.run([str(vpy), "-m", "pip", "install", "--no-input", "--disable-pip-version-check",
                            pip_target], capture_output=True, text=True, timeout=recipe.timeout_s)
        log.append(f"pip rc={r.returncode}; {(r.stderr or '')[-400:]}")
        if r.returncode != 0:
            return _fail(recipe, "pip install failed", before, log, t0)
    except subprocess.TimeoutExpired:
        return _fail(recipe, f"install timed out after {recipe.timeout_s}s", before, log, t0)

    # version verification
    ok, after = recipe_installed(recipe)
    if not ok or after.split(".")[0] != recipe.pinned_version.split(".")[0]:
        return _fail(recipe, f"version verification failed (got {after!r}, pin {recipe.pinned_version})",
                     before, log, t0)

    # mandatory smoke test
    smoke = smoke_test(recipe)
    if not smoke["ok"]:
        return _fail(recipe, f"smoke test failed: {smoke['detail']}", before, log, t0,
                     version_after=after)

    result = {
        "name": recipe.name, "state": "READY", "success": True,
        "version_before": before, "version_after": after,
        "pinned_version": recipe.pinned_version, "smoke": smoke,
        "elapsed_s": round(time.time() - t0, 1), "reason": "installed, verified and smoke-tested",
    }
    _record({"action": "install", **result})
    return result


def _fail(recipe: Recipe, reason: str, before: str, log: list[str], t0: float,
          version_after: str = "") -> dict:
    result = {"name": recipe.name, "state": "FAILED", "success": False,
              "version_before": before, "version_after": version_after,
              "elapsed_s": round(time.time() - t0, 1), "reason": reason, "log": log[-3:]}
    _record({"action": "install", **result})
    return result


def smoke_test(recipe: Recipe) -> dict:
    vpy = venv_python(recipe)
    if not vpy.exists():
        return {"ok": False, "detail": "isolated env missing"}
    code = (f"import {recipe.import_name} as m; "
            f"print(getattr(m, '__version__', 'ok'))")
    try:
        r = subprocess.run([str(vpy), "-c", code], capture_output=True, text=True, timeout=180)
        return {"ok": r.returncode == 0, "detail": (r.stdout or r.stderr).strip()[:200]}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}


def ledger_entries() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [json.loads(ln) for ln in LEDGER.read_text(encoding="utf-8").splitlines() if ln.strip()]


def acquisition_summary() -> dict:
    from collections import Counter
    entries = ledger_entries()
    installs = [e for e in entries if e.get("action") == "install"]
    return {
        "ledger": str(LEDGER),
        "resolutions": sum(1 for e in entries if e.get("action") == "resolve"),
        "install_attempts": len(installs),
        "install_success": sum(1 for e in installs if e.get("success")),
        "states": dict(Counter(e.get("state") for e in installs)),
        "approved_recipes": len(RECIPES),
    }
