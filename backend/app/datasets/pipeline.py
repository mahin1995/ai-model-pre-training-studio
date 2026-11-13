"""Bounded, deterministic document preparation. No model/training imports."""
import json
import random
import re
import unicodedata
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

from .schemas import ProcessingSettings
from .storage import DatasetError, checksum, read_jsonl, write_jsonl


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        elif not self.hidden and tag in {"p", "div", "br", "li", "h1", "h2", "h3", "section", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in {"p", "div", "li", "section", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def clean_text(text: str, settings: ProcessingSettings) -> str:
    if settings.normalizeUnicode:
        text = unicodedata.normalize("NFC", text)
    if settings.normalizeNewlines:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    if settings.stripHtml:
        parser = PlainText()
        parser.feed(text)
        parser.close()
        text = "".join(parser.parts)
    if settings.collapseWhitespace:
        text = re.sub(r"\s+", " ", text)
    if settings.trimWhitespace:
        text = text.strip()
    return text


class Groups:
    def __init__(self, size):
        self.parent = list(range(size))

    def root(self, index):
        while index != self.parent[index]:
            self.parent[index] = self.parent[self.parent[index]]
            index = self.parent[index]
        return index

    def merge(self, a, b):
        self.parent[self.root(b)] = self.root(a)


def prepare(raw_path: Path, output: Path, settings: ProcessingSettings, notify=lambda stage, progress: None) -> dict:
    notify("cleaning", 5)
    raw = list(read_jsonl(raw_path))
    cleaned = []
    removed_empty = changed = 0
    for index, original in enumerate(raw):
        text = clean_text(original["text"], settings)
        changed += text != original["text"]
        if settings.removeEmpty and not text.strip():
            removed_empty += 1
        else:
            cleaned.append({**original, "text": text, "provenance": list(original["provenance"])})
        if index % 100 == 0:
            notify("cleaning", 5 + int(30 * (index + 1) / max(len(raw), 1)))
    if not cleaned:
        raise DatasetError("No documents remain after cleaning. Review the data or cleaning settings.")
    notify("deduplicating", 40)
    groups = Groups(len(cleaned))
    tokens = {}
    seen_text = {}
    retained = []
    duplicate_count = 0
    for index, record in enumerate(cleaned):
        keys = []
        if record["group_id"]:
            keys.append(("group", record["group_id"]))
        if settings.grouping == "source":
            keys.append(("source", record["source"]))
        for key in keys:
            if key in tokens:
                groups.merge(index, tokens[key])
            else:
                tokens[key] = index
        previous = seen_text.get(record["text"])
        if previous is None:
            seen_text[record["text"]] = index
            retained.append(index)
        else:
            # Union before dropping duplicates so explicit groups/source boundaries
            # survive deduplication, including transitive duplicate connections.
            groups.merge(index, previous)
            if settings.deduplicate:
                cleaned[previous]["provenance"].extend(record["provenance"])
                duplicate_count += 1
            else:
                retained.append(index)
        if index % 100 == 0:
            notify("deduplicating", 40 + int(25 * (index + 1) / len(cleaned)))
    notify("splitting", 70)
    grouped = defaultdict(list)
    for index in retained:
        record = cleaned[index]
        record["duplicateCount"] = len(record["provenance"]) - 1
        grouped[groups.root(index)].append(record)
    ratios = {"train": settings.train, "validation": settings.validation, "test": settings.test}
    enabled = [name for name, ratio in ratios.items() if ratio]
    if len(grouped) < len(enabled):
        raise DatasetError(f"Only {len(grouped)} independent group(s) remain, but {len(enabled)} non-zero splits were requested. Add independent documents, switch grouping, or set unused splits to 0%.")
    ordered = list(grouped.values())
    random.Random(settings.seed).shuffle(ordered)
    ordered.sort(key=len, reverse=True)  # Seeded order breaks equal-size ties.
    splits = {name: [] for name in ratios}
    group_counts = dict.fromkeys(ratios, 0)
    total = len(retained)
    for index, records in enumerate(ordered):
        empty = [name for name in enabled if group_counts[name] == 0]
        remaining = len(ordered) - index
        candidates = empty if remaining == len(empty) else enabled
        chosen = max(candidates, key=lambda name: (total * ratios[name] / 100 - len(splits[name]), ratios[name]))
        splits[chosen].extend(records)
        group_counts[chosen] += 1
        if index % 100 == 0:
            notify("splitting", 70 + int(15 * (index + 1) / len(ordered)))
    artifacts = {}
    for name, records in splits.items():
        path = output / f"{name}.jsonl"
        write_jsonl(path, records)
        artifacts[name] = {"filename": path.name, "recordCount": len(records), "groupCount": group_counts[name],
                           "actualPercent": round(len(records) * 100 / total, 2), "requestedPercent": ratios[name],
                           "sizeBytes": path.stat().st_size, "sha256": checksum(path)}
        notify("splitting", 90)
    write_jsonl(output / "processed.jsonl", [cleaned[index] for index in retained])
    manifest = {"schemaVersion": 1, "settings": settings.model_dump(), "seed": settings.seed,
                "counts": {"input": len(raw), "changed": changed, "emptyRemoved": removed_empty,
                           "duplicatesRemoved": duplicate_count, "output": total, "groups": len(grouped)},
                "splits": artifacts, "sources": sorted({r["source"] for r in raw}),
                "rawRecordsSha256": checksum(raw_path),
                "processed": {"filename": "processed.jsonl", "sha256": checksum(output / "processed.jsonl")},
                "note": "Groups and identical cleaned content stay together. Actual split ratios may differ from requested ratios."}
    notify("splitting", 95)
    return manifest


def write_manifest(output: Path, manifest: dict):
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
