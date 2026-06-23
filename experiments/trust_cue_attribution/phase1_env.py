"""Phase 1 scFoundation inference environment probe.

This probe checks whether the selected HPC Python environment and GPU
allocation are ready to attempt a tiny scFoundation inference smoke. It does not
load model checkpoints or run inference.
"""

from __future__ import annotations

import importlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REQUIRED_INFERENCE_MODULES = [
    "numpy",
    "pandas",
    "scipy",
    "torch",
    "einops",
    "scanpy",
    "anndata",
    "h5py",
    "local_attention",
]


def build_scfoundation_inference_env_report(
    *,
    scfoundation_dir: str | None = None,
    checkpoint: str | None = None,
    require_cuda: bool = True,
    check_scfoundation_import: bool = True,
) -> dict[str, Any]:
    """Return a compact report for scFoundation inference readiness."""
    paths = _path_checks(scfoundation_dir=scfoundation_dir, checkpoint=checkpoint)
    modules = [_module_import_record(module) for module in REQUIRED_INFERENCE_MODULES]
    torch_info = _torch_info()
    nvidia_smi = _nvidia_smi_record()
    scfoundation_import = _scfoundation_import_record(
        scfoundation_dir=scfoundation_dir,
        enabled=check_scfoundation_import,
    )
    status = _readiness_status(
        paths=paths,
        modules=modules,
        torch_info=torch_info,
        scfoundation_import=scfoundation_import,
        require_cuda=require_cuda,
    )
    return {
        "phase": "phase1",
        "adapter": "ScFoundationAdapter",
        "status": status,
        "claim_boundary": "inference environment probe only; no checkpoint load, embedding, or LLM trust claim",
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "require_cuda": require_cuda,
        "paths": paths,
        "module_imports": modules,
        "torch": torch_info,
        "nvidia_smi": nvidia_smi,
        "scfoundation_import": scfoundation_import,
        "next_actions": _next_actions(status, modules, scfoundation_import),
    }


def write_scfoundation_inference_env_report(out: str, **kwargs) -> dict[str, Any]:
    report = build_scfoundation_inference_env_report(**kwargs)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return report


def _path_checks(*, scfoundation_dir: str | None, checkpoint: str | None) -> dict[str, Any]:
    return {
        "scfoundation_dir": _path_record(scfoundation_dir, "dir"),
        "model_dir": _path_record(_join(scfoundation_dir, "model"), "dir"),
        "load_py": _path_record(_join(scfoundation_dir, "model", "load.py"), "file"),
        "get_embedding_py": _path_record(_join(scfoundation_dir, "model", "get_embedding.py"), "file"),
        "checkpoint": _path_record(checkpoint, "file"),
    }


def _path_record(path: str | None, kind: str) -> dict[str, Any]:
    if not path:
        return {
            "path": None,
            "kind": kind,
            "exists": False,
            "matches_kind": False,
        }
    candidate = Path(path)
    exists = candidate.exists()
    if kind == "file":
        matches_kind = candidate.is_file()
    elif kind == "dir":
        matches_kind = candidate.is_dir()
    else:
        raise ValueError(f"unknown path kind {kind!r}")
    return {
        "path": path,
        "kind": kind,
        "exists": exists,
        "matches_kind": matches_kind,
    }


def _module_import_record(module: str, timeout: int = 20) -> dict[str, Any]:
    code = (
        "import importlib, importlib.metadata, json, sys\n"
        f"module = {module!r}\n"
        "try:\n"
        "    imported = importlib.import_module(module)\n"
        "    try:\n"
        "        version = importlib.metadata.version(module.replace('_', '-'))\n"
        "    except Exception:\n"
        "        version = str(getattr(imported, '__version__', 'unknown'))\n"
        "    print(json.dumps({'ok': True, 'version': version, 'file': str(getattr(imported, '__file__', ''))}))\n"
        "except Exception as exc:\n"
        "    print(json.dumps({'ok': False, 'error': f'{type(exc).__name__}: {exc}'}))\n"
        "    sys.exit(0)\n"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
        if not payload.get("ok"):
            return {
                "module": module,
                "ok": False,
                "version": None,
                "file": None,
                "error": payload.get("error", "unknown import error"),
            }
        return {
            "module": module,
            "ok": True,
            "version": payload.get("version"),
            "file": payload.get("file"),
            "error": None,
        }
    except subprocess.TimeoutExpired:
        return {
            "module": module,
            "ok": False,
            "version": None,
            "file": None,
            "error": f"TimeoutExpired: import exceeded {timeout} seconds",
        }
    except Exception as exc:
        return {
            "module": module,
            "ok": False,
            "version": None,
            "file": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _torch_info() -> dict[str, Any]:
    try:
        import torch  # type: ignore
    except Exception as exc:
        return {
            "import_ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    cuda_available = bool(torch.cuda.is_available())
    device_count = int(torch.cuda.device_count()) if cuda_available else 0
    device_names = []
    for idx in range(device_count):
        try:
            device_names.append(torch.cuda.get_device_name(idx))
        except Exception as exc:  # pragma: no cover - GPU driver dependent.
            device_names.append(f"unreadable_device_{idx}: {type(exc).__name__}: {exc}")
    return {
        "import_ok": True,
        "version": str(getattr(torch, "__version__", "unknown")),
        "cuda_version": str(getattr(torch.version, "cuda", None)),
        "cuda_available": cuda_available,
        "cuda_device_count": device_count,
        "cuda_device_names": device_names,
    }


def _nvidia_smi_record() -> dict[str, Any]:
    binary = shutil.which("nvidia-smi")
    if not binary:
        return {
            "available": False,
            "returncode": None,
            "stdout": "",
            "stderr": "nvidia-smi not found",
        }
    try:
        proc = subprocess.run(
            [binary, "-L"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        return {
            "available": True,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except Exception as exc:  # pragma: no cover - system dependent.
        return {
            "available": True,
            "returncode": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
        }


def _scfoundation_import_record(*, scfoundation_dir: str | None, enabled: bool) -> dict[str, Any]:
    if not enabled:
        return {
            "enabled": False,
            "ok": None,
            "error": None,
        }
    model_dir = Path(scfoundation_dir).joinpath("model") if scfoundation_dir else None
    if not model_dir or not model_dir.is_dir():
        return {
            "enabled": True,
            "ok": False,
            "error": "missing_model_dir",
        }
    old_path = list(sys.path)
    try:
        sys.path.insert(0, str(model_dir))
        importlib.import_module("load")
        return {
            "enabled": True,
            "ok": True,
            "error": None,
        }
    except Exception as exc:
        return {
            "enabled": True,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        sys.path = old_path
        sys.modules.pop("load", None)


def _readiness_status(
    *,
    paths: dict[str, Any],
    modules: list[dict[str, Any]],
    torch_info: dict[str, Any],
    scfoundation_import: dict[str, Any],
    require_cuda: bool,
) -> str:
    missing_paths = [name for name, row in paths.items() if not row["matches_kind"]]
    if missing_paths:
        return "blocked_missing_artifacts"
    missing_modules = [row["module"] for row in modules if not row["ok"]]
    if missing_modules:
        return "blocked_missing_or_broken_modules"
    if require_cuda and not torch_info.get("cuda_available"):
        return "blocked_no_cuda_visible"
    if scfoundation_import.get("enabled") and not scfoundation_import.get("ok"):
        return "blocked_scfoundation_import"
    if not require_cuda and not torch_info.get("cuda_available"):
        return "ready_for_gpu_env_probe"
    return "ready_for_inference_smoke"


def _next_actions(status: str, modules: list[dict[str, Any]], scfoundation_import: dict[str, Any]) -> list[str]:
    if status == "ready_for_inference_smoke":
        return [
            "Run a tiny scFoundation embedding smoke on one to five cells.",
            "Write compact internal-signal summaries only; keep large embeddings under hpc_outputs.",
        ]
    if status == "ready_for_gpu_env_probe":
        return [
            "Run this same environment probe inside a GPU Slurm allocation.",
            "If CUDA is visible there, proceed to a tiny scFoundation embedding smoke.",
        ]
    if status == "blocked_missing_or_broken_modules":
        missing = [row["module"] for row in modules if not row["ok"]]
        return [
            f"Install or select an environment with importable modules: {', '.join(missing)}.",
            "Prefer fixing the environment before modifying scFoundation code.",
        ]
    if status == "blocked_no_cuda_visible":
        return [
            "Submit this probe inside a GPU Slurm allocation.",
            "For Cayuga use a GPU partition such as scu-gpu or preempt_gpu with one GPU.",
        ]
    if status == "blocked_scfoundation_import":
        return [
            f"Fix scFoundation model import error: {scfoundation_import.get('error')}.",
            "Likely causes include missing local_attention or incompatible torch/numpy/scipy versions.",
        ]
    return [
        "Stage the scFoundation repo, model directory, load.py, get_embedding.py, and checkpoint before retrying.",
    ]


def _join(base: str | None, *parts: str) -> str | None:
    if not base:
        return None
    return str(Path(base).joinpath(*parts))
