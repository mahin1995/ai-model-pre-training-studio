import logging
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .pipeline import prepare, write_manifest
from .corrections import prepare_corrected
from .schemas import ProcessingSettings
from .storage import DatasetError, storage_path
from ..tokenizers.jobs import claim_preparation, execute_preparation, recover_preparation
from ..training.jobs import claim_smoke, execute_smoke, recover_smoke
from ..inference.jobs import claim_inference, execute_inference, recover_inference

logger = logging.getLogger(__name__)
WORKER_LOCK = 734120502


class Cancelled(Exception):
    pass


def recover_interrupted(conn, root: Path | None = None):
    """Only expired leases are failed; queued work is safe to execute after restart."""
    recovered = conn.execute("""UPDATE dataset_jobs SET status = 'failed',
        error = 'Processing was interrupted. Retry to create a new version.', finished_at = now()
        WHERE status IN ('cleaning','deduplicating','splitting')
        AND (heartbeat_at IS NULL OR heartbeat_at < now() - interval '60 seconds') RETURNING id, dataset_id""").fetchall()
    if root is not None:
        for job in recovered:
            row = conn.execute("SELECT storage_key FROM datasets WHERE id = %s", (job["dataset_id"],)).fetchone()
            if row:
                shutil.rmtree(storage_path(root, row["storage_key"]) / "versions" / f".tmp-{job['id']}", ignore_errors=True)


def claim_job(conn, worker_id):
    with conn.transaction():
        row = conn.execute("""SELECT j.*, d.storage_key, d.metadata, d.files, d.project_id
            FROM dataset_jobs j JOIN datasets d ON d.id = j.dataset_id
            WHERE j.status = 'queued' ORDER BY j.created_at, j.id
            FOR UPDATE OF j SKIP LOCKED LIMIT 1""").fetchone()
        if row:
            conn.execute("""UPDATE dataset_jobs SET status = 'cleaning', worker_id = %s,
                heartbeat_at = now(), progress = 1 WHERE id = %s""", (worker_id, row["id"]))
        return row


def execute_job(conn, root: Path, job: dict, stopping: threading.Event):
    version_id = uuid4()
    base = storage_path(root, job["storage_key"])
    staging = base / "versions" / f".tmp-{job['id']}"
    final = base / "versions" / str(version_id)
    published = False
    last_update = 0.0
    last_stage = None

    def notify(stage, progress):
        nonlocal last_update, last_stage
        if stopping.is_set():
            raise DatasetError("Processing was interrupted during server shutdown. Retry this job.")
        now = time.monotonic()
        if stage != last_stage or now - last_update >= 0.25:
            row = conn.execute("SELECT cancel_requested FROM dataset_jobs WHERE id = %s", (job["id"],)).fetchone()
            if not row:
                raise DatasetError("Processing job no longer exists.")
            if row["cancel_requested"]:
                raise Cancelled()
            conn.execute("UPDATE dataset_jobs SET status = %s, progress = %s, heartbeat_at = now() WHERE id = %s",
                         (stage, progress, job["id"]))
            last_update, last_stage = now, stage

    try:
        staging.mkdir(parents=True, exist_ok=False)
        if snapshot := job.get("correction_input"):
            parent = conn.execute("SELECT * FROM dataset_versions WHERE id = %s AND dataset_id = %s",
                                  (snapshot["baseVersionId"], job["dataset_id"])).fetchone()
            if not parent:
                raise DatasetError("Parent dataset version is unavailable.")
            manifest = prepare_corrected(storage_path(root, parent["storage_key"]), staging, parent["manifest"], snapshot, notify)
        else:
            manifest = prepare(base / "records.jsonl", staging, ProcessingSettings.model_validate(job["settings"]), notify)
        # Serializes cancellation vs publication: either cancel wins or the whole
        # version commits. Files become visible only via a committed version row.
        with conn.transaction():
            current = conn.execute("SELECT * FROM dataset_jobs WHERE id = %s FOR UPDATE", (job["id"],)).fetchone()
            if current["cancel_requested"]:
                raise Cancelled()
            if stopping.is_set():
                raise DatasetError("Processing was interrupted during server shutdown. Retry this job.")
            version = conn.execute("SELECT COALESCE(MAX(version), 0) + 1 AS version FROM dataset_versions WHERE dataset_id = %s", (job["dataset_id"],)).fetchone()["version"]
            manifest.update({"jobId": str(job["id"]), "datasetId": str(job["dataset_id"]), "projectId": str(job["project_id"]),
                             "versionId": str(version_id), "version": version,
                             "createdAt": datetime.now(timezone.utc).isoformat(),
                             "metadata": job["metadata"], "rawFiles": job["files"]})
            write_manifest(staging, manifest)
            staging.rename(final)
            key = f"{job['storage_key']}/versions/{version_id}"
            conn.execute("INSERT INTO dataset_versions (id, dataset_id, job_id, version, storage_key, manifest) VALUES (%s,%s,%s,%s,%s,%s)",
                         (version_id, job["dataset_id"], job["id"], version, key, Jsonb(manifest)))
            conn.execute("UPDATE dataset_jobs SET status = 'completed', progress = 100, result_version_id = %s, heartbeat_at = now(), finished_at = now() WHERE id = %s", (version_id, job["id"]))
            conn.execute("UPDATE datasets SET updated_at = now() WHERE id = %s", (job["dataset_id"],))
        published = True
    except Cancelled:
        conn.execute("UPDATE dataset_jobs SET status = 'cancelled', finished_at = now() WHERE id = %s", (job["id"],))
    except Exception as exc:
        # User data/path errors are actionable; DB/system errors do not leak credentials.
        detail = str(exc) if isinstance(exc, DatasetError) else "Processing failed while reading or writing artifacts. Check storage/database availability and retry."
        try:
            conn.execute("UPDATE dataset_jobs SET status = 'failed', error = %s, finished_at = now() WHERE id = %s", (detail, job["id"]))
        except psycopg.Error:
            logger.warning("Dataset job lost its database connection; its lease will be recovered.")
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        if not published and final.exists():
            # A lost COMMIT acknowledgement is ambiguous. Never delete an artifact
            # directory if PostgreSQL may have committed its published version.
            try:
                exists = conn.execute("SELECT 1 FROM dataset_versions WHERE id = %s", (version_id,)).fetchone()
                if not exists:
                    shutil.rmtree(final, ignore_errors=True)
            except psycopg.Error:
                pass


class DatasetWorker:
    def __init__(self, url: str, root: Path):
        self.url, self.root = url, root
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self.run, name="dataset-worker", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stopping.set()
        self.thread.join(timeout=10)

    def run(self):
        worker_id = uuid4()
        while not self.stopping.is_set():
            try:
                with psycopg.connect(self.url, autocommit=True, row_factory=dict_row, connect_timeout=5) as conn:
                    # A session lock on a dedicated connection guarantees only one
                    # processing job across API processes, without occupying API pool slots.
                    acquired = conn.execute("SELECT pg_try_advisory_lock(%s) AS locked", (WORKER_LOCK,)).fetchone()["locked"]
                    if not acquired:
                        self.stopping.wait(1)
                        continue
                    while not self.stopping.is_set():
                        recover_interrupted(conn, self.root)
                        recover_preparation(conn, self.root)
                        recover_smoke(conn, self.root)
                        recover_inference(conn, self.root)
                        job = claim_job(conn, worker_id)
                        if job:
                            execute_job(conn, self.root, job, self.stopping)
                        else:
                            preparation = claim_preparation(conn, worker_id)
                            if preparation:
                                kind, run = preparation
                                execute_preparation(conn, self.root, kind, run, self.stopping)
                            else:
                                smoke = claim_smoke(conn, worker_id)
                                if smoke:
                                    execute_smoke(conn, self.root, smoke, self.stopping)
                                else:
                                    inference = claim_inference(conn, worker_id)
                                    if inference:
                                        execute_inference(conn, self.root, inference, self.stopping)
                                    else:
                                        self.stopping.wait(0.5)
            except Exception:
                logger.warning("Dataset worker temporarily unavailable; queued jobs remain in PostgreSQL.")
                self.stopping.wait(2)
