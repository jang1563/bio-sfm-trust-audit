#!/usr/bin/env bash
# Phase 2 tiny Boltz GPU smoke: verify the torch(cu130)/GPU stack, MSA-server
# reachability, and capture a REAL confidence JSON to lock the records parser.
# Tiny monomer (ubiquitin, 76 aa). Not a scientific result -- wiring smoke only.
#
#SBATCH --job-name=trustcue-p2-boltz-smoke
#SBATCH --output=experiments/trust_cue_attribution/hpc_outputs/logs/p2-boltz-smoke-%j.out
#SBATCH --error=experiments/trust_cue_attribution/hpc_outputs/logs/p2-boltz-smoke-%j.err
#SBATCH --time=01:00:00
#SBATCH --partition=scu-gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
ENV="$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/envs/boltz-py312"
SMOKE="$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/phase2_boltz_smoke"
export BOLTZ_CACHE="${BOLTZ_CACHE:-/scratch/USER/boltz_cache}"

mkdir -p "$SMOKE" "$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/logs" "$BOLTZ_CACHE"
cd "$PROJECT_ROOT"

echo "=== node / GPU / torch CUDA check ==="
hostname
nvidia-smi -L || true
"$ENV/bin/python" -c "import torch; print('torch', torch.__version__, 'cuda_build', torch.version.cuda, 'cuda_available', torch.cuda.is_available()); assert torch.cuda.is_available(), 'CUDA NOT available on this node (torch cu130 vs node driver mismatch?) -- needs a torch/CUDA downgrade'"

cat > "$SMOKE/ubiquitin.fasta" <<'FASTA'
>A|protein
MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG
FASTA

echo "=== boltz predict (tiny monomer smoke) ==="
"$ENV/bin/boltz" predict "$SMOKE/ubiquitin.fasta" \
  --out_dir "$SMOKE/out" \
  --cache "$BOLTZ_CACHE" \
  --use_msa_server \
  --accelerator gpu \
  --model boltz2 \
  --no_kernels \
  --override \
  --output_format mmcif

echo "=== confidence JSON (real output schema) ==="
conf="$(find "$SMOKE/out" -name 'confidence_*_model_0.json' | head -1)"
echo "conf_path=$conf"
"$ENV/bin/python" -c "import json,sys; d=json.load(open(sys.argv[1])); print(json.dumps({k:d.get(k) for k in ['confidence_score','complex_plddt','complex_iplddt','ptm','iptm','protein_iptm']}, indent=2))" "$conf"

echo "TRUST_CUE_PHASE2_BOLTZ_SMOKE_OK"
