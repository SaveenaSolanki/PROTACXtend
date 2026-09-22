"""Allow-listed, pinned installation recipes for on-demand capability acquisition.

Security model
--------------
* The LLM/agent surface has **no** install tool. Installation is only reachable
  through the human-facing ``protacxtend install <approved-capability>`` command.
* Only names present in :data:`RECIPES` can be installed. There is no path that
  accepts a raw package name or a shell command from a caller.
* Commands are executed as **argument lists** (never ``shell=True``) inside a
  dedicated virtual environment under ``~/.protacxtend/acquired/<recipe>``.
* Every recipe pins an exact version. After installation the version is verified
  and a smoke test must pass before the capability is registered READY.
* A checksum is required and verified when a recipe specifies a direct artifact
  URL; for index-pinned recipes the checksum requirement is reported as
  ``not_applicable`` (pip resolves and hash-checks the wheel from the index over TLS).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Recipe:
    name: str                      # unique recipe id == installable name
    capability: str                # canonical capability id it provides
    manager: str                   # "pip" (only approved manager)
    spec: str                      # exact pinned requirement, e.g. "meeko==0.8.0"
    import_name: str               # module/import used for version + smoke verification
    pinned_version: str
    smoke: str                     # smoke-test key executed inside the isolated env
    license_class: str = "open_source_permissive"
    requires_gpu: bool = False
    requires_network: bool = False
    url: str = ""                  # optional direct artifact URL
    checksum_sha256: str = ""      # required when url is set
    notes: str = ""
    approved: bool = True
    timeout_s: int = 900

    @property
    def isolated(self) -> bool:
        return True

    def to_dict(self) -> dict:
        d = asdict(self)
        d["checksum_required"] = bool(self.url)
        d["checksum_applicable"] = bool(self.url)
        return d


def _r(*args, **kwargs) -> Recipe:
    return Recipe(*args, **kwargs)


# Capability keys follow protacxtend.scientific_backends.registry.Capability and
# protacxtend.escalation.capabilities.CAPABILITY_DESCRIPTIONS.
RECIPES: dict[str, Recipe] = {
    r.name: r
    for r in [
        _r("meeko", "ligand_preparation", "pip", "meeko==0.8.0", "meeko", "0.8.0",
           "import_version", notes="RDKit-based ligand PDBQT preparation"),
        _r("pdbfixer", "structure_preparation", "pip", "pdbfixer==1.12.0", "pdbfixer", "1.12.0",
           "import_version", notes="Structure repair / missing atoms / hydrogens"),
        _r("biopython", "structure_preparation", "pip", "biopython==1.88", "Bio", "1.88",
           "import_version", notes="PDB parsing and geometry primitives"),
        _r("openbabel-wheel", "cheminformatics", "pip", "openbabel-wheel==3.1.1.23", "openbabel", "3.1.1.23",
           "import_version", notes="Format conversion / fallback cheminformatics"),
        _r("rdchiral", "reaction_prediction", "pip", "rdchiral==1.1.0", "rdchiral", "1.1.0",
           "import_version", notes="Template-based retrosynthetic transforms"),
        _r("rxnmapper", "reaction_prediction", "pip", "rxnmapper==0.4.3", "rxnmapper", "0.4.3",
           "import_version", requires_network=True, notes="Atom-mapping model weights download on first use"),
        _r("rascore", "synthetic_accessibility", "pip", "rascore==1.0.7", "rascore", "1.0.7",
           "import_version", requires_network=True, notes="Retrosynthetic accessibility score"),
        _r("crem", "de_novo_generation", "pip", "crem==0.3.2", "crem", "0.3.2",
           "import_version", notes="Fragment-based molecular generation"),
        _r("guacamol", "de_novo_generation", "pip", "guacamol==0.5.5", "guacamol", "0.5.5",
           "import_version", notes="Molecular generation benchmark suite"),
        _r("mmpdb", "fragmentation", "pip", "mmpdb==3.1.4", "mmpdb", "3.1.4",
           "import_version", notes="Matched molecular pair analysis"),
        _r("PyTDC", "admet_toxicity", "pip", "PyTDC==1.1.15", "tdc", "1.1.15",
           "import_version", requires_network=True, notes="Therapeutics Data Commons ADMET models"),
        _r("aizynthfinder", "retrosynthesis", "pip", "aizynthfinder==4.4.1", "aizynthfinder", "4.4.1",
           "import_version", requires_gpu=False, requires_network=True,
           notes="Retrosynthetic tree search; policy assets downloaded separately"),
        _r("chembl-webresource-client", "literature_mining", "pip",
           "chembl_webresource_client==0.10.9", "chembl_webresource_client", "0.10.9",
           "import_version", requires_network=True, notes="ChEMBL REST client"),
        _r("requests", "literature_mining", "pip", "requests==2.34.2", "requests", "2.34.2",
           "import_version", notes="HTTP client used by external database adapters"),
    ]
}

# Aliases so `install <tool or capability>` is unambiguous but still allow-listed.
ALIASES: dict[str, str] = {
    "ligand_preparation": "meeko",
    "structure_preparation": "pdbfixer",
    "cheminformatics": "openbabel-wheel",
    "reaction_prediction": "rdchiral",
    "synthetic_accessibility": "rascore",
    "de_novo_generation": "crem",
    "fragmentation": "mmpdb",
    "admet_toxicity": "PyTDC",
    "retrosynthesis": "aizynthfinder",
    "literature_mining": "chembl-webresource-client",
    "openbabel": "openbabel-wheel",
    "tdc": "PyTDC",
    "chembl": "chembl-webresource-client",
}


def find_recipe(name: str) -> Recipe | None:
    """Resolve an allow-listed recipe by exact name or approved alias. Never
    constructs a package name from arbitrary input."""
    if not name:
        return None
    key = name.strip()
    if key in RECIPES:
        return RECIPES[key]
    if key in ALIASES:
        return RECIPES[ALIASES[key]]
    # case-insensitive exact match only (no fuzzy package guessing)
    lowered = key.lower()
    for rname, recipe in RECIPES.items():
        if rname.lower() == lowered:
            return recipe
    for alias, target in ALIASES.items():
        if alias.lower() == lowered:
            return RECIPES[target]
    return None


def is_approved(name: str) -> bool:
    r = find_recipe(name)
    return bool(r and r.approved)


def list_recipes() -> list[dict]:
    return [RECIPES[k].to_dict() for k in sorted(RECIPES)]


def recipes_for_capability(capability: str) -> list[Recipe]:
    return [r for r in RECIPES.values() if r.capability == capability and r.approved]
