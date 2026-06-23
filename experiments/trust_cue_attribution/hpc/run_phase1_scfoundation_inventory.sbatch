#!/usr/bin/env bash
#SBATCH --job-name=trustcue-p1-scf-inv
#SBATCH --output=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-p1-scf-inv-%j.out
#SBATCH --error=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-p1-scf-inv-%j.err
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
PYTHON="${PYTHON:-/usr/bin/python3.12}"
OUT_DIR="${OUT_DIR:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/phase1_preflight}"
SCFOUNDATION_GENE_INDEX="${SCFOUNDATION_GENE_INDEX:-}"
PHASE1_INPUT_DATA="${PHASE1_INPUT_DATA:-}"

mkdir -p "$OUT_DIR" "$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/logs"
cd "$PROJECT_ROOT"

echo "PROJECT_ROOT=$PROJECT_ROOT"
echo "PYTHON=$PYTHON"
echo "OUT_DIR=$OUT_DIR"
echo "SCFOUNDATION_GENE_INDEX=$SCFOUNDATION_GENE_INDEX"
echo "PHASE1_INPUT_DATA=$PHASE1_INPUT_DATA"

export PYTHONNOUSERSITE=1

"$PYTHON" -m unittest discover -s experiments/trust_cue_attribution/tests

"$PYTHON" experiments/trust_cue_attribution/run.py phase1-input-inventory \
  --gene-index "$SCFOUNDATION_GENE_INDEX" \
  --input-data "$PHASE1_INPUT_DATA" \
  --out "$OUT_DIR/scfoundation_input_inventory.json"

status="$("$PYTHON" -c 'import json, sys; print(json.load(open(sys.argv[1]))["status"])' "$OUT_DIR/scfoundation_input_inventory.json")"
echo "PHASE1_SCF_INPUT_INVENTORY_STATUS=$status"
echo "TRUST_CUE_PHASE1_SCF_INPUT_INVENTORY_OK"
