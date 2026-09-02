# P4ward Docker image for PROTACPilot

This directory contains the Docker build context for the P4ward ternary
complex modeling engine. The image is used by `P4wardWrapper` in
`tools/p4ward_wrapper.py`.

## Quick Start

```bash
# Build the image
docker build -t protacpilot/p4ward -f Dockerfile ../..

# Test it
docker run --rm protacpilot/p4ward --write_default
```

## Usage

The wrapper in `synglue_agent/tools/p4ward_wrapper.py` handles Docker
invocation automatically. To use it:

```python
from synglue_agent.tools.p4ward_wrapper import P4wardWrapper

wrapper = P4wardWrapper(mode="docker")
result = wrapper.run(
    receptor_pdb="hmgb2.pdb",
    ligase_pdb="crbn.pdb",
    receptor_ligand_mol2="icm.mol2",
    ligase_ligand_mol2="pomalidomide.mol2", 
    protac_smiles=["...SMILES..."],
    e3="CRBN",
    output_dir="./p4ward_output",
)
```

## Pre-built Image

A pre-built image is available at `paulajlr/p4ward:latest`.
The wrapper will use it by default. If you want to build locally,
run the Dockerfile in this directory.

## License Note

P4ward depends on MEGADOCK (CC BY-NC 4.0). Commercial use is prohibited.
This image is for academic/non-commercial research only.
