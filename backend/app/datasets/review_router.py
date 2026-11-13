"""Project-scoped, revision-checked correction drafts and source comparison."""
from uuid import UUID, uuid4

import psycopg
import pymupdf
from fastapi import APIRouter, HTTPException, Query, Request, Response
from psycopg.types.json import Jsonb

from .corrections import draft_summary, safe_cleanup, suggestions
from .router import find_dataset, find_version, job_json
from .schemas import ACTIVE, MAX_BYTES, CorrectionEdit, CorrectionPublish
from .storage import read_jsonl, storage_path

router = APIRouter(prefix="/api/projects/{project_id}/datasets/{dataset_id}", tags=["dataset-review"])


def read_parent(root, version):
    try:
        return list(read_jsonl(storage_path(root, version["storage_key"]) / "processed.jsonl"))
    except (OSError, ValueError):
        raise HTTPException(410, "Parent version artifacts are unavailable.") from None


def ensure_idle(conn, dataset_id):
    if conn.execute("SELECT 1 FROM dataset_jobs WHERE dataset_id=%s AND status=ANY(%s)", (dataset_id, list(ACTIVE))).fetchone():
        raise HTTPException(409, "Wait for the active processing job before editing or publishing corrections.")


def read_draft(conn, dataset_id, version_id):
    return conn.execute("SELECT * FROM dataset_correction_drafts WHERE dataset_id=%s AND base_version_id=%s", (dataset_id, version_id)).fetchone()


@router.get("/versions/{version_id}/corrections")
def review_page(project_id: UUID, dataset_id: UUID, version_id: UUID, request: Request,
                page: int = Query(default=1, ge=1)):
    with request.app.state.pool.connection() as conn:
        dataset = find_dataset(conn, project_id, dataset_id)
        version = find_version(conn, dataset_id, version_id)
        records = read_parent(request.app.state.data_root, version)
        if page > len(records):
            raise HTTPException(404, "Review record not found.")
        draft = read_draft(conn, dataset_id, version_id)
    edits = draft["edits"] if draft else {}
    record = records[page - 1]
    edit = edits.get(record["id"], {})
    text = edit.get("text", record["text"])
    source = record["provenance"][0]
    image_url = None
    file = next((f for f in dataset["files"] if f["id"] == source["fileId"]), None)
    if file and file["name"].lower().endswith(".pdf") and source.get("page"):
        image_url = f"/api/projects/{project_id}/datasets/{dataset_id}/files/{file['id']}/pages/{source['page']}/image"
    return {"page": page, "revision": draft["revision"] if draft else 0,
            "summary": draft_summary(records, edits), "record": record, "text": text,
            "reviewed": edit.get("reviewed", False), "suggestions": suggestions(text),
            "cleanedText": safe_cleanup(text), "sourceImageUrl": image_url,
            "updatedAt": draft["updated_at"].isoformat() if draft else None}


@router.put("/versions/{version_id}/corrections")
def save_review(project_id: UUID, dataset_id: UUID, version_id: UUID, edit: CorrectionEdit, request: Request):
    with request.app.state.pool.connection() as conn:
        find_dataset(conn, project_id, dataset_id, lock=True)
        ensure_idle(conn, dataset_id)
        version = find_version(conn, dataset_id, version_id)
        records = read_parent(request.app.state.data_root, version)
        if not any(r["id"] == edit.recordId for r in records):
            raise HTTPException(404, "Record not found in the selected parent version.")
        draft = read_draft(conn, dataset_id, version_id)
        current_revision = draft["revision"] if draft else 0
        if current_revision != edit.revision:
            raise HTTPException(409, "This draft changed in another tab. Reload the saved draft before retrying; your editor text is still available.")
        edits = dict(draft["edits"]) if draft else {}
        edits[edit.recordId] = {"text": edit.text, "reviewed": edit.reviewed}
        total_bytes = sum(len(edits.get(r["id"], {}).get("text", r["text"]).encode("utf-8")) for r in records)
        if total_bytes > MAX_BYTES:
            raise HTTPException(422, "Corrected text exceeds the 20 MiB sample limit.")
        row = conn.execute("""INSERT INTO dataset_correction_drafts (dataset_id,base_version_id,revision,edits)
            VALUES (%s,%s,1,%s) ON CONFLICT (dataset_id,base_version_id) DO UPDATE
            SET revision=dataset_correction_drafts.revision+1, edits=EXCLUDED.edits, updated_at=now() RETURNING *""",
            (dataset_id, version_id, Jsonb(edits))).fetchone()
        return {"revision": row["revision"], "summary": draft_summary(records, edits), "updatedAt": row["updated_at"].isoformat()}


@router.post("/versions/{version_id}/corrections/publish", status_code=202)
def publish_review(project_id: UUID, dataset_id: UUID, version_id: UUID, body: CorrectionPublish, request: Request):
    try:
        with request.app.state.pool.connection() as conn:
            dataset = find_dataset(conn, project_id, dataset_id, lock=True)
            ensure_idle(conn, dataset_id)
            if dataset["metadata"]["permission"] != "confirmed":
                raise HTTPException(409, "Confirm source usage permission before publishing corrections.")
            version = find_version(conn, dataset_id, version_id)
            draft = read_draft(conn, dataset_id, version_id)
            if not draft or draft["revision"] != body.revision:
                raise HTTPException(409, "Draft revision changed or no draft exists. Reload the draft before publishing.")
            records = read_parent(request.app.state.data_root, version)
            summary = draft_summary(records, draft["edits"])
            if summary["reviewed"] != summary["total"]:
                raise HTTPException(409, "Review and save every record before publishing a corrected version.")
            snapshot = {"baseVersionId": str(version_id), "draftRevision": draft["revision"], "edits": draft["edits"]}
            previous = conn.execute("""SELECT id FROM dataset_jobs WHERE dataset_id=%s
                AND correction_input->>'baseVersionId'=%s AND correction_input->>'draftRevision'=%s
                AND status='completed' LIMIT 1""", (dataset_id, str(version_id), str(draft["revision"]))).fetchone()
            if previous:
                raise HTTPException(409, "This saved draft has already been published. Edit the draft or select its new version.")
            job = conn.execute("""INSERT INTO dataset_jobs (id,dataset_id,settings,status,correction_input)
                VALUES (%s,%s,%s,'queued',%s) RETURNING *""",
                (uuid4(), dataset_id, Jsonb(version["manifest"]["settings"]), Jsonb(snapshot))).fetchone()
            conn.execute("UPDATE datasets SET updated_at=now() WHERE id=%s", (dataset_id,))
            return job_json(job)
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "This dataset already has an active job.") from None


@router.get("/files/{file_id}/pages/{page}/image")
def source_page(project_id: UUID, dataset_id: UUID, file_id: UUID, page: int, request: Request):
    with request.app.state.pool.connection() as conn:
        dataset = find_dataset(conn, project_id, dataset_id)
    file = next((f for f in dataset["files"] if f["id"] == str(file_id)), None)
    if not file or not file["name"].lower().endswith(".pdf"):
        raise HTTPException(404, "Source PDF not found in this dataset.")
    path = storage_path(request.app.state.data_root, dataset["storage_key"] + "/" + file["storedName"])
    if not path.is_file():
        raise HTTPException(410, "Original PDF is unavailable.")
    try:
        with pymupdf.open(path) as document:
            if page < 1 or page > len(document):
                raise HTTPException(404, "PDF page not found.")
            source = document[page - 1]
            scale = min(2, 1400 / max(source.rect.width, source.rect.height, 1))
            data = source.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes("png")
    except (pymupdf.FileDataError, RuntimeError, ValueError):
        raise HTTPException(422, "Source PDF page could not be rendered.") from None
    return Response(data, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})
