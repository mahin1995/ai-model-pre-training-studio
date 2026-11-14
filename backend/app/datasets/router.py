import shutil
import logging
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError
from psycopg.types.json import Jsonb
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from .importing import parse_import
from .schemas import ACTIVE, MAX_BYTES, MAX_FILES, SUPPORTED_EXTENSIONS, DatasetMetadata, ProcessingSettings
from .storage import DatasetError, checksum, dataset_key, read_jsonl, storage_path

router = APIRouter(prefix="/api/projects/{project_id}/datasets", tags=["datasets"])
logger = logging.getLogger(__name__)


def project_exists(conn, project_id):
    if not conn.execute("SELECT 1 FROM projects WHERE id = %s", (project_id,)).fetchone():
        raise HTTPException(404, "Project not found. Save the project before importing datasets.")


def find_dataset(conn, project_id, dataset_id, lock=False):
    row = conn.execute("SELECT * FROM datasets WHERE id = %s AND project_id = %s" + (" FOR UPDATE" if lock else ""), (dataset_id, project_id)).fetchone()
    if row is None:
        raise HTTPException(404, "Dataset not found in this project.")
    return row


def job_json(row):
    if not row:
        return None
    return {"id": str(row["id"]), "datasetId": str(row["dataset_id"]), "settings": row["settings"],
            "correctionParentVersionId": (row.get("correction_input") or {}).get("baseVersionId"),
            "status": row["status"], "progress": row["progress"], "cancelRequested": row["cancel_requested"],
            "error": row["error"], "resultVersionId": str(row["result_version_id"]) if row["result_version_id"] else None,
            "createdAt": row["created_at"].isoformat(), "finishedAt": row["finished_at"].isoformat() if row["finished_at"] else None}


def dataset_json(conn, row, detail=False):
    latest_job = conn.execute("SELECT * FROM dataset_jobs WHERE dataset_id = %s ORDER BY created_at DESC, id LIMIT 1", (row["id"],)).fetchone()
    latest_version = conn.execute("SELECT * FROM dataset_versions WHERE dataset_id = %s ORDER BY version DESC LIMIT 1", (row["id"],)).fetchone()
    result = {"id": str(row["id"]), "projectId": str(row["project_id"]), "metadata": row["metadata"],
              "recordCount": row["record_count"], "sizeBytes": row["size_bytes"], "emptyCount": row["empty_count"],
              "status": latest_job["status"] if latest_job else "imported", "latestJob": job_json(latest_job),
              "versionCount": latest_version["version"] if latest_version else 0,
              "createdAt": row["created_at"].isoformat(), "updatedAt": row["updated_at"].isoformat()}
    if detail:
        result["files"] = [{k: v for k, v in file.items() if k != "storedName"} for file in row["files"]]
        versions = conn.execute("SELECT * FROM dataset_versions WHERE dataset_id = %s ORDER BY version DESC", (row["id"],)).fetchall()
        result["versions"] = [{"id": str(v["id"]), "version": v["version"], "manifest": v["manifest"], "createdAt": v["created_at"].isoformat()} for v in versions]
    return result


@router.get("")
def list_datasets(project_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        project_exists(conn, project_id)
        rows = conn.execute("SELECT * FROM datasets WHERE project_id = %s ORDER BY created_at DESC, id", (project_id,)).fetchall()
        return [dataset_json(conn, row) for row in rows]


@router.post("", status_code=201)
async def import_dataset(project_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        project_exists(conn, project_id)
    dataset_id = uuid4()
    key = dataset_key(project_id, dataset_id)
    root = request.app.state.data_root
    final = storage_path(root, key)
    staging = final.parent / f".import-{dataset_id}"
    published = False
    try:
        async with request.form(max_files=MAX_FILES, max_fields=1, max_part_size=65536) as form:
            try:
                metadata = DatasetMetadata.model_validate_json(form.get("metadata", ""))
            except (ValidationError, TypeError):
                raise HTTPException(422, "Provide valid dataset metadata: name, language, source, licenseNote and permission.") from None
            files = form.getlist("files")
            if not files or len(files) > MAX_FILES or any(not isinstance(f, UploadFile) for f in files):
                raise HTTPException(422, "Choose between 1 and 20 TXT/JSONL/PDF files.")
            if any(key != "metadata" and key != "files" for key in form):
                raise HTTPException(422, "Only metadata and files fields are accepted.")
            staging.mkdir(parents=True, exist_ok=False)
            total = 0
            stored = []
            for upload in files:
                name = (upload.filename or "").replace("\\", "/").split("/")[-1]
                if not name or len(name) > 200 or any(ord(c) < 32 for c in name):
                    raise HTTPException(422, "Filenames must contain 1–200 printable characters.")
                suffix = Path(name).suffix.lower()
                if suffix not in SUPPORTED_EXTENSIONS:
                    raise HTTPException(422, f"{name}: only TXT, JSONL and PDF files are supported.")
                file_id = str(uuid4())
                stored_name = f"{file_id}{suffix}"
                size = 0
                with (staging / stored_name).open("wb") as output:
                    while chunk := await upload.read(65536):
                        total += len(chunk)
                        size += len(chunk)
                        if total > MAX_BYTES:
                            raise HTTPException(413, "Import exceeds the 20 MiB total file size limit.")
                        output.write(chunk)
                stored.append({"id": file_id, "name": name, "storedName": stored_name,
                               "sizeBytes": size, "sha256": checksum(staging / stored_name)})
            count, empty = await run_in_threadpool(parse_import, staging, stored, metadata)
            # Both rename and INSERT occur before committing the published reference.
            with request.app.state.pool.connection() as conn:
                project_exists(conn, project_id)
                staging.rename(final)
                row = conn.execute("""INSERT INTO datasets
                    (id, project_id, metadata, storage_key, record_count, size_bytes, empty_count, files)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (dataset_id, project_id, Jsonb(metadata.model_dump()), key, count, total, empty, Jsonb(stored))).fetchone()
                result = dataset_json(conn, row, detail=True)
            published = True
            return result
    except DatasetError as exc:
        raise HTTPException(422, str(exc)) from None
    except OSError:
        raise HTTPException(507, "Could not store dataset files. Check the training data directory and available disk space.") from None
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        if not published and final.exists():
            try:
                with request.app.state.pool.connection() as conn:
                    exists = conn.execute("SELECT 1 FROM datasets WHERE id = %s", (dataset_id,)).fetchone()
                if not exists:
                    shutil.rmtree(final, ignore_errors=True)
            except Exception:
                # A commit acknowledgement may have been lost: don't delete data
                # when the publication outcome cannot be determined safely.
                pass


@router.get("/{dataset_id}")
def dataset_detail(project_id: UUID, dataset_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        return dataset_json(conn, find_dataset(conn, project_id, dataset_id), detail=True)


@router.delete("/{dataset_id}")
def delete_dataset(project_id: UUID, dataset_id: UUID, request: Request):
    # Lock the same row as processing submission so no job can be queued while
    # its inputs are being removed. Existing queued/running jobs block deletion.
    with request.app.state.pool.connection() as conn:
        row = find_dataset(conn, project_id, dataset_id, lock=True)
        if conn.execute("SELECT 1 FROM dataset_jobs WHERE dataset_id = %s AND status = ANY(%s)",
                        (dataset_id, list(ACTIVE))).fetchone():
            raise HTTPException(409, "Cancel or finish dataset processing before deleting this upload.")
        expected_key = dataset_key(project_id, dataset_id)
        if conn.execute("SELECT 1 FROM tokenizer_runs WHERE dataset_id=%s LIMIT 1", (dataset_id,)).fetchone():
            raise HTTPException(409, "Delete dependent sequence runs and tokenizer runs before deleting this dataset upload.")
        if row["storage_key"] != expected_key:
            raise HTTPException(409, "Dataset storage reference is inconsistent. No files were deleted.")
        path = storage_path(request.app.state.data_root, expected_key)
        # Break the jobs/versions reference cycle before removing child rows.
        conn.execute("UPDATE dataset_jobs SET result_version_id = NULL WHERE dataset_id = %s", (dataset_id,))
        conn.execute("DELETE FROM dataset_versions WHERE dataset_id = %s", (dataset_id,))
        conn.execute("DELETE FROM dataset_jobs WHERE dataset_id = %s", (dataset_id,))
        conn.execute("DELETE FROM datasets WHERE id = %s AND project_id = %s", (dataset_id, project_id))
    # Delete artifacts only after the database commit succeeds. A database failure
    # must never destroy files still referenced by a visible dataset.
    warning = None
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass
    except OSError:
        logger.warning("Deleted dataset %s; its stored files could not be fully removed.", dataset_id)
        warning = "The upload was removed from the library, but some stored files could not be cleaned up. Check storage permissions and disk health."
    return {"id": str(dataset_id), "deleted": True, "cleanupWarning": warning}


@router.patch("/{dataset_id}")
def update_metadata(project_id: UUID, dataset_id: UUID, metadata: DatasetMetadata, request: Request):
    with request.app.state.pool.connection() as conn:
        find_dataset(conn, project_id, dataset_id, lock=True)
        if conn.execute("SELECT 1 FROM dataset_jobs WHERE dataset_id = %s AND status = ANY(%s)", (dataset_id, list(ACTIVE))).fetchone():
            raise HTTPException(409, "Wait for the active processing job before changing source metadata.")
        row = conn.execute("UPDATE datasets SET metadata = %s, updated_at = now() WHERE id = %s RETURNING *", (Jsonb(metadata.model_dump()), dataset_id)).fetchone()
        return dataset_json(conn, row, detail=True)


def find_version(conn, dataset_id, version_id):
    row = conn.execute("SELECT * FROM dataset_versions WHERE id = %s AND dataset_id = %s", (version_id, dataset_id)).fetchone()
    if not row:
        raise HTTPException(404, "Dataset version not found.")
    return row


@router.get("/{dataset_id}/preview")
def preview(project_id: UUID, dataset_id: UUID, request: Request, version_id: UUID | None = None,
            split: str = "processed", page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=20)):
    with request.app.state.pool.connection() as conn:
        row = find_dataset(conn, project_id, dataset_id)
        if version_id:
            if split not in {"processed", "train", "validation", "test"}:
                raise HTTPException(422, "Unknown preview split.")
            version = find_version(conn, dataset_id, version_id)
            key = version["storage_key"]
            count = version["manifest"]["counts"]["output"] if split == "processed" else version["manifest"]["splits"][split]["recordCount"]
            filename = f"{split}.jsonl"
        else:
            key, filename, count = row["storage_key"], "records.jsonl", row["record_count"]
    path = storage_path(request.app.state.data_root, key) / filename
    try:
        from itertools import islice
        records = list(islice(read_jsonl(path), (page - 1) * page_size, page * page_size))
    except (OSError, ValueError):
        raise HTTPException(410, "Dataset artifacts are unavailable. Check the configured data directory.") from None
    # A 1 MiB record must not produce a 20 MiB preview response. Full text remains in downloads.
    for record in records:
        record["textTruncated"] = len(record["text"]) > 4000
        record["text"] = record["text"][:4000]
        record["provenanceCount"] = len(record["provenance"])
        record["provenance"] = record["provenance"][:5]
    return {"records": records, "page": page, "pageSize": page_size, "total": count}


@router.post("/{dataset_id}/process", status_code=202)
def process(project_id: UUID, dataset_id: UUID, settings: ProcessingSettings, request: Request):
    try:
        with request.app.state.pool.connection() as conn:
            row = find_dataset(conn, project_id, dataset_id, lock=True)
            if row["metadata"]["permission"] != "confirmed":
                raise HTTPException(409, "Confirm source usage permission in Overview before processing.")
            job = conn.execute("INSERT INTO dataset_jobs (id, dataset_id, settings, status) VALUES (%s,%s,%s,'queued') RETURNING *",
                               (uuid4(), dataset_id, Jsonb(settings.model_dump()))).fetchone()
            conn.execute("UPDATE datasets SET updated_at = now() WHERE id = %s", (dataset_id,))
            return job_json(job)
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "This dataset already has an active processing job.") from None


@router.get("/{dataset_id}/jobs/{job_id}")
def get_job(project_id: UUID, dataset_id: UUID, job_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        find_dataset(conn, project_id, dataset_id)
        row = conn.execute("SELECT * FROM dataset_jobs WHERE id = %s AND dataset_id = %s", (job_id, dataset_id)).fetchone()
        if not row:
            raise HTTPException(404, "Dataset job not found.")
        return job_json(row)


@router.post("/{dataset_id}/jobs/{job_id}/cancel")
def cancel_job(project_id: UUID, dataset_id: UUID, job_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        find_dataset(conn, project_id, dataset_id)
        row = conn.execute("SELECT * FROM dataset_jobs WHERE id = %s AND dataset_id = %s FOR UPDATE", (job_id, dataset_id)).fetchone()
        if not row:
            raise HTTPException(404, "Dataset job not found.")
        if row["status"] == "queued":
            row = conn.execute("UPDATE dataset_jobs SET status = 'cancelled', cancel_requested = true, finished_at = now() WHERE id = %s RETURNING *", (job_id,)).fetchone()
        elif row["status"] in ACTIVE:
            row = conn.execute("UPDATE dataset_jobs SET cancel_requested = true WHERE id = %s RETURNING *", (job_id,)).fetchone()
        else:
            raise HTTPException(409, "This job has already finished.")
        return job_json(row)


@router.get("/{dataset_id}/versions/{version_id}/download")
def download(project_id: UUID, dataset_id: UUID, version_id: UUID, request: Request, artifact: str = "manifest"):
    filenames = {"manifest": "manifest.json", "processed": "processed.jsonl", "train": "train.jsonl", "validation": "validation.jsonl", "test": "test.jsonl",
                 "continuous": "continuous-train.txt", "documents": "documents.jsonl", "corrections": "corrections.json"}
    if artifact not in filenames:
        raise HTTPException(422, "Unknown dataset artifact.")
    with request.app.state.pool.connection() as conn:
        find_dataset(conn, project_id, dataset_id)
        version = find_version(conn, dataset_id, version_id)
    path = storage_path(request.app.state.data_root, version["storage_key"]) / filenames[artifact]
    if not path.is_file():
        raise HTTPException(410, "Dataset artifact is unavailable. Check the configured data directory.")
    media_type = "text/plain; charset=utf-8" if artifact == "continuous" else "application/json" if artifact in {"manifest", "corrections"} else "application/x-ndjson"
    return FileResponse(path, filename=f"dataset-v{version['version']}-{filenames[artifact]}", media_type=media_type)


class UploadBodyLimit:
    """Bound multipart bytes while they are received, before form parsing/spooling."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or not scope["path"].endswith("/datasets"):
            return await self.app(scope, receive, send)
        limit = MAX_BYTES + 256 * 1024  # Multipart framing + bounded metadata.
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = 0
        if declared > limit:
            return await JSONResponse({"detail": "Import exceeds the 20 MiB upload limit."}, status_code=413)(scope, receive, send)
        total = 0

        async def bounded_receive():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > limit:
                raise HTTPException(413, "Import exceeds the 20 MiB upload limit.")
            return message
        return await self.app(scope, bounded_receive, send)
