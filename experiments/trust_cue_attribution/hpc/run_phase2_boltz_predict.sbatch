#!/usr/bin/env bash
# Phase 2 Boltz-2 prediction over the curated RCSB target set (validated command;
# --no_kernels avoids the absent cuequivariance kernel under cu13). Resumable:
# re-submitting skips targets that already have a confidence JSON. Each target's
# predictions go under $PRED/<target_id>/ so phase2_records.py (pointed at $PRED)
# finds confidence_<id>_model_0.json per target.
#
#SBATCH --job-name=trustcue-p2-boltz-predict
#SBATCH --output=experiments/trust_cue_attribution/hpc_outputs/logs/p2-boltz-predict-%j.out
#SBATCH --error=experiments/trust_cue_attribution/hpc_outputs/logs/p2-boltz-predict-%j.err
#SBATCH --time=16:00:00
#SBATCH --partition=scu-gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
ENV="$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/envs/boltz-py312"
TARGETS="${TARGETS:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/phase2_targets}"
PRED="${PRED:-$TARGETS/predictions}"
export BOLTZ_CACHE="${BOLTZ_CACHE:-/scratch/USER/boltz_cache}"

mkdir -p "$PRED" "$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/logs" "$BOLTZ_CACHE"
cd "$PROJECT_ROOT"

nvidia-smi -L || true
"$ENV/bin/python" -c "import torch; assert torch.cuda.is_available(), 'no CUDA on node'"

n=0; ok=0; fail=0
for fasta in "$TARGETS"/fasta/*.fasta; do
  [ -e "$fasta" ] || { echo "no FASTAs under $TARGETS/fasta"; exit 4; }
  tid="$(basename "$fasta" .fasta)"
  n=$((n+1))
  outdir="$PRED/$tid"
  if ls "$outdir"/boltz_results_*/predictions/"$tid"/confidence_*_model_0.json >/dev/null 2>&1; then
    echo "[$n] $tid already done -- skip"; ok=$((ok+1)); continue
  fi
  echo "[$n] predicting $tid ..."
  if "$ENV/bin/boltz" predict "$fasta" \
       --out_dir "$outdir" --cache "$BOLTZ_CACHE" --use_msa_server \
       --accelerator gpu --model boltz2 --no_kernels --override --output_format mmcif; then
    ok=$((ok+1))
  else
    echo "[$n] $tid FAILED (continuing)"; fail=$((fail+1))
  fi
done

echo "PHASE2_BOLTZ_PREDICT_SUMMARY n=$n ok=$ok fail=$fail"
echo "TRUST_CUE_PHASE2_BOLTZ_PREDICT_OK"
