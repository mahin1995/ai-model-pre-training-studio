"""Reviewed edits and derived artifacts; never rewrite raw or parent versions."""
import copy
import json
import re
import unicodedata
from collections import OrderedDict

from .storage import DatasetError, checksum, read_jsonl, write_jsonl

# Suggestions are shown for explicit, page-local acceptance, never applied in a worker.
SUGGESTIONS = {"হললো": "হলো", "ককোননো": "কোনো", "কররো": "করো", "ভাললো": "ভালো", "গুললো": "গুলো", "বুঝঝো": "বুঝো", "ততো": "তো"}


def suggestions(text):
    result = []
    for old, new in SUGGESTIONS.items():
        # Match whole whitespace/punctuation-delimited words, preserving Bangla marks.
        pattern = r"(?<![\w\u0980-\u09ff])" + re.escape(old) + r"(?![\w\u0980-\u09ff])"
        matches = list(re.finditer(pattern, text))
        if matches:
            result.append({"before": old, "after": new, "count": len(matches),
                           "ranges": [[m.start(), m.end()] for m in matches]})
    return result


def safe_cleanup(text):
    # U+200C/U+200D are deliberately preserved; removing all format chars breaks Bangla.
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = text.replace("\u200b", "").replace("\ufeff", "")
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")).strip()


def draft_summary(records, edits):
    return {"total": len(records), "reviewed": sum(bool(edits.get(r["id"], {}).get("reviewed")) for r in records),
            "changed": sum(edits.get(r["id"], {}).get("text", r["text"]) != r["text"] for r in records)}


def prepare_corrected(parent, output, parent_manifest, snapshot, notify):
    originals = list(read_jsonl(parent / "processed.jsonl"))
    if checksum(parent / "processed.jsonl") != parent_manifest["processed"]["sha256"]:
        raise DatasetError("Parent version checksum mismatch. Restore its original artifacts before publishing corrections.")
    edits = snapshot["edits"]
    if set(edits) != {r["id"] for r in originals} or any(not e["reviewed"] for e in edits.values()):
        raise DatasetError("Every record must be reviewed before publishing a corrected version.")
    notify("cleaning", 5)
    corrected = []
    report = []
    for index, original in enumerate(originals):
        edit = edits[original["id"]]
        if not edit["text"].strip():
            raise DatasetError("Reviewed records must not be empty.")
        record = {**original, "text": edit["text"]}
        corrected.append(record)
        if record["text"] != original["text"]:
            report.append({"recordId": record["id"], "provenance": record["provenance"],
                           "before": original["text"], "after": record["text"], "reviewed": True})
        if index % 25 == 0:
            notify("cleaning", 5 + int(45 * (index + 1) / len(originals)))
    by_id = {r["id"]: r for r in corrected}
    notify("splitting", 55)
    memberships = {}
    text_splits = {}
    splits = {}
    for name in ("train", "validation", "test"):
        parent_path = parent / f"{name}.jsonl"
        if checksum(parent_path) != parent_manifest["splits"][name]["sha256"]:
            raise DatasetError("Parent split checksum mismatch. Restore its original artifacts before publishing corrections.")
        items = []
        for old in read_jsonl(parent_path):
            if old["id"] in memberships or old["id"] not in by_id:
                raise DatasetError("Parent version has inconsistent split membership.")
            record = by_id[old["id"]]
            previous = text_splits.setdefault(record["text"], name)
            if previous != name:
                raise DatasetError("Corrections created identical text across splits. Review the affected records before publishing.")
            memberships[record["id"]] = name
            items.append(record)
        path = output / f"{name}.jsonl"
        write_jsonl(path, items)
        splits[name] = {**parent_manifest["splits"][name], "recordCount": len(items),
                        "sha256": checksum(path), "sizeBytes": path.stat().st_size}
    if set(memberships) != set(by_id):
        raise DatasetError("Parent version has missing split records.")
    write_jsonl(output / "processed.jsonl", corrected)
    # Keep page order within each source PDF; never concatenate distinct sources into one document.
    documents = OrderedDict()
    for record in corrected:
        provenance = record["provenance"][0]
        key = provenance["fileId"] if provenance.get("page") else record["id"]
        documents.setdefault(key, []).append(record)
    exports = []
    for key, records in documents.items():
        records.sort(key=lambda r: r["provenance"][0].get("page", 0))
        names = {memberships[r["id"]] for r in records}
        if len(names) != 1:
            raise DatasetError("Pages of one source document span multiple splits; review grouping first.")
        exports.append({"documentId": key, "split": names.pop(),
                        "filename": records[0]["provenance"][0]["filename"],
                        "recordIds": [r["id"] for r in records],
                        "pages": [r["provenance"][0].get("page") for r in records],
                        "text": "\n\n".join(r["text"].strip() for r in records)})
    write_jsonl(output / "documents.jsonl", exports)
    (output / "continuous-train.txt").write_text("\n\n".join(d["text"] for d in exports if d["split"] == "train"), encoding="utf-8")
    (output / "corrections.json").write_text(json.dumps({"parentVersionId": snapshot["baseVersionId"],
        "draftRevision": snapshot["draftRevision"], "reviewedRecords": len(corrected), "changes": report}, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts = {}
    for key, filename in (("documents", "documents.jsonl"), ("continuous", "continuous-train.txt"), ("corrections", "corrections.json")):
        path = output / filename
        artifacts[key] = {"filename": filename, "sha256": checksum(path), "sizeBytes": path.stat().st_size}
    manifest = copy.deepcopy(parent_manifest)
    manifest.update({"schemaVersion": 2, "parentVersionId": snapshot["baseVersionId"],
        "parentProcessedSha256": parent_manifest["processed"]["sha256"],
        "counts": {**parent_manifest["counts"], "input": len(originals), "output": len(corrected),
                   "changed": len(report), "emptyRemoved": 0, "duplicatesRemoved": 0},
        "splits": splits, "processed": {"filename": "processed.jsonl", "sha256": checksum(output / "processed.jsonl")},
        "correction": {"draftRevision": snapshot["draftRevision"], "reviewedRecords": len(corrected), "changedRecords": len(report)},
        "artifacts": artifacts,
        "note": "Reviewed correction of a saved version. Original records, page provenance and split membership are preserved. Continuous text is training-only; documents.jsonl preserves source boundaries."})
    notify("splitting", 95)
    return manifest
