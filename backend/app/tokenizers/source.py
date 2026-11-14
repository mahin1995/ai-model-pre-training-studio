"""Load only immutable, reviewed, checksum-verified document text."""
import json

from ..datasets.storage import DatasetError, checksum, read_jsonl, storage_path
from .schemas import MAX_RECORDS, MAX_TEXT_BYTES


def eligibility(manifest, permission):
    counts = manifest.get("counts", {})
    correction = manifest.get("correction", {})
    if permission != "confirmed":
        return "Confirm source usage permission in Datasets."
    if not counts.get("output") or correction.get("reviewedRecords") != counts["output"]:
        return "Publish a version with every record reviewed in Review & Correct."
    if not manifest.get("splits", {}).get("train", {}).get("recordCount"):
        return "The training split is empty."
    if "documents" not in manifest.get("artifacts", {}):
        return "This version has no reviewed document export."
    return None


def load_documents(root, snapshot):
    base = storage_path(root, snapshot["storageKey"])
    manifest = snapshot["manifest"]
    reason = eligibility(manifest, snapshot["permission"])
    if reason:
        raise DatasetError(reason)
    entries = {"processed": {**manifest["processed"], "filename": "processed.jsonl"},
               "documents": manifest["artifacts"]["documents"], **manifest["splits"]}
    manifest_path = base / "manifest.json"
    if not manifest_path.is_file() or checksum(manifest_path) != snapshot["manifestSha256"]:
        raise DatasetError("Source manifest checksum mismatch. Restore the selected dataset version.")
    if json.loads(manifest_path.read_text()) != manifest:
        raise DatasetError("Source manifest differs from its published metadata.")
    paths = {}
    for key, entry in entries.items():
        path = storage_path(base, entry["filename"])
        if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024 or checksum(path) != entry["sha256"]:
            raise DatasetError(f"Source {key} artifact is missing, oversized or has a checksum mismatch.")
        paths[key] = path
    records = list(read_jsonl(paths["processed"]))
    if len(records) != manifest["counts"]["output"] or len(records) > MAX_RECORDS:
        raise DatasetError("Reviewed record count is inconsistent or exceeds 10,000 records.")
    by_id = {r["id"]: r for r in records}
    if len(by_id) != len(records):
        raise DatasetError("Source record IDs are not unique.")
    memberships, groups, content_splits = {}, {}, {}
    for split in ("train", "validation", "test"):
        items = list(read_jsonl(paths[split]))
        if len(items) != manifest["splits"][split]["recordCount"]:
            raise DatasetError("Source split counts are inconsistent.")
        for record in items:
            if record["id"] in memberships or record != by_id.get(record["id"]):
                raise DatasetError("Source split membership differs from reviewed records.")
            memberships[record["id"]] = split
            if content_splits.setdefault(record["text"], split) != split:
                raise DatasetError("Identical source text crosses split boundaries.")
            if record.get("group_id") and groups.setdefault(record["group_id"], split) != split:
                raise DatasetError("Source groups cross split boundaries.")
    if set(memberships) != set(by_id):
        raise DatasetError("Source split membership is incomplete.")
    documents = list(read_jsonl(paths["documents"]))
    seen, document_ids = set(), set()
    for document in documents:
        ids = document["recordIds"]
        if not ids or len(set(ids)) != len(ids) or seen.intersection(ids) or not set(ids) <= set(by_id):
            raise DatasetError("Document references are inconsistent.")
        source = [by_id[i] for i in ids]
        first = source[0]["provenance"][0]
        expected_id = first["fileId"] if first.get("page") else source[0]["id"]
        pages = [r["provenance"][0].get("page") for r in source]
        if (document["documentId"] != expected_id or expected_id in document_ids
                or document["pages"] != pages or document["filename"] != first["filename"]
                or document["split"] not in {"train", "validation", "test"}
                or any(memberships[i] != document["split"] for i in ids)
                or document["text"] != "\n\n".join(r["text"].strip() for r in source)):
            raise DatasetError("Document text, provenance or split does not match the reviewed version.")
        if first.get("page") and (pages != sorted(pages) or any(r["provenance"][0]["fileId"] != first["fileId"] for r in source)):
            raise DatasetError("PDF pages are out of order or mixed between sources.")
        if not document["text"].strip():
            raise DatasetError("Reviewed documents must not be empty.")
        seen.update(ids)
        document_ids.add(expected_id)
    if seen != set(by_id) or sum(len(d["text"].encode("utf-8")) for d in documents) > MAX_TEXT_BYTES:
        raise DatasetError("Reviewed documents are incomplete or exceed the 20 MiB text limit.")
    if not any(d["split"] == "train" for d in documents):
        raise DatasetError("No training documents are available.")
    return documents
