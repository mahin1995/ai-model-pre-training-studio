import json
import logging
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import psycopg
from psycopg.types.json import Jsonb

from ..datasets.storage import DatasetError, storage_path, write_jsonl
from .schemas import LIBRARY_VERSION, RUNNING
from .sequences import package_bundle
from .source import load_documents
from .storage import check_disk, describe_artifact, table_for, verified_artifact, write_json

logger = logging.getLogger(__name__)
BACKEND = Path(__file__).resolve().parents[2]


class PreparationCancelled(Exception):
    pass


def child_environment():
    return {"PATH": os.defpath, "LANG": "C.UTF-8", "TOKENIZERS_PARALLELISM": "false",
            "PYTHONNOUSERSITE": "1", "PYTHONPATH": str(BACKEND), "HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"}


def stop_child(process):
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        process.wait(timeout=5)
        return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=5)


def recover_preparation(conn, root):
    for kind in ("tokenizer", "sequence"):
        table = table_for(kind)
        rows = conn.execute(f"""UPDATE {table} SET status='failed', finished_at=now(),
            error='Preparation was interrupted. Retry to start a new run.'
            WHERE status=ANY(%s) AND (heartbeat_at IS NULL OR heartbeat_at < now()-interval '60 seconds') RETURNING storage_key""", (list(RUNNING),)).fetchall()
        for row in rows:
            path = storage_path(root, row["storage_key"])
            shutil.rmtree(path.parent / (".tmp-" + path.name), ignore_errors=True)


def claim_preparation(conn, worker_id):
    for kind in ("tokenizer", "sequence"):
        table = table_for(kind)
        with conn.transaction():
            row = conn.execute(f"SELECT * FROM {table} WHERE status='queued' ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
            if row:
                conn.execute(f"UPDATE {table} SET status='validating', worker_id=%s, heartbeat_at=now(),started_at=now() WHERE id=%s", (worker_id, row["id"]))
                return kind, row
    return None


def execute_preparation(conn, root, kind, run, stopping):
    table = table_for(kind)
    final = storage_path(root, run["storage_key"])
    staging = final.parent / (".tmp-" + final.name)
    process = None
    published = False

    def heartbeat(stage=None):
        if stopping.is_set():
            raise DatasetError("Preparation stopped during server shutdown. Retry this run.")
        current = conn.execute(f"SELECT cancel_requested FROM {table} WHERE id=%s", (run["id"],)).fetchone()
        if not current or current["cancel_requested"]:
            raise PreparationCancelled()
        if stage in RUNNING:
            conn.execute(f"UPDATE {table} SET status=%s,heartbeat_at=now() WHERE id=%s", (stage, run["id"]))
        else:
            conn.execute(f"UPDATE {table} SET heartbeat_at=now() WHERE id=%s", (run["id"],))

    try:
        check_disk(root)
        heartbeat("validating")
        documents = load_documents(root, run["source_snapshot"])
        staging.mkdir(parents=True, exist_ok=False)
        write_jsonl(staging / "input.jsonl", documents)
        write_json(staging / "settings.json", run["settings"])
        tokenizer_files = {}
        if kind == "sequence":
            saved = run["source_snapshot"]["tokenizer"]
            tokenizer_files = {filename: verified_artifact(root, saved, key) for key, filename in
                               (("tokenizer", "tokenizer.json"), ("config", "tokenizer_config.json"), ("special_tokens", "special_tokens_map.json"))}
            verified_artifact(root, saved, "manifest")
            shutil.copyfile(tokenizer_files["tokenizer.json"], staging / "source-tokenizer.json")
        heartbeat()
        process = subprocess.Popen([sys.executable, "-m", "app.tokenizers.train_process", kind, str(staging)],
            cwd=BACKEND, env=child_environment(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=os.name == "posix")
        while process.poll() is None:
            stage = None
            try:
                stage = json.loads((staging / "stage.json").read_text())["stage"]
            except (OSError, ValueError, KeyError):
                pass
            heartbeat(stage)
            stopping.wait(.25)
        heartbeat("verifying")
        if process.returncode:
            error_path = staging / "error.json"
            detail = json.loads(error_path.read_text())["detail"] if error_path.is_file() else "Preparation child process failed. Retry and check local dependencies."
            raise DatasetError(detail)
        result = json.loads((staging / "result.json").read_text())
        snapshot = run["source_snapshot"]
        manifest = {**result, "schemaVersion": 1, "pipelineVersion": 1, "kind": kind, "runId": str(run["id"]),
            "libraryVersion": LIBRARY_VERSION, "settings": run["settings"],
            "source": {key: snapshot[key] for key in ("datasetId", "datasetVersionId", "datasetVersion", "datasetName", "manifestSha256")},
            "sourceHashes": {"processed": snapshot["manifest"]["processed"]["sha256"],
                             "documents": snapshot["manifest"]["artifacts"]["documents"]["sha256"]}}
        if kind == "sequence":
            manifest["tokenizerRunId"] = str(run["tokenizer_run_id"])
            manifest["tokenizerSource"] = snapshot["tokenizer"]["manifest"]["source"]
            manifest["tokenizerSha256"] = snapshot["tokenizer"]["manifest"]["artifacts"]["tokenizer"]["sha256"]
            for key, filename in (("tokenizer", "tokenizer.json"), ("config", "tokenizer_config.json"), ("special_tokens", "special_tokens_map.json")):
                shutil.copyfile(tokenizer_files[filename], staging / filename)
                manifest["artifacts"][key] = describe_artifact(staging / filename)
        # The downloadable manifest excludes hashes of itself and its containing ZIP.
        write_json(staging / "manifest.json", manifest)
        bundle = package_bundle(staging, tokenizer_files) if kind == "sequence" else None
        manifest["artifacts"]["manifest"] = describe_artifact(staging / "manifest.json")
        if bundle:
            manifest["artifacts"]["bundle"] = bundle
        for temporary in ("input.jsonl", "settings.json", "stage.json", "stage.tmp", "result.json", "error.json", "source-tokenizer.json"):
            (staging / temporary).unlink(missing_ok=True)
        heartbeat()
        with conn.transaction():
            current = conn.execute(f"SELECT cancel_requested FROM {table} WHERE id=%s FOR UPDATE", (run["id"],)).fetchone()
            if not current or current["cancel_requested"]:
                raise PreparationCancelled()
            if stopping.is_set():
                raise DatasetError("Preparation stopped before publication. Retry this run.")
            staging.rename(final)
            conn.execute(f"UPDATE {table} SET status='completed',manifest=%s,finished_at=now(),heartbeat_at=now() WHERE id=%s", (Jsonb(manifest), run["id"]))
        published = True
    except PreparationCancelled:
        conn.execute(f"UPDATE {table} SET status='cancelled',finished_at=now() WHERE id=%s", (run["id"],))
    except Exception as exc:
        detail = str(exc) if isinstance(exc, DatasetError) else "Preparation failed while reading or writing artifacts. Check storage, database and dependencies, then retry."
        try:
            conn.execute(f"UPDATE {table} SET status='failed',error=%s,finished_at=now() WHERE id=%s AND status=ANY(%s)", (detail, run["id"], list(RUNNING)))
        except psycopg.Error:
            logger.warning("Preparation lost its database connection; the expired lease will be recovered.")
    finally:
        if process:
            stop_child(process)
        shutil.rmtree(staging, ignore_errors=True)
        if not published and final.exists():
            try:
                state = conn.execute(f"SELECT status FROM {table} WHERE id=%s", (run["id"],)).fetchone()
                if state and state["status"] != "completed":
                    shutil.rmtree(final, ignore_errors=True)
            except psycopg.Error:
                pass  # An ambiguous COMMIT must not destroy possibly published files.
