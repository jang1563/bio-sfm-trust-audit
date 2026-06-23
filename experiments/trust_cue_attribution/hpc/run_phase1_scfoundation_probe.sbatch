#!/usr/bin/env bash
#SBATCH --job-name=trustcue-p1-scf-probe
#SBATCH --output=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-p1-scf-probe-%j.out
#SBATCH --error=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-p1-scf-probe-%j.err
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
PYTHON="${PYTHON:-/usr/bin/python3.12}"
OUT_DIR="${OUT_DIR:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/phase1_preflight}"
SCFOUNDATION_DIR="${SCFOUNDATION_DIR:-}"
SCFOUNDATION_CHECKPOINT="${SCFOUNDATION_CHECKPOINT:-}"
SCFOUNDATION_GENE_INDEX="${SCFOUNDATION_GENE_INDEX:-}"
PHASE1_INPUT_DATA="${PHASE1_INPUT_DATA:-}"
PHASE1_OUTPUT_DIR="${PHASE1_OUTPUT_DIR:-$OUT_DIR/generated}"

mkdir -p "$OUT_DIR" "$PHASE1_OUTPUT_DIR" "$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/logs"
cd "$PROJECT_ROOT"

echo "PROJECT_ROOT=$PROJECT_ROOT"
echo "PYTHON=$PYTHON"
echo "OUT_DIR=$OUT_DIR"
echo "SCFOUNDATION_DIR=$SCFOUNDATION_DIR"
echo "SCFOUNDATION_CHECKPOINT=$SCFOUNDATION_CHECKPOINT"
echo "SCFOUNDATION_GENE_INDEX=$SCFOUNDATION_GENE_INDEX"
echo "PHASE1_INPUT_DATA=$PHASE1_INPUT_DATA"
echo "PHASE1_OUTPUT_DIR=$PHASE1_OUTPUT_DIR"

"$PYTHON" -m unittest discover -s experiments/trust_cue_attribution/tests

"$PYTHON" experiments/trust_cue_attribution/run.py phase1-preflight \
  --out "$OUT_DIR/scfoundation_contract.json"

"$PYTHON" experiments/trust_cue_attribution/run.py phase1-feasibility \
  --scfoundation-dir "$SCFOUNDATION_DIR" \
  --checkpoint "$SCFOUNDATION_CHECKPOINT" \
  --gene-index "$SCFOUNDATION_GENE_INDEX" \
  --input-data "$PHASE1_INPUT_DATA" \
  --output-dir "$PHASE1_OUTPUT_DIR" \
  --out "$OUT_DIR/scfoundation_feasibility.json"

status="$("$PYTHON" -c 'import json, sys; print(json.load(open(sys.argv[1]))["status"])' "$OUT_DIR/scfoundation_feasibility.json")"
echo "PHASE1_SCF_PROBE_STATUS=$status"
echo "TRUST_CUE_PHASE1_SCF_PROBE_OK"
