import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import psutil

from .config import ROOT

TORCH_PROBE = """
import importlib.util, json
if importlib.util.find_spec('torch') is None:
    print(json.dumps({'state': 'missing'}))
else:
    try:
        import torch
        available = torch.cuda.is_available()
        devices = []
        if available:
            for index in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(index)
                devices.append({'name': props.name, 'vramGb': round(props.total_memory / 1024**3, 2)})
        print(json.dumps({'state': 'ok', 'version': torch.__version__, 'cudaRuntime': torch.version.cuda,
                          'cudaAvailable': available, 'devices': devices}))
    except Exception as exc:
        print(json.dumps({'state': 'error', 'message': str(exc)[:300]}))
"""


def run_probe(command: list[str], timeout: int = 20):
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def inspect_environment(runner=run_probe) -> dict:
    checks = []

    def check(key, title, status, value, detail, action=""):
        checks.append({"id": key, "title": title, "status": status, "value": value, "detail": detail, "action": action})

    check("python", "Python runtime", "pass" if sys.version_info >= (3, 11) else "blocked", platform.python_version(),
          "Checks use the Python environment running this backend.", "Use Python 3.11 or newer." if sys.version_info < (3, 11) else "")
    packages = []
    for name in ("torch", "transformers", "datasets", "tokenizers", "accelerate", "peft"):
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            version = None
        packages.append({"name": name, "version": version, "required": name in {"torch", "transformers", "datasets", "tokenizers"}})

    torch_info = {"state": "error"}
    try:
        result = runner([sys.executable, "-I", "-c", TORCH_PROBE], timeout=20)
        if result.returncode != 0:
            raise RuntimeError("PyTorch probe exited unsuccessfully.")
        # Native libraries may print diagnostics before the JSON result.
        torch_info = json.loads(result.stdout.strip().splitlines()[-1])
        if torch_info.get("state") == "missing":
            check("pytorch", "PyTorch", "blocked", "Not installed", "PyTorch is not installed in the backend environment.", "Install a compatible PyTorch build into .venv using the official PyTorch installer instructions, then rerun checks.")
        elif torch_info.get("state") != "ok":
            check("pytorch", "PyTorch", "error", "Import failed", torch_info.get("message", "PyTorch could not be loaded."), "Check the installed build and its Python/driver compatibility, then rerun checks.")
        else:
            check("pytorch", "PyTorch", "pass", torch_info["version"], "PyTorch imported successfully in an isolated subprocess.")
    except subprocess.TimeoutExpired:
        check("pytorch", "PyTorch", "error", "Check timed out", "The PyTorch probe exceeded 20 seconds.", "Inspect the Python installation or GPU driver and rerun checks.")
    except (OSError, ValueError, IndexError, KeyError, RuntimeError):
        check("pytorch", "PyTorch", "error", "Check failed", "The isolated PyTorch probe did not return a valid result.", "Inspect the backend Python environment and rerun checks.")

    devices = torch_info.get("devices", [])
    if torch_info.get("state") != "ok":
        check("cuda", "PyTorch CUDA access", "blocked", "Not verified", "CUDA access cannot be checked until PyTorch imports successfully.", "Resolve the PyTorch check first. A driver-reported GPU alone does not verify training access.")
    elif torch_info.get("cudaAvailable"):
        check("cuda", "PyTorch CUDA access", "pass", f"CUDA {torch_info.get('cudaRuntime')}", f"{len(devices)} CUDA device(s) visible to PyTorch. Forward/backward testing is still a later milestone.")
    else:
        check("cuda", "PyTorch CUDA access", "blocked", "Unavailable", "PyTorch cannot currently access a CUDA GPU. CPU-only experiments remain possible.", "For CUDA training, check the NVIDIA driver and install a compatible CUDA-enabled PyTorch build.")

    driver_devices = []
    if shutil.which("nvidia-smi"):
        try:
            result = runner(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"], timeout=6)
            if result.returncode != 0:
                raise RuntimeError("Driver query failed")
            for line in result.stdout.strip().splitlines():
                name, memory, driver = [v.strip() for v in line.rsplit(",", 2)]
                driver_devices.append({"name": name, "vramGb": round(float(memory) / 1024, 2), "driver": driver})
            if not driver_devices:
                raise ValueError("No devices")
            check("driver", "NVIDIA driver", "pass", driver_devices[0]["driver"], f"{len(driver_devices)} GPU(s) reported by nvidia-smi. This is independent of PyTorch CUDA access.")
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            check("driver", "NVIDIA driver", "warning", "Query failed", "nvidia-smi is installed but the GPU query failed.", "Check the NVIDIA driver installation and GPU availability.")
    else:
        check("driver", "NVIDIA driver", "warning", "nvidia-smi not found", "No NVIDIA driver utility was found on the backend host.", "If this host should have an NVIDIA GPU, install/repair its driver. This check does not detect Apple or AMD accelerators.")

    memory = None
    try:
        measured = psutil.virtual_memory()
        memory = {"totalGb": round(measured.total / 1024**3, 2), "availableGb": round(measured.available / 1024**3, 2)}
        check("memory", "System memory", "pass", f"{memory['totalGb']} GB", f"{memory['availableGb']} GB available at check time. Model capacity is not estimated yet.")
    except (OSError, RuntimeError):
        check("memory", "System memory", "error", "Could not inspect", "The host did not provide memory information.", "Check host permissions and retry.")

    disk = None
    data_path = Path(os.getenv("STUDIO_DATA_DIR", str(ROOT))).expanduser()
    try:
        usage = shutil.disk_usage(data_path)
        disk = {"path": str(data_path.resolve()), "totalGb": round(usage.total / 1024**3, 2), "freeGb": round(usage.free / 1024**3, 2)}
        check("disk", "Training disk", "pass" if usage.free > 0 else "blocked", f"{disk['freeGb']} GB free", f"Measured at {disk['path']}. Required space depends on datasets and checkpoints.", "Free disk space before proceeding." if usage.free == 0 else "")
    except OSError:
        check("disk", "Training disk", "error", "Path unavailable", "The configured training data path could not be inspected.", "Set STUDIO_DATA_DIR to an existing accessible directory and rerun checks.")

    missing = [p["name"] for p in packages if p["required"] and p["name"] != "torch" and p["version"] is None]
    check("stack", "Training libraries", "warning" if missing else "pass", f"{len(missing)} missing" if missing else "Installed", f"Missing: {', '.join(missing)}." if missing else "Transformers, Datasets and Tokenizers are installed. A pipeline smoke test is still required.", "Install the missing training libraries into .venv after selecting compatible versions." if missing else "")
    return {"checkedAt": datetime.now(timezone.utc).isoformat(), "host": platform.node(), "platform": platform.platform(),
            "pythonExecutable": sys.executable, "scope": "backend-host", "status": "checks-passed" if all(c["status"] == "pass" for c in checks) else "needs-attention",
            "checks": checks, "packages": packages, "gpus": devices, "driverGpus": driver_devices, "memory": memory, "disk": disk}
