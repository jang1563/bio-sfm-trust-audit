#!/usr/bin/env bash
#SBATCH --job-name=trustcue-p1-scf-env
#SBATCH --output=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-p1-scf-env-%j.out
#SBATCH --error=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-p1-scf-env-%j.err
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=12G

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
PYTHON="${PYTHON:-/usr/bin/python3.12}"
OUT_DIR="${OUT_DIR:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/phase1_preflight}"
SCFOUNDATION_DIR="${SCFOUNDATION_DIR:-}"
SCFOUNDATION_CHECKPOINT="${SCFOUNDATION_CHECKPOINT:-}"

mkdir -p "$OUT_DIR" "$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/logs"
cd "$PROJECT_ROOT"

echo "PROJECT_ROOT=$PROJECT_ROOT"
echo "PYTHON=$PYTHON"
echo "OUT_DIR=$OUT_DIR"
echo "SCFOUNDATION_DIR=$SCFOUNDATION_DIR"
echo "SCFOUNDATION_CHECKPOINT=$SCFOUNDATION_CHECKPOINT"
echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-}"
command -v nvidia-smi || true
nvidia-smi -L || true

export PYTHONNOUSERSITE=1

"$PYTHON" -m unittest discover -s experiments/trust_cue_attribution/tests

"$PYTHON" experiments/trust_cue_attribution/run.py phase1-inference-env \
  --scfoundation-dir "$SCFOUNDATION_DIR" \
  --checkpoint "$SCFOUNDATION_CHECKPOINT" \
  --out "$OUT_DIR/scfoundation_inference_env.json"

status="$("$PYTHON" -c 'import json, sys; print(json.load(open(sys.argv[1]))["status"])' "$OUT_DIR/scfoundation_inference_env.json")"
echo "PHASE1_SCF_INFERENCE_ENV_STATUS=$status"
if [ "$status" != "ready_for_inference_smoke" ]; then
  echo "Phase 1 scFoundation inference environment is not ready: $status" >&2
  exit 3
fi
echo "TRUST_CUE_PHASE1_SCF_INFERENCE_ENV_OK"
