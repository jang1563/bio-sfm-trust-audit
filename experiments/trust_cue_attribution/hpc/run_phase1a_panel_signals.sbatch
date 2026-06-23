#!/usr/bin/env bash
#SBATCH --job-name=trustcue-p1a-panel
#SBATCH --output=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-p1a-panel-%j.out
#SBATCH --error=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-p1a-panel-%j.err
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=64G

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
PYTHON="${PYTHON:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/envs/scfoundation-smoke-py39/bin/python}"
OUT_DIR="${OUT_DIR:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/phase1a_panel_signals}"
REPORT_OUT="${REPORT_OUT:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/phase1a_panel_signals/panel_signal_report.json}"
SCFOUNDATION_DIR="${SCFOUNDATION_DIR:-}"
PHASE1A_INPUT_DATA="${PHASE1A_INPUT_DATA:-}"
PHASE1A_MANIFEST="${PHASE1A_MANIFEST:-$PROJECT_ROOT/experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json}"
MAX_CELLS_PER_PANEL="${MAX_CELLS_PER_PANEL:-16}"
MAX_CONTROL_CELLS="${MAX_CONTROL_CELLS:-64}"
SEED="${SEED:-37}"

mkdir -p "$OUT_DIR" "$(dirname "$REPORT_OUT")" "$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/logs"
cd "$PROJECT_ROOT"

echo "PROJECT_ROOT=$PROJECT_ROOT"
echo "PYTHON=$PYTHON"
echo "OUT_DIR=$OUT_DIR"
echo "REPORT_OUT=$REPORT_OUT"
echo "SCFOUNDATION_DIR=$SCFOUNDATION_DIR"
echo "PHASE1A_INPUT_DATA=$PHASE1A_INPUT_DATA"
echo "PHASE1A_MANIFEST=$PHASE1A_MANIFEST"
echo "MAX_CELLS_PER_PANEL=$MAX_CELLS_PER_PANEL"
echo "MAX_CONTROL_CELLS=$MAX_CONTROL_CELLS"
echo "SEED=$SEED"
echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-}"
command -v nvidia-smi || true
nvidia-smi -L || true

export PYTHONNOUSERSITE=1

"$PYTHON" -m unittest discover -s experiments/trust_cue_attribution/tests

"$PYTHON" experiments/trust_cue_attribution/run.py phase1a-panel-signals \
  --scfoundation-dir "$SCFOUNDATION_DIR" \
  --input-data "$PHASE1A_INPUT_DATA" \
  --phase1a-manifest "$PHASE1A_MANIFEST" \
  --out-dir "$OUT_DIR" \
  --report-out "$REPORT_OUT" \
  --max-cells-per-panel "$MAX_CELLS_PER_PANEL" \
  --max-control-cells "$MAX_CONTROL_CELLS" \
  --seed "$SEED"

status="$("$PYTHON" -c 'import json, sys; print(json.load(open(sys.argv[1]))["status"])' "$REPORT_OUT")"
echo "PHASE1A_PANEL_SIGNAL_STATUS=$status"
if [ "$status" != "ready_for_phase1a_panel_specific_signal_packets" ]; then
  echo "Phase 1A panel-specific signal report did not reach target status: $status" >&2
  exit 5
fi
echo "TRUST_CUE_PHASE1A_PANEL_SIGNAL_OK"
