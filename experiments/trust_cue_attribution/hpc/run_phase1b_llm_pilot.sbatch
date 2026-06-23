#!/usr/bin/env bash
#SBATCH --job-name=trustcue-p1b-llm
#SBATCH --output=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-p1b-llm-%j.out
#SBATCH --error=experiments/trust_cue_attribution/hpc_outputs/logs/trustcue-p1b-llm-%j.err
#SBATCH --time=03:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
PYTHON="${PYTHON:-/usr/bin/python3.12}"
OUT_DIR="${OUT_DIR:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/phase1b_signal_pilot}"
RESULTS_DIR="${RESULTS_DIR:-$PROJECT_ROOT/experiments/trust_cue_attribution/results/phase1b_signal_pilot}"
PROVIDER="${PROVIDER:-anthropic_messages}"
MODEL="${MODEL:-claude-sonnet-4-6}"
DELAY="${DELAY:-0.2}"
EXPECTED_REQUESTS="${EXPECTED_REQUESTS:-48}"

PANELS="${PANELS:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl}"
NEIGHBOR_REPORT="${NEIGHBOR_REPORT:-$PROJECT_ROOT/experiments/trust_cue_attribution/results/phase1b_edge_neighbor/neighbor_signal_report.json}"
PACKETS="${PACKETS:-$OUT_DIR/phase1b_signal_packets.jsonl}"
REQUESTS="${REQUESTS:-$OUT_DIR/requests_phase1b_signal_pilot.jsonl}"
MANIFEST_OUT="${MANIFEST_OUT:-$RESULTS_DIR/manifest.json}"
EPISODES_OUT="${EPISODES_OUT:-$OUT_DIR/llm_${MODEL}_phase1b_signal_pilot_episodes.jsonl}"
ANALYSIS_OUT="${ANALYSIS_OUT:-$OUT_DIR/llm_${MODEL}_phase1b_signal_pilot_analysis.json}"
TRAJECTORIES_OUT="${TRAJECTORIES_OUT:-$OUT_DIR/llm_${MODEL}_phase1b_signal_pilot_trajectories.jsonl}"
TRAJECTORY_SUMMARY_OUT="${TRAJECTORY_SUMMARY_OUT:-$OUT_DIR/llm_${MODEL}_phase1b_signal_pilot_trajectory_summary.json}"
export EPISODES_OUT

mkdir -p "$OUT_DIR" "$RESULTS_DIR" "$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/logs"
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
echo "OUT_DIR=$OUT_DIR"
echo "RESULTS_DIR=$RESULTS_DIR"
echo "PANELS=$PANELS"
echo "NEIGHBOR_REPORT=$NEIGHBOR_REPORT"
echo "PACKETS=$PACKETS"
echo "REQUESTS=$REQUESTS"
echo "EPISODES_OUT=$EPISODES_OUT"
echo "EXPECTED_REQUESTS=$EXPECTED_REQUESTS"

"$PYTHON" -m unittest discover -s experiments/trust_cue_attribution/tests

"$PYTHON" experiments/trust_cue_attribution/run.py phase1b-signal-packets \
  --panels "$PANELS" \
  --neighbor-report "$NEIGHBOR_REPORT" \
  --out "$PACKETS" \
  --manifest-out "$MANIFEST_OUT"

"$PYTHON" experiments/trust_cue_attribution/run.py make-requests \
  --packets "$PACKETS" \
  --template experiments/trust_cue_attribution/prompts/decision_prompt.md \
  --model "$MODEL" \
  --out "$REQUESTS"

request_count="$("$PYTHON" -c 'import sys; print(sum(1 for line in open(sys.argv[1]) if line.strip()))' "$REQUESTS")"
if [[ "$request_count" != "$EXPECTED_REQUESTS" ]]; then
  echo "Expected $EXPECTED_REQUESTS requests, observed $request_count in $REQUESTS" >&2
  exit 3
fi

"$PYTHON" experiments/trust_cue_attribution/run.py run-llm-episodes \
  --requests "$REQUESTS" \
  --provider "$PROVIDER" \
  --model "$MODEL" \
  --continue-on-error \
  --resume \
  --progress-every 1 \
  --delay "$DELAY" \
  --out "$EPISODES_OUT"

episode_count="$("$PYTHON" -c 'import sys; print(sum(1 for line in open(sys.argv[1]) if line.strip()))' "$EPISODES_OUT")"
if [[ "$episode_count" != "$EXPECTED_REQUESTS" ]]; then
  echo "Expected $EXPECTED_REQUESTS episodes, observed $episode_count in $EPISODES_OUT" >&2
  exit 4
fi

"$PYTHON" experiments/trust_cue_attribution/run.py analyze-episodes \
  --episodes "$EPISODES_OUT" \
  --out "$ANALYSIS_OUT"

for lam in 0.2 0.5 0.8; do
  "$PYTHON" experiments/trust_cue_attribution/run.py score-episodes \
    --panels "$PANELS" \
    --packets "$PACKETS" \
    --episodes "$EPISODES_OUT" \
    --lam "$lam" \
    --out "$OUT_DIR/llm_${MODEL}_phase1b_signal_pilot_scores_lambda_${lam}.json"

  "$PYTHON" experiments/trust_cue_attribution/run.py paired-cue-effects \
    --panels "$PANELS" \
    --packets "$PACKETS" \
    --episodes "$EPISODES_OUT" \
    --lam "$lam" \
    --baseline-cue no_internal_signal \
    --out "$OUT_DIR/llm_${MODEL}_phase1b_signal_pilot_paired_effects_lambda_${lam}.json"
done

"$PYTHON" experiments/trust_cue_attribution/run.py cue-attribution \
  --panels "$PANELS" \
  --packets "$PACKETS" \
  --episodes "$EPISODES_OUT" \
  --lam 0.5 \
  --baseline-cue no_internal_signal \
  --out "$OUT_DIR/llm_${MODEL}_phase1b_signal_pilot_cue_attribution.json"

"$PYTHON" experiments/trust_cue_attribution/run.py explanation-faithfulness \
  --panels "$PANELS" \
  --packets "$PACKETS" \
  --episodes "$EPISODES_OUT" \
  --lam 0.5 \
  --baseline-cue no_internal_signal \
  --out "$OUT_DIR/llm_${MODEL}_phase1b_signal_pilot_explanation_faithfulness.json"

"$PYTHON" experiments/trust_cue_attribution/run.py episodes-to-trajectories \
  --panels "$PANELS" \
  --packets "$PACKETS" \
  --episodes "$EPISODES_OUT" \
  --lam 0.5 \
  --out "$TRAJECTORIES_OUT"

"$PYTHON" experiments/trust_cue_attribution/run.py summarize-trajectories \
  --trajectories "$TRAJECTORIES_OUT" \
  --out "$TRAJECTORY_SUMMARY_OUT"

echo "TRUST_CUE_PHASE1B_LLM_PILOT_OK"
