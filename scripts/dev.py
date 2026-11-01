#!/usr/bin/env python3
"""One command for a local PostgreSQL + FastAPI + React workspace."""
import hashlib
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
children = []


def run(command, **kwargs):
    subprocess.run(command, cwd=ROOT, check=True, **kwargs)


def setup():
    env_path = ROOT / ".env"
    if not env_path.exists():
        content = (ROOT / ".env.example").read_text().replace("POSTGRES_PASSWORD=change-me", f"POSTGRES_PASSWORD={secrets.token_urlsafe(30)}")
        descriptor = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(content)
        print("Created .env with a generated local database password.", flush=True)
    if not PYTHON.exists():
        run([sys.executable, "-m", "venv", str(VENV)])
    requirements = ROOT / "backend" / "requirements.txt"
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    stamp = VENV / ".studio-dependencies"
    if not stamp.exists() or stamp.read_text() != digest:
        run([str(PYTHON), "-m", "pip", "install", "-r", str(requirements)])
        stamp.write_text(digest)
    # Read .env using the exact parser used by the backend; never echo credentials.
    raw = subprocess.check_output([str(PYTHON), "-c", "from dotenv import dotenv_values; import json; print(json.dumps(dotenv_values('.env')))"], cwd=ROOT, text=True)
    import json
    for key, value in json.loads(raw).items():
        if value is not None:
            os.environ.setdefault(key, value)
    lock = ROOT / "frontend" / "package-lock.json"
    npm_stamp = ROOT / "frontend" / "node_modules" / ".studio-dependencies"
    npm_digest = hashlib.sha256(lock.read_bytes()).hexdigest()
    if not npm_stamp.exists() or npm_stamp.read_text() != npm_digest:
        run(["npm", "ci", "--prefix", "frontend"])
        npm_stamp.write_text(npm_digest)
    if not os.getenv("DATABASE_URL"):
        run(["docker", "compose", "up", "-d", "--wait", "db"])


def stop(*_args):
    for process in children:
        if process.poll() is None:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
    for process in children:
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()


def main():
    setup()
    api_port = os.getenv("API_PORT", "8000")
    frontend_port = os.getenv("FRONTEND_PORT", "5173")
    # Refuse occupied ports rather than accidentally proxying another service.
    import socket
    for port in (api_port, frontend_port):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", int(port)))
            except OSError:
                raise RuntimeError(f"Port {port} is already in use. Stop its service or change .env.") from None
    children.append(subprocess.Popen([str(PYTHON), "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", api_port, "--reload", "--reload-dir", "backend"], cwd=ROOT, start_new_session=True))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        for _ in range(60):
            if children[0].poll() is not None:
                raise RuntimeError("The backend stopped before becoming ready.")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{api_port}/api/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.5)
        else:
            raise RuntimeError("The backend did not become ready. Check PostgreSQL and the backend output.")
        env = {**os.environ, "STUDIO_API_TARGET": f"http://127.0.0.1:{api_port}"}
        children.append(subprocess.Popen(["npm", "run", "dev", "--prefix", "frontend", "--", "--port", frontend_port, "--strictPort"], cwd=ROOT, env=env, start_new_session=True))
        print(f"\nStudio: http://127.0.0.1:{frontend_port}\nAPI docs: http://127.0.0.1:{api_port}/docs\nCtrl+C stops React and Python; PostgreSQL data remains in its Docker volume.\n", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        raise RuntimeError("One of the application servers stopped.")
    finally:
        stop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        stop()
    except (RuntimeError, subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"Could not start Studio: {exc}", file=sys.stderr)
        sys.exit(1)
