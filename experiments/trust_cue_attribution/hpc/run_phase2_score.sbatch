#!/usr/bin/env bash
# Phase 2 scoring: after the Boltz prediction batch, compute lDDT truth ->
# assemble gate records -> run the offline calibration gate. Submit chained:
#   sbatch --dependency=afterok:<predict_job_id> run_phase2_score.sbatch
# so the Phase 2 gate result is produced unattended once predictions finish.
#
#SBATCH --job-name=trustcue-p2-score
#SBATCH --output=experiments/trust_cue_attribution/hpc_outputs/logs/p2-score-%j.out
#SBATCH --error=experiments/trust_cue_attribution/hpc_outputs/logs/p2-score-%j.err
#SBATCH --time=02:00:00
#SBATCH --partition=scu-cpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
PY="$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/envs/boltz-py312/bin/python"
T="$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/phase2_targets"
GATE_OUT="experiments/trust_cue_attribution/results/phase2_preflight/calibration_gate.json"
cd "$PROJECT_ROOT"
mkdir -p "$(dirname "$GATE_OUT")"

echo "=== 1) CA-lDDT truth vs experimental references ==="
"$PY" experiments/trust_cue_attribution/phase2_truth.py \
  --targets "$T/targets.jsonl" --reference-dir "$T/reference" --pred-dir "$T/predictions" \
  --out "$T/truth.jsonl"

echo "=== 2) assemble gate records (Boltz confidence + truth) ==="
"$PY" experiments/trust_cue_attribution/phase2_records.py \
  --boltz-out-dir "$T/predictions" --targets "$T/targets.jsonl" --truth "$T/truth.jsonl" \
  --out "$T/records.jsonl"

echo "=== 3) offline calibration gate (lambda 0.5) ==="
"$PY" - <<PY
import sys
sys.path.insert(0, "experiments/trust_cue_attribution")
from phase2_calibration_gate import read_records, write_phase2_calibration_gate
gate = write_phase2_calibration_gate(read_records("$T/records.jsonl"), "$GATE_OUT", lam=0.5)
print("PHASE2_GATE_DECISION:", gate["decision"])
print("wrong_risk_auroc:", gate["signal_validity"]["wrong_risk_auroc"])
print("scope:", gate["scope"])
print("margins:", gate["margins"])
PY

echo "TRUST_CUE_PHASE2_SCORE_OK"
