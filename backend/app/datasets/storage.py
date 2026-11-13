import hashlib
import json
from pathlib import Path
from uuid import UUID


class DatasetError(ValueError):
    """A user-actionable input or processing error."""


def storage_path(root: Path, key: str) -> Path:
    path = (root / key).resolve()
    if not path.is_relative_to(root.resolve()):
        raise DatasetError("Invalid dataset storage reference.")
    return path


def dataset_key(project_id: UUID, dataset_id: UUID) -> str:
    return f"datasets/{project_id}/{dataset_id}"


def write_jsonl(path: Path, records) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
