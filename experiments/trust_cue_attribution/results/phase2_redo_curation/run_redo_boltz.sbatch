#!/bin/bash
#SBATCH --job-name=p2redo-boltz
#SBATCH --output=/scratch/USER/LLM_SFM_interpretability/experiments/trust_cue_attribution/hpc_outputs/logs/p2redo-boltz-%j.out
#SBATCH --error=/scratch/USER/LLM_SFM_interpretability/experiments/trust_cue_attribution/hpc_outputs/logs/p2redo-boltz-%j.err
#SBATCH --time=16:00:00
#SBATCH --partition=scu-gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
set -uo pipefail
ENV=/scratch/USER/LLM_SFM_interpretability/experiments/trust_cue_attribution/hpc_outputs/envs/boltz-py312
WORK=/scratch/USER/LLM_SFM_interpretability/experiments/trust_cue_attribution/hpc_outputs/phase2_redo
export BOLTZ_CACHE=/scratch/USER/boltz_cache
mkdir -p "$WORK/predictions"
n=0
for fasta in "$WORK"/fasta/*.fasta; do
  tid=$(basename "$fasta" .fasta); n=$((n+1))
  outdir="$WORK/predictions/$tid"
  if ls "$outdir"/boltz_results_*/predictions/"$tid"/confidence_*_model_0.json >/dev/null 2>&1; then
    echo "[$n] $tid already done -- skip"; continue
  fi
  echo "[$n] predicting $tid ..."
  "$ENV/bin/boltz" predict "$fasta" --out_dir "$outdir" --cache "$BOLTZ_CACHE" --use_msa_server \
    --accelerator gpu --model boltz2 --no_kernels --override --output_format mmcif || echo "[$n] $tid FAILED"
done
echo ALL_DONE
