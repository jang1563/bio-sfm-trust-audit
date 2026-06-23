#!/usr/bin/env bash
#SBATCH --job-name=trustcue-llm
#SBATCH --output=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-llm-%j.out
#SBATCH --error=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-llm-%j.err
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
PYTHON="${PYTHON:-/usr/bin/python3.12}"
OUT_DIR="${OUT_DIR:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/phase0_smoke}"
PROVIDER="${PROVIDER:-anthropic_messages}"
MODEL="${MODEL:?Set MODEL to the LLM model name before submitting this job}"
LIMIT="${LIMIT:-24}"
DELAY="${DELAY:-0.2}"
LAM="${LAM:-0.5}"

REQUESTS="${REQUESTS:-$OUT_DIR/requests_full.jsonl}"
PANELS="${PANELS:-$OUT_DIR/panels_full.jsonl}"
PACKETS="${PACKETS:-$OUT_DIR/cue_packets_full.jsonl}"
EPISODES_OUT="${EPISODES_OUT:-$OUT_DIR/llm_${MODEL}_episodes_limit_${LIMIT}.jsonl}"
SCORES_OUT="${SCORES_OUT:-$OUT_DIR/llm_${MODEL}_scores_limit_${LIMIT}_lambda_${LAM}.json}"
export EPISODES_OUT SCORES_OUT

mkdir -p "$OUT_DIR" "$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/logs"
cd "$PROJECT_ROOT"

if [[ -f "$HOME/.api_keys" ]]; then
  set -a
  source "$HOME/.api_keys"
  set +a
fi

if [[ "$PROVIDER" == "openai_responses" && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY is required for PROVIDER=openai_responses" >&2
  exit 2
fi

if [[ "$PROVIDER" == "anthropic_messages" && -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ANTHROPIC_API_KEY is required for PROVIDER=anthropic_messages" >&2
  exit 2
fi

echo "PROJECT_ROOT=$PROJECT_ROOT"
echo "PYTHON=$PYTHON"
echo "PROVIDER=$PROVIDER"
echo "MODEL=$MODEL"
echo "LIMIT=$LIMIT"
echo "REQUESTS=$REQUESTS"
echo "EPISODES_OUT=$EPISODES_OUT"
echo "SCORES_OUT=$SCORES_OUT"

LIMIT_ARGS=()
if [[ "$LIMIT" != "all" ]]; then
  LIMIT_ARGS=(--limit "$LIMIT")
fi

"$PYTHON" experiments/trust_cue_attribution/run.py run-llm-episodes \
  --requests "$REQUESTS" \
  --provider "$PROVIDER" \
  --model "$MODEL" \
  --continue-on-error \
  --resume \
  --progress-every 1 \
  --delay "$DELAY" \
  --out "$EPISODES_OUT" \
  "${LIMIT_ARGS[@]}"

"$PYTHON" experiments/trust_cue_attribution/run.py score-episodes \
  --panels "$PANELS" \
  --packets "$PACKETS" \
  --episodes "$EPISODES_OUT" \
  --lam "$LAM" \
  --out "$SCORES_OUT"

"$PYTHON" -c '
import json
import os
from pathlib import Path

episodes = Path(os.environ["EPISODES_OUT"])
scores = Path(os.environ["SCORES_OUT"])
episode_count = sum(1 for _ in open(episodes)) if episodes.exists() else 0
score_payload = json.loads(scores.read_text()) if scores.exists() else {}
summary = {
    "episodes": episode_count,
    "scores": str(scores),
    "summary": score_payload.get("summary", {}),
}
print(json.dumps(summary, indent=2, sort_keys=True))
'

echo "TRUST_CUE_PHASE0_LLM_PILOT_OK"
