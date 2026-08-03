#!/bin/bash
# P4ward run for PEG6 linker
# HMGB2 + ICM + Pomalidomide
cd /storage/saveena/protacpilot/outputs/p4ward_evidence/linker_optimization/p4ward_PEG6
docker run --rm \
  -v /storage/saveena/protacpilot/outputs/p4ward_evidence/linker_optimization/p4ward_PEG6:/home/data \
  paulajlr/p4ward:latest \
  --config_file /home/data/config.ini \
  2>&1 | tee p4ward_run.log
echo "P4ward run complete: PEG6"
