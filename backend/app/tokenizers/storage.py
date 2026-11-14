import json
import shutil
from pathlib import Path

from ..datasets.storage import DatasetError, checksum, storage_path
from .schemas import MIN_FREE_BYTES

TABLES = {"tokenizer": "tokenizer_runs", "sequence": "sequence_runs"}


def table_for(kind):
    return TABLES[kind]  # Internal enum only, never a browser-controlled table name.


def check_disk(root):
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < MIN_FREE_BYTES:
        raise DatasetError("At least 512 MiB of free data storage is required for this sample run.")


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def describe_artifact(path):
    return {"filename": path.name, "sizeBytes": path.stat().st_size, "sha256": checksum(path)}


def verified_artifact(root, run, artifact):
    if run["status"] != "completed" or not run["manifest"]:
        raise DatasetError("This run has no published artifacts yet.")
    entry = run["manifest"].get("artifacts", {}).get(artifact)
    if not entry:
        raise DatasetError("Unknown run artifact.")
    path = storage_path(root, run["storage_key"] + "/" + entry["filename"])
    if not path.is_file() or path.stat().st_size != entry["sizeBytes"] or checksum(path) != entry["sha256"]:
        raise DatasetError("Saved artifact is missing or its checksum does not match. Restore storage or retry this run.")
    return path
