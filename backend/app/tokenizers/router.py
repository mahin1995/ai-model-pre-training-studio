from datetime import datetime, timezone
import json
from itertools import islice
import shutil
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from psycopg.types.json import Jsonb

from ..datasets.router import find_dataset, project_exists
from ..datasets.storage import DatasetError, checksum, read_jsonl, storage_path
from .pipeline import load_tokenizer
from .schemas import ACTIVE, LIBRARY_VERSION, EncodeRequest, SequenceCreate, TokenizerCreate
from .source import eligibility
from .storage import check_disk, table_for, verified_artifact

tokenizer_router = APIRouter(prefix="/api/projects/{project_id}/tokenizers", tags=["tokenizers"])
sequence_router = APIRouter(prefix="/api/projects/{project_id}/sequence-runs", tags=["sequences"])


def run_json(row):
    started, ended = row["started_at"], row["finished_at"]
    snapshot = row["source_snapshot"]
    return {"id": str(row["id"]), "projectId": str(row["project_id"]), "datasetId": str(row["dataset_id"]),
        "datasetVersionId": str(row["dataset_version_id"]), "datasetVersion": snapshot["datasetVersion"],
        "datasetName": snapshot["datasetName"], "tokenizerRunId": str(row["tokenizer_run_id"]) if row.get("tokenizer_run_id") else None,
        "status": row["status"], "settings": row["settings"], "cancelRequested": row["cancel_requested"],
        "error": row["error"], "manifest": row["manifest"], "createdAt": row["created_at"].isoformat(),
        "elapsedSeconds": max(0, ((ended or datetime.now(timezone.utc)) - started).total_seconds()) if started else 0}


def find_run(conn, project_id, run_id, kind, lock=False):
    row = conn.execute(f"SELECT * FROM {table_for(kind)} WHERE id=%s AND project_id=%s" + (" FOR UPDATE" if lock else ""), (run_id, project_id)).fetchone()
    if not row:
        raise HTTPException(404, "Run not found in this project.")
    return row


def source_snapshot(conn, root, project_id, version_id):
    row = conn.execute("""SELECT v.*,d.id AS dataset_id,d.metadata AS dataset_metadata FROM dataset_versions v
        JOIN datasets d ON d.id=v.dataset_id WHERE v.id=%s AND d.project_id=%s FOR UPDATE OF d""", (version_id, project_id)).fetchone()
    if not row:
        raise HTTPException(404, "Dataset version not found in this project.")
    reason = eligibility(row["manifest"], row["dataset_metadata"]["permission"])
    if reason:
        raise HTTPException(409, reason)
    path = storage_path(root, row["storage_key"]) / "manifest.json"
    if not path.is_file():
        raise HTTPException(410, "Selected version artifacts are unavailable.")
    return {"datasetId": str(row["dataset_id"]), "datasetVersionId": str(version_id), "datasetVersion": row["version"],
        "datasetName": row["dataset_metadata"]["name"], "permission": row["dataset_metadata"]["permission"],
        "storageKey": row["storage_key"], "manifest": row["manifest"], "manifestSha256": checksum(path), "libraryVersion": LIBRARY_VERSION}


def enqueue(conn, root, project_id, kind, snapshot, settings, tokenizer_id=None):
    try:
        check_disk(root)
    except (DatasetError, OSError):
        raise HTTPException(507, "At least 512 MiB free and writable data storage is required.") from None
    run_id = uuid4()
    folder = "tokenizers" if kind == "tokenizer" else "sequences"
    fields = ["id", "project_id", "dataset_id", "dataset_version_id", "settings", "source_snapshot", "storage_key"]
    values = [run_id, project_id, snapshot["datasetId"], snapshot["datasetVersionId"], Jsonb(settings), Jsonb(snapshot), f"{folder}/{project_id}/{run_id}"]
    if kind == "sequence":
        fields.append("tokenizer_run_id")
        values.append(tokenizer_id)
    row = conn.execute(f"INSERT INTO {table_for(kind)} ({','.join(fields)}) VALUES ({','.join(['%s'] * len(values))}) RETURNING *", values).fetchone()
    return run_json(row)


@tokenizer_router.get("/sources")
def sources(project_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        project_exists(conn, project_id)
        rows = conn.execute("""SELECT v.*,d.metadata,d.id AS dataset_id FROM dataset_versions v JOIN datasets d ON d.id=v.dataset_id
            WHERE d.project_id=%s ORDER BY v.created_at DESC,v.version DESC""", (project_id,)).fetchall()
    return [{"datasetId": str(row["dataset_id"]), "datasetName": row["metadata"]["name"], "versionId": str(row["id"]),
        "version": row["version"], "trainingRecords": row["manifest"]["splits"]["train"]["recordCount"],
        "reviewedRecords": row["manifest"].get("correction", {}).get("reviewedRecords", 0),
        "eligible": eligibility(row["manifest"], row["metadata"]["permission"]) is None,
        "reason": eligibility(row["manifest"], row["metadata"]["permission"])} for row in rows]


@tokenizer_router.post("", status_code=202)
def create_tokenizer(project_id: UUID, body: TokenizerCreate, request: Request):
    with request.app.state.pool.connection() as conn:
        snapshot = source_snapshot(conn, request.app.state.data_root, project_id, body.datasetVersionId)
        return enqueue(conn, request.app.state.data_root, project_id, "tokenizer", snapshot, {"vocabSize": body.vocabSize})


@sequence_router.post("", status_code=202)
def create_sequences(project_id: UUID, body: SequenceCreate, request: Request):
    with request.app.state.pool.connection() as conn:
        tokenizer = find_run(conn, project_id, body.tokenizerRunId, "tokenizer")
        find_dataset(conn, project_id, tokenizer["dataset_id"], lock=True)
        tokenizer = find_run(conn, project_id, body.tokenizerRunId, "tokenizer", lock=True)
        if tokenizer["status"] != "completed":
            raise HTTPException(409, "Choose a successfully completed tokenizer.")
        dataset = find_dataset(conn, project_id, tokenizer["dataset_id"])
        if dataset["metadata"]["permission"] != "confirmed":
            raise HTTPException(409, "Confirm dataset usage permission before generating sequences.")
        snapshot = {**tokenizer["source_snapshot"], "tokenizer": {"status": "completed", "storage_key": tokenizer["storage_key"], "manifest": tokenizer["manifest"]}}
        return enqueue(conn, request.app.state.data_root, project_id, "sequence", snapshot,
                       {"sequenceLength": body.sequenceLength}, body.tokenizerRunId)


@tokenizer_router.post("/{run_id}/encode")
def encode(project_id: UUID, run_id: UUID, body: EncodeRequest, request: Request):
    with request.app.state.pool.connection() as conn:
        row = find_run(conn, project_id, run_id, "tokenizer")
    try:
        tokenizer = load_tokenizer(verified_artifact(request.app.state.data_root, row, "tokenizer"))
        encoded = tokenizer.encode(body.text, add_special_tokens=False)
        start, end = (body.tokenPage - 1) * 256, body.tokenPage * 256
        decoded = tokenizer.decode(encoded.ids, skip_special_tokens=False)
        return {"tokenCount": len(encoded.ids), "tokenPage": body.tokenPage, "pageSize": 256,
            "tokens": [{"index": index, "id": encoded.ids[index], "piece": encoded.tokens[index], "offset": encoded.offsets[index]}
                       for index in range(start, min(end, len(encoded.ids)))],
            "decodedText": decoded, "roundTripMatches": decoded == body.text,
            "bytesPerToken": len(body.text.encode("utf-8")) / len(encoded.ids) if encoded.ids else 0}
    except DatasetError as exc:
        raise HTTPException(409, str(exc)) from None


@sequence_router.get("/{run_id}/preview")
def sequence_preview(project_id: UUID, run_id: UUID, request: Request,
                     split: str = "train", page: int = Query(default=1, ge=1)):
    if split not in {"train", "validation", "test"}:
        raise HTTPException(422, "Choose train, validation or test.")
    with request.app.state.pool.connection() as conn:
        row = find_run(conn, project_id, run_id, "sequence")
    try:
        path = verified_artifact(request.app.state.data_root, row, split)
        tokenizer = load_tokenizer(verified_artifact(request.app.state.data_root, row, "tokenizer"))
        records = list(islice(read_jsonl(path), (page - 1) * 5, page * 5))
        for record in records:
            real = sum(record["attention_mask"])
            record["decodedText"] = tokenizer.decode(record["input_ids"][:real], skip_special_tokens=False)
        return {"records": records, "page": page, "pageSize": 5, "total": row["manifest"]["counts"][split]["sequences"]}
    except DatasetError as exc:
        raise HTTPException(409, str(exc)) from None


def register_common(router, kind):
    table = table_for(kind)

    @router.get("")
    def list_runs(project_id: UUID, request: Request):
        with request.app.state.pool.connection() as conn:
            project_exists(conn, project_id)
            return [run_json(row) for row in conn.execute(f"SELECT * FROM {table} WHERE project_id=%s ORDER BY created_at DESC,id", (project_id,)).fetchall()]

    @router.get("/{run_id}")
    def get_run(project_id: UUID, run_id: UUID, request: Request):
        with request.app.state.pool.connection() as conn:
            return run_json(find_run(conn, project_id, run_id, kind))

    @router.post("/{run_id}/cancel")
    def cancel(project_id: UUID, run_id: UUID, request: Request):
        with request.app.state.pool.connection() as conn:
            run = find_run(conn, project_id, run_id, kind, lock=True)
            if run["status"] not in ACTIVE:
                raise HTTPException(409, "This run has already finished.")
            if run["status"] == "queued":
                conn.execute(f"UPDATE {table} SET status='cancelled',cancel_requested=true,finished_at=now() WHERE id=%s", (run_id,))
            else:
                conn.execute(f"UPDATE {table} SET cancel_requested=true WHERE id=%s", (run_id,))
            return run_json(find_run(conn, project_id, run_id, kind))

    @router.post("/{run_id}/retry", status_code=202)
    def retry(project_id: UUID, run_id: UUID, request: Request):
        with request.app.state.pool.connection() as conn:
            previous = find_run(conn, project_id, run_id, kind)
            dataset = find_dataset(conn, project_id, previous["dataset_id"], lock=True)
            if previous["status"] in ACTIVE:
                raise HTTPException(409, "Finish or cancel the active run before retrying.")
            if dataset["metadata"]["permission"] != "confirmed":
                raise HTTPException(409, "Confirm source permission before retrying.")
            return enqueue(conn, request.app.state.data_root, project_id, kind, previous["source_snapshot"],
                           previous["settings"], previous.get("tokenizer_run_id"))

    @router.delete("/{run_id}")
    def delete(project_id: UUID, run_id: UUID, request: Request):
        with request.app.state.pool.connection() as conn:
            run = find_run(conn, project_id, run_id, kind, lock=True)
            if run["status"] in ACTIVE:
                raise HTTPException(409, "Cancel or finish this run before deleting it.")
            if kind == "tokenizer" and conn.execute("SELECT 1 FROM sequence_runs WHERE tokenizer_run_id=%s", (run_id,)).fetchone():
                raise HTTPException(409, "Delete the dependent sequence runs before deleting this tokenizer.")
            if conn.execute(f"SELECT 1 FROM model_configs WHERE {'tokenizer_run_id' if kind == 'tokenizer' else 'sequence_run_id'}=%s", (run_id,)).fetchone():
                raise HTTPException(409, "Delete dependent model configurations and smoke runs first.")
            conn.execute(f"DELETE FROM {table} WHERE id=%s", (run_id,))
        warning = None
        try:
            shutil.rmtree(storage_path(request.app.state.data_root, run["storage_key"]))
        except FileNotFoundError:
            pass
        except OSError:
            warning = "Run removed; some stored files could not be cleaned up. Check storage permissions."
        return {"deleted": True, "cleanupWarning": warning}

    @router.get("/{run_id}/download")
    def download(project_id: UUID, run_id: UUID, request: Request, artifact: str = "manifest"):
        allowed = {"tokenizer", "config", "special_tokens", "manifest"} if kind == "tokenizer" else {"train", "validation", "test", "tokens", "manifest", "bundle"}
        if artifact not in allowed:
            raise HTTPException(422, "Unknown run artifact.")
        with request.app.state.pool.connection() as conn:
            run = find_run(conn, project_id, run_id, kind)
        try:
            path = verified_artifact(request.app.state.data_root, run, artifact)
        except DatasetError as exc:
            raise HTTPException(409, str(exc)) from None
        media = "application/zip" if artifact == "bundle" else "application/x-ndjson" if artifact in {"train", "validation", "test", "tokens"} else "application/json"
        return FileResponse(path, filename=path.name, media_type=media)


register_common(tokenizer_router, "tokenizer")
register_common(sequence_router, "sequence")
