#!/usr/bin/env bash
#SBATCH --job-name=trustcue-p1b-pool
#SBATCH --output=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-p1b-pool-%j.out
#SBATCH --error=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-p1b-pool-%j.err
#SBATCH --time=03:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=96G

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
PYTHON="${PYTHON:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/envs/scfoundation-smoke-py39/bin/python}"
OUT_DIR="${OUT_DIR:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/phase1b_edge_neighbor}"
POOL_OUT="${POOL_OUT:-$OUT_DIR/embedding_pool.json}"
POOL_REPORT_OUT="${POOL_REPORT_OUT:-$OUT_DIR/embedding_pool_report.json}"
NEIGHBOR_REPORT_OUT="${NEIGHBOR_REPORT_OUT:-$PROJECT_ROOT/experiments/trust_cue_attribution/results/phase1b_edge_neighbor/neighbor_signal_report.json}"
SCFOUNDATION_DIR="${SCFOUNDATION_DIR:-/scratch/USER/huggingface/benchmark/scFoundation}"
PHASE1B_INPUT_DATA="${PHASE1B_INPUT_DATA:-/scratch/USER/nomos/data/norman_2019.h5ad}"
PANELS="${PANELS:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl}"
PHASE1A_MANIFEST="${PHASE1A_MANIFEST:-$PROJECT_ROOT/experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json}"
MAX_CELLS_PER_PANEL="${MAX_CELLS_PER_PANEL:-12}"
MAX_CONTROL_CELLS="${MAX_CONTROL_CELLS:-128}"
K_NEIGHBORS="${K_NEIGHBORS:-10}"
SEED="${SEED:-41}"

mkdir -p "$OUT_DIR" "$(dirname "$NEIGHBOR_REPORT_OUT")" "$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/logs"
cd "$PROJECT_ROOT"

echo "PROJECT_ROOT=$PROJECT_ROOT"
echo "PYTHON=$PYTHON"
echo "OUT_DIR=$OUT_DIR"
echo "POOL_OUT=$POOL_OUT"
echo "POOL_REPORT_OUT=$POOL_REPORT_OUT"
echo "NEIGHBOR_REPORT_OUT=$NEIGHBOR_REPORT_OUT"
echo "SCFOUNDATION_DIR=$SCFOUNDATION_DIR"
echo "PHASE1B_INPUT_DATA=$PHASE1B_INPUT_DATA"
echo "PANELS=$PANELS"
echo "PHASE1A_MANIFEST=$PHASE1A_MANIFEST"
echo "MAX_CELLS_PER_PANEL=$MAX_CELLS_PER_PANEL"
echo "MAX_CONTROL_CELLS=$MAX_CONTROL_CELLS"
echo "K_NEIGHBORS=$K_NEIGHBORS"
echo "SEED=$SEED"
echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-}"
command -v nvidia-smi || true
nvidia-smi -L || true

export PYTHONNOUSERSITE=1

"$PYTHON" -m unittest discover -s experiments/trust_cue_attribution/tests

"$PYTHON" experiments/trust_cue_attribution/run.py phase1b-embedding-pool \
  --scfoundation-dir "$SCFOUNDATION_DIR" \
  --input-data "$PHASE1B_INPUT_DATA" \
  --panels "$PANELS" \
  --out-dir "$OUT_DIR" \
  --pool-out "$POOL_OUT" \
  --report-out "$POOL_REPORT_OUT" \
  --max-cells-per-panel "$MAX_CELLS_PER_PANEL" \
  --max-control-cells "$MAX_CONTROL_CELLS" \
  --seed "$SEED"

pool_status="$("$PYTHON" -c 'import json, sys; print(json.load(open(sys.argv[1]))["status"])' "$POOL_REPORT_OUT")"
echo "PHASE1B_EMBEDDING_POOL_STATUS=$pool_status"
if [ "$pool_status" != "ready_for_phase1b_edge_neighbor_signals" ]; then
  echo "Phase 1B embedding pool did not reach target status: $pool_status" >&2
  exit 5
fi

"$PYTHON" experiments/trust_cue_attribution/run.py phase1b-neighbor-signals \
  --panels "$PANELS" \
  --manifest "$PHASE1A_MANIFEST" \
  --embedding-pool "$POOL_OUT" \
  --out "$NEIGHBOR_REPORT_OUT" \
  --k-neighbors "$K_NEIGHBORS" \
  --seed "$SEED"

neighbor_status="$("$PYTHON" -c 'import json, sys; print(json.load(open(sys.argv[1]))["status"])' "$NEIGHBOR_REPORT_OUT")"
echo "PHASE1B_NEIGHBOR_SIGNAL_STATUS=$neighbor_status"
if [ "$neighbor_status" != "phase1b_edge_neighbor_signal_diagnostic_ready" ]; then
  echo "Phase 1B neighbor signal diagnostic did not reach target status: $neighbor_status" >&2
  exit 6
fi

echo "TRUST_CUE_PHASE1B_EDGE_NEIGHBOR_OK"
