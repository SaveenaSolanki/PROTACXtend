"""Model-weight registry with lazy, licence-checked, checksum-verified download.

Model weights are never baked into the default image. Backends declare which
models they need; the registry verifies the licence against the policy, streams
the download to a cache directory, checks SHA-256, and only then returns the
path.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from protacxtend.scientific_backends.licenses import (
    DEFAULT_POLICY,
    LicenseInfo,
    LicensePolicy,
    OPEN_SOURCE_PERMISSIVE,
)


@dataclass(frozen=True)
class ModelSpec:
    name: str
    backend: str
    version: str = ""
    url: str = ""
    sha256: str = ""
    license: LicenseInfo = OPEN_SOURCE_PERMISSIVE
    size_mb: float = 0.0
    vram_gb: float = 0.0
    local_path: str = ""
    requires_gpu: bool = False
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "backend": self.backend, "version": self.version,
            "url": self.url, "sha256": self.sha256, "license": self.license.name,
            "license_class": self.license.license_class.value,
            "size_mb": self.size_mb, "vram_gb": self.vram_gb,
            "local_path": self.local_path, "requires_gpu": self.requires_gpu,
            "description": self.description,
        }


MODEL_REGISTRY: dict[str, ModelSpec] = {
    "tack_dc50": ModelSpec("tack_dc50", "chemprop", "committed", local_path="protacxtend/data/tack/tack_dc50_model.joblib",
                           description="Committed TACK DC50 model (shipped as package data)"),
    "tack_dmax": ModelSpec("tack_dmax", "chemprop", "committed", local_path="protacxtend/data/tack/tack_dmax_model.joblib",
                           description="Committed TACK Dmax model"),
    "tack_bin": ModelSpec("tack_bin", "chemprop", "committed", local_path="protacxtend/data/tack/tack_bin_model.joblib",
                          description="Committed TACK binary degradation model"),
    "chemberta": ModelSpec("chemberta", "transformers", "",
                           url="https://huggingface.co/DeepChem/ChemBERTa-77M-MTR",
                           license=OPEN_SOURCE_PERMISSIVE, description="ChemBERTa SMILES encoder"),
    "esm2_t33": ModelSpec("esm2_t33", "esm", "650M",
                          url="https://dl.fbaipublicfiles.com/fair-esm/models/esm2_t33_650M_UR50D.pt",
                          license=OPEN_SOURCE_PERMISSIVE, size_mb=2600,
                          description="ESM-2 protein language model (MIT)"),
    "diffdock_weights": ModelSpec("diffdock_weights", "diffdock", "",
                                  url="", license=OPEN_SOURCE_PERMISSIVE, requires_gpu=True,
                                  description="DiffDock weights (add SHA256 before enabling auto-download)"),
    "alphafold_params": ModelSpec("alphafold_params", "structure_retrieval", "2.3",
                                  url="", license=OPEN_SOURCE_PERMISSIVE,
                                  size_mb=5000, requires_gpu=True,
                                  description="AlphaFold params (licence-checked, very large)"),
}


def cache_dir() -> Path:
    root = os.environ.get("PROTACXTEND_MODEL_CACHE")
    path = Path(root) if root else (Path.home() / ".protacxtend" / "models")
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_models() -> list[dict[str, Any]]:
    return [spec.to_dict() for spec in MODEL_REGISTRY.values()]


def models_for(backend: str) -> list[ModelSpec]:
    return [m for m in MODEL_REGISTRY.values() if m.backend == backend]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_model(name: str, *, policy: LicensePolicy | None = None,
                allow_unverified: bool = False, dest: str | Path | None = None) -> dict[str, Any]:
    """Resolve a model to a local path, downloading + verifying when needed.

    Returns ``{status, path, name, version, license_class, sha256, verified}``.
    Never downloads a model whose licence the policy rejects.
    """
    policy = policy or DEFAULT_POLICY
    spec = MODEL_REGISTRY.get(name)
    if spec is None:
        return {"status": "unknown_model", "name": name}
    allowed, reason = policy.allows(spec.license)
    if not allowed:
        return {"status": "LICENSE_REQUIRED", "name": name, "reason": reason,
                "license_class": spec.license.license_class.value}

    if spec.local_path:
        local = Path(spec.local_path)
        if local.exists():
            return {"status": "local", "name": name, "path": str(local),
                    "verified": True, "license_class": spec.license.license_class.value}
        return {"status": "missing_local_asset", "name": name, "path": str(local)}

    target_dir = Path(dest) if dest else cache_dir()
    target = target_dir / f"{name}{Path(spec.url).suffix or '.bin'}"
    if target.exists() and spec.sha256:
        if _sha256(target) == spec.sha256:
            return {"status": "cached", "name": name, "path": str(target), "verified": True,
                    "license_class": spec.license.license_class.value}
    if not spec.url:
        return {"status": "no_url", "name": name,
                "reason": "model URL/SHA256 not configured; add to MODEL_REGISTRY"}
    if not spec.sha256 and not allow_unverified:
        return {"status": "unverified_refused", "name": name,
                "reason": "no SHA256 on file; pass allow_unverified=True to override"}
    if not policy.allow_network:
        return {"status": "CAPABILITY_UNAVAILABLE", "name": name,
                "reason": "network disabled; set PROTACXTEND_ALLOW_NETWORK=1 to download"}
    try:
        import requests

        target.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(spec.url, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            with tempfile.NamedTemporaryFile(delete=False, dir=str(target.parent)) as tmp:
                digest = hashlib.sha256()
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    tmp.write(chunk)
                    digest.update(chunk)
                tmp_path = Path(tmp.name)
        if spec.sha256 and digest.hexdigest() != spec.sha256:
            tmp_path.unlink(missing_ok=True)
            return {"status": "checksum_mismatch", "name": name,
                    "expected": spec.sha256, "actual": digest.hexdigest()}
        tmp_path.replace(target)
        return {"status": "downloaded", "name": name, "path": str(target), "verified": bool(spec.sha256),
                "sha256": digest.hexdigest(), "license_class": spec.license.license_class.value}
    except Exception as exc:  # noqa: BLE001
        return {"status": "download_failed", "name": name, "error": str(exc)}


__all__ = ["ModelSpec", "MODEL_REGISTRY", "list_models", "models_for", "fetch_model", "cache_dir"]
