#!/usr/bin/env bash
# Build an isolated Cayuga/Expanse env for Phase 2 Boltz structure prediction.
#
# Boltz (MIT, reproduces AlphaFold3; emits pLDDT/PAE/pTM/ipTM) needs Python >=
# 3.10. Cayuga login provides /usr/bin/python3.12, so a plain venv is enough (no
# conda required). Writes under hpc_outputs/envs by default and does not touch
# existing environments. Run on the login node; `boltz predict` itself needs a
# GPU job (see run_phase2_boltz_predict.sbatch). Model weights are downloaded by
# Boltz on first predict, not here.

set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$PWD}"
ENV_PREFIX="${ENV_PREFIX:-$PROJECT_ROOT/experiments/trust_cue_attribution/hpc_outputs/envs/boltz-py312}"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3.12}"

echo "PROJECT_ROOT=$PROJECT_ROOT"
echo "ENV_PREFIX=$ENV_PREFIX"
echo "PYTHON_BIN=$PYTHON_BIN"
"$PYTHON_BIN" --version

if [ ! -x "$ENV_PREFIX/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$ENV_PREFIX"
fi

"$ENV_PREFIX/bin/python" -m pip install --upgrade pip setuptools wheel
"$ENV_PREFIX/bin/python" -m pip install boltz

"$ENV_PREFIX/bin/python" - <<'PY'
import sys
print("python", sys.version.split()[0])
import boltz
print("boltz", getattr(boltz, "__version__", "unknown"))
try:
    import torch
    print("torch", torch.__version__, "cuda_build", torch.version.cuda,
          "cuda_available", torch.cuda.is_available())
except Exception as exc:  # torch import on a CPU login node is fine to note
    print("torch import note:", exc)
PY

echo "TRUST_CUE_PHASE2_BOLTZ_ENV_BUILD_OK"
