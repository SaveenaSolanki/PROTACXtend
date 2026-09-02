#!/bin/bash
# Usage: bash run_turbo.sh <db_dir> <out_dir> <query_csv> [workers]
# Example: bash run_turbo.sh data outputs/SynGlue_Runs query.csv 15

DB_DIR=${1:-data}
OUT_DIR=${2:-outputs/SynGlue_Runs}
QUERY_CSV=${3:-query.csv}
WORKERS=${4:-15}

python3 multiprocess_synglue.py \
	--db_dir "$DB_DIR" \
	--out_dir "$OUT_DIR" \
	--query "$QUERY_CSV" \
	--workers "$WORKERS"
