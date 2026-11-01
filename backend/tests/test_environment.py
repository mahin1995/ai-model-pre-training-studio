import json
import subprocess
from types import SimpleNamespace

import app.environment as env


def runner_for(info):
    def runner(command, timeout):
        if command[0] == "nvidia-smi":
            return SimpleNamespace(returncode=0, stdout="Test GPU, 24576, 590.0\n")
        return SimpleNamespace(returncode=0, stdout=json.dumps(info))
    return runner


def test_no_pytorch_does_not_falsely_verify_cuda(monkeypatch):
    monkeypatch.setattr(env.shutil, "which", lambda _: "nvidia-smi")
    report = env.inspect_environment(runner_for({"state": "missing"}))
    checks = {c["id"]: c for c in report["checks"]}
    assert checks["pytorch"]["status"] == "blocked"
    assert checks["cuda"]["status"] == "blocked"
    assert checks["driver"]["status"] == "pass"
    assert report["gpus"] == [] and report["driverGpus"][0]["vramGb"] == 24
    assert report["scope"] == "backend-host" and report["status"] == "needs-attention"


def test_working_cuda_reports_only_torch_visible_devices(monkeypatch):
    monkeypatch.setattr(env.shutil, "which", lambda _: None)
    report = env.inspect_environment(runner_for({"state": "ok", "version": "test", "cudaRuntime": "13.0", "cudaAvailable": True, "devices": [{"name": "Test GPU", "vramGb": 24}]}))
    assert next(c for c in report["checks"] if c["id"] == "cuda")["status"] == "pass"
    assert report["gpus"][0]["name"] == "Test GPU"


def test_timeouts_and_inaccessible_disk_are_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(env.shutil, "which", lambda _: None)
    monkeypatch.setenv("STUDIO_DATA_DIR", str(tmp_path / "missing"))
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("probe", 20)
    report = env.inspect_environment(timeout)
    checks = {c["id"]: c for c in report["checks"]}
    assert checks["pytorch"]["value"] == "Check timed out"
    assert checks["disk"]["status"] == "error" and report["disk"] is None


def test_environment_endpoint_is_real_json(client, monkeypatch):
    monkeypatch.setattr("app.main.inspect_environment", lambda: {"scope": "backend-host", "checks": []})
    assert client.get("/api/environment").json()["scope"] == "backend-host"
