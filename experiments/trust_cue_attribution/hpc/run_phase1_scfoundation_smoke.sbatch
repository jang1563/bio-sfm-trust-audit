#!/usr/bin/env bash
#SBATCH --job-name=trustcue-p1-scf-smoke
#SBATCH --output=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-p1-scf-smoke-%j.out
#SBATCH --error=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-p1-scf-smoke-%j.err
#SBATCH --time=00:45:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
PYTHON="${PYTHON:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/envs/scfoundation-smoke-py39/bin/python}"
OUT_DIR="${OUT_DIR:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/phase1_scfoundation_smoke}"
REPORT_OUT="${REPORT_OUT:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/phase1_preflight/scfoundation_smoke_report.json}"
SCFOUNDATION_DIR="${SCFOUNDATION_DIR:-}"
PHASE1_INPUT_DATA="${PHASE1_INPUT_DATA:-}"
N_CELLS="${N_CELLS:-3}"

mkdir -p "$OUT_DIR" "$(dirname "$REPORT_OUT")" "$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/logs"
cd "$PROJECT_ROOT"

echo "PROJECT_ROOT=$PROJECT_ROOT"
echo "PYTHON=$PYTHON"
echo "OUT_DIR=$OUT_DIR"
echo "REPORT_OUT=$REPORT_OUT"
echo "SCFOUNDATION_DIR=$SCFOUNDATION_DIR"
echo "PHASE1_INPUT_DATA=$PHASE1_INPUT_DATA"
echo "N_CELLS=$N_CELLS"
echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-}"
command -v nvidia-smi || true
nvidia-smi -L || true

export PYTHONNOUSERSITE=1

"$PYTHON" -m unittest discover -s experiments/trust_cue_attribution/tests

"$PYTHON" experiments/trust_cue_attribution/run.py phase1-scfoundation-smoke \
  --scfoundation-dir "$SCFOUNDATION_DIR" \
  --input-data "$PHASE1_INPUT_DATA" \
  --out-dir "$OUT_DIR" \
  --report-out "$REPORT_OUT" \
  --n-cells "$N_CELLS"

status="$("$PYTHON" -c 'import json, sys; print(json.load(open(sys.argv[1]))["status"])' "$REPORT_OUT")"
echo "PHASE1_SCF_SMOKE_STATUS=$status"
if [ "$status" != "ready_for_internal_signal_summary_adapter" ]; then
  echo "Phase 1 scFoundation smoke did not reach target status: $status" >&2
  exit 4
fi
echo "TRUST_CUE_PHASE1_SCF_SMOKE_OK"
