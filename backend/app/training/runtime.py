"""API-side runtime discovery. Never imports Torch in the API process."""
import json
import os
from pathlib import Path
import subprocess
import time

from ..config import ROOT
from ..datasets.storage import DatasetError

BACKEND = ROOT / 'backend'
SETUP_ACTION = 'Run python3 scripts/setup_training.py --profile cpu (or --profile cu128 for NVIDIA), then check again.'
_cache = {}


def training_python():
    return Path(os.getenv('STUDIO_TRAINING_PYTHON', str(ROOT / '.venv-training/bin/python'))).expanduser().absolute()


def child_environment():
    return {'PATH': os.defpath, 'LANG': 'C.UTF-8', 'PYTHONPATH': str(BACKEND), 'PYTHONNOUSERSITE': '1',
            'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1',
            'TOKENIZERS_PARALLELISM': 'false', 'OMP_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2',
            'CUBLAS_WORKSPACE_CONFIG': ':4096:8'}


def inspect_runtime(force=False, heartbeat=None):
    executable = training_python()
    key = (str(executable), executable.stat().st_mtime_ns if executable.exists() else 0)
    cached = _cache.get(key)
    if not force and cached and time.monotonic() - cached[0] < 30:
        return cached[1]
    result = {'scope': 'training-runtime', 'ready': False, 'cpu': False, 'cuda': False,
              'message': 'Training environment is not installed.', 'action': SETUP_ACTION, 'versions': {}}
    if executable.is_file() and os.access(executable, os.X_OK):
        try:
            command = [str(executable), '-m', 'app.training.probe']
            if heartbeat is None:
                probe = subprocess.run(command, cwd=BACKEND, env=child_environment(), capture_output=True, text=True, timeout=60)
            else:
                # Worker validation must remain cancellable during native imports
                # and the forward/backward probe, as well as actual training.
                from ..tokenizers.jobs import stop_child
                process = subprocess.Popen(command, cwd=BACKEND, env=child_environment(), stdout=subprocess.PIPE,
                                           stderr=subprocess.DEVNULL, text=True, start_new_session=os.name=='posix')
                deadline = time.monotonic()+60
                try:
                    while True:
                        heartbeat()
                        if time.monotonic()>deadline:
                            raise subprocess.TimeoutExpired(command,60)
                        try:
                            output,_ = process.communicate(timeout=0.25)
                            probe = subprocess.CompletedProcess(command,process.returncode,output,'')
                            break
                        except subprocess.TimeoutExpired:
                            continue
                finally:
                    if process.poll() is None:
                        stop_child(process)
                    if process.stdout:
                        process.stdout.close()
            if probe.returncode != 0:
                raise ValueError('Probe failed')
            result.update(json.loads(probe.stdout.strip().splitlines()[-1]))
        except subprocess.TimeoutExpired:
            result['message'] = 'Training-runtime checks exceeded 60 seconds.'
        except DatasetError:
            raise
        except (OSError, ValueError, IndexError):
            result['message'] = 'Training libraries could not be imported or tested. Check the isolated installation.'
    _cache[key] = (time.monotonic(), result)
    return result


def select_runtime(config, force=False, heartbeat=None):
    report = inspect_runtime(force=force, heartbeat=heartbeat)
    device = config['device']
    if not report['ready'] or not report['cpu']:
        raise DatasetError(report['message'] + ' ' + report['action'])
    if device == 'cuda' and not report['cuda']:
        raise DatasetError('CUDA forward/backward is unavailable in the training runtime. Check CUDA setup or select CPU explicitly.')
    if device == 'auto':
        # A GPU visible to Torch that fails execution must not silently fall back.
        if report.get('cudaError'):
            raise DatasetError('CUDA was detected but its training probe failed. Repair CUDA or explicitly select CPU.')
        device = 'cuda' if report['cuda'] else 'cpu'
    return {**report, 'device': device, 'deviceName': report.get('deviceName') if device == 'cuda' else 'CPU'}
