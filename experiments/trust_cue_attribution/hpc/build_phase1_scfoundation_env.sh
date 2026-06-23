#!/usr/bin/env bash
# Build an isolated Cayuga/Expanse env for Phase 1 scFoundation smoke tests.
#
# This script writes under hpc_outputs/envs by default. It does not modify
# existing user conda environments.

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
ENV_PREFIX="${ENV_PREFIX:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/envs/scfoundation-smoke-py39}"
CONDA_BIN="${CONDA_BIN:-/scratch/USER/home_overflow/miniconda3/miniconda3/bin/conda}"
PYTHON_VERSION="${PYTHON_VERSION:-3.9}"

echo "PROJECT_ROOT=$PROJECT_ROOT"
echo "ENV_PREFIX=$ENV_PREFIX"
echo "CONDA_BIN=$CONDA_BIN"
echo "PYTHON_VERSION=$PYTHON_VERSION"

if [ ! -x "$CONDA_BIN" ]; then
  echo "Conda binary is not executable: $CONDA_BIN" >&2
  exit 2
fi

if [ ! -x "$ENV_PREFIX/bin/python" ]; then
  "$CONDA_BIN" create -y -p "$ENV_PREFIX" "python=$PYTHON_VERSION" pip
fi

"$ENV_PREFIX/bin/python" -m pip install --upgrade pip setuptools wheel

"$ENV_PREFIX/bin/python" -m pip install \
  "numpy<2" \
  pandas \
  scipy \
  h5py \
  anndata \
  scanpy \
  einops \
  tqdm \
  local-attention \
  torch

"$ENV_PREFIX/bin/python" - <<'PY'
mods = ["numpy", "pandas", "scipy", "h5py", "anndata", "scanpy", "einops", "torch", "local_attention"]
for module in mods:
    imported = __import__(module)
    print(module, getattr(imported, "__version__", "unknown"))

import torch
print("torch_cuda_version", torch.version.cuda)
print("torch_cuda_available", torch.cuda.is_available())
PY

echo "TRUST_CUE_PHASE1_SCF_ENV_BUILD_OK"
