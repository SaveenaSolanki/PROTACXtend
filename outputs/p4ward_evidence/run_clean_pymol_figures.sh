#!/usr/bin/env bash
set -euo pipefail
cd /storage/saveena/protacpilot/outputs/p4ward_evidence
export LIBGL_ALWAYS_SOFTWARE=1
pymol -cq overview_clean_v2.pml
pymol -cq gap_zoom_clean_v2.pml
pymol -cq lysines_clean_v2.pml
ls -lh fig*_clean_v2.png fig*_clean_v2.pse
