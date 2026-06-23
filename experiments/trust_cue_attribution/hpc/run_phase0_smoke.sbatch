#!/usr/bin/env bash
#SBATCH --job-name=trustcue-p0
#SBATCH --output=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-p0-%j.out
#SBATCH --error=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-p0-%j.err
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
PYTHON="${PYTHON:-/usr/bin/python3.12}"
OUT_DIR="${OUT_DIR:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/phase0_smoke}"
SUBSTRATE_CSV="${SUBSTRATE_CSV:-$PROJECT_ROOT/data/external/Verify-or-Trust/gears_norman.csv}"
MARGINAL_CSV="${MARGINAL_CSV:-$PROJECT_ROOT/data/external/Causal_Grounding_Eval/labeled_marginal.csv}"

mkdir -p "$OUT_DIR" "$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/logs"
cd "$PROJECT_ROOT"

echo "PROJECT_ROOT=$PROJECT_ROOT"
echo "PYTHON=$PYTHON"
echo "SUBSTRATE_CSV=$SUBSTRATE_CSV"
echo "MARGINAL_CSV=$MARGINAL_CSV"
echo "OUT_DIR=$OUT_DIR"

"$PYTHON" -m unittest discover -s experiments/trust_cue_attribution/tests

"$PYTHON" experiments/trust_cue_attribution/run.py build-panels \
  --substrate "$SUBSTRATE_CSV" \
  --marginal "$MARGINAL_CSV" \
  --out "$OUT_DIR/panels_full.jsonl"

"$PYTHON" experiments/trust_cue_attribution/run.py build-panels \
  --substrate "$SUBSTRATE_CSV" \
  --marginal "$MARGINAL_CSV" \
  --require-additive \
  --out "$OUT_DIR/panels_additive.jsonl"

"$PYTHON" experiments/trust_cue_attribution/run.py cue-packets \
  --panels "$OUT_DIR/panels_full.jsonl" \
  --out "$OUT_DIR/cue_packets_full.jsonl"

"$PYTHON" experiments/trust_cue_attribution/run.py make-requests \
  --packets "$OUT_DIR/cue_packets_full.jsonl" \
  --template experiments/trust_cue_attribution/prompts/decision_prompt.md \
  --model phase0-request-template \
  --out "$OUT_DIR/requests_full.jsonl"

"$PYTHON" experiments/trust_cue_attribution/run.py run-llm-episodes \
  --requests "$OUT_DIR/requests_full.jsonl" \
  --provider mock_defer \
  --model mock-defer \
  --limit 12 \
  --out "$OUT_DIR/mock_defer_episodes_12.jsonl"

"$PYTHON" experiments/trust_cue_attribution/run.py score-episodes \
  --panels "$OUT_DIR/panels_full.jsonl" \
  --packets "$OUT_DIR/cue_packets_full.jsonl" \
  --episodes "$OUT_DIR/mock_defer_episodes_12.jsonl" \
  --out "$OUT_DIR/mock_defer_scores_12.json"

"$PYTHON" experiments/trust_cue_attribution/run.py simulate-episodes \
  --panels "$OUT_DIR/panels_full.jsonl" \
  --packets "$OUT_DIR/cue_packets_full.jsonl" \
  --policy signal_gated_verify \
  --out "$OUT_DIR/policy_signal_gated_episodes.jsonl"

"$PYTHON" experiments/trust_cue_attribution/run.py score-episodes \
  --panels "$OUT_DIR/panels_full.jsonl" \
  --packets "$OUT_DIR/cue_packets_full.jsonl" \
  --episodes "$OUT_DIR/policy_signal_gated_episodes.jsonl" \
  --out "$OUT_DIR/policy_signal_gated_scores.json"

"$PYTHON" experiments/trust_cue_attribution/run.py baselines \
  --panels "$OUT_DIR/panels_full.jsonl" \
  > "$OUT_DIR/baselines_full.json"

"$PYTHON" experiments/trust_cue_attribution/run.py baselines \
  --panels "$OUT_DIR/panels_additive.jsonl" \
  > "$OUT_DIR/baselines_additive.json"

"$PYTHON" - <<'PY'
import json
from pathlib import Path
import os

out = Path(os.environ.get("OUT_DIR", "experiments/trust_cue_attribution/hpc_outputs/phase0_smoke"))
panels_full = sum(1 for _ in open(out / "panels_full.jsonl"))
panels_additive = sum(1 for _ in open(out / "panels_additive.jsonl"))
cue_packets = sum(1 for _ in open(out / "cue_packets_full.jsonl"))
requests_full = sum(1 for _ in open(out / "requests_full.jsonl"))
mock_defer_episodes = sum(1 for _ in open(out / "mock_defer_episodes_12.jsonl"))
synthetic_episodes = sum(1 for _ in open(out / "policy_signal_gated_episodes.jsonl"))
summary = {
    "panels_full": panels_full,
    "panels_additive": panels_additive,
    "cue_packets_full": cue_packets,
    "requests_full": requests_full,
    "mock_defer_episodes_12": mock_defer_episodes,
    "policy_signal_gated_episodes": synthetic_episodes,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "TRUST_CUE_PHASE0_SMOKE_OK"
