import json
import shutil
import zipfile
from contextlib import ExitStack

from ..datasets.storage import DatasetError
from .schemas import MAX_CONTENT_TOKENS, MAX_OUTPUT_BYTES
from .storage import describe_artifact


def build_blocks(ids, length):
    if length < 3 or len(ids) < 2:
        raise DatasetError("Sequences require at least two real tokens and block length >= 3.")
    blocks = [ids[start:start + length] for start in range(0, len(ids), length)]
    if len(blocks[-1]) == 1 and len(blocks) > 1:
        blocks[-1].insert(0, blocks[-2].pop())
    for block in blocks:
        if len(block) < 2:
            raise DatasetError("A sequence has no next-token target.")
        padding = length - len(block)
        yield {"input_ids": block + [0] * padding, "attention_mask": [1] * len(block) + [0] * padding,
               "labels": block + [-100] * padding}


def generate_sequences(documents, tokenizer, output, length, notify=lambda stage: None):
    notify("encoding")
    counts = {name: {"documents": 0, "sequences": 0, "contentTokens": 0, "boundaryTokens": 0, "paddedTokens": 0}
              for name in ("train", "validation", "test")}
    total_tokens = written_bytes = 0
    with ExitStack() as stack:
        streams = {name: stack.enter_context((output / f"{name}.jsonl").open("w", encoding="utf-8")) for name in counts}
        tokens_stream = stack.enter_context((output / "documents.tokens.jsonl").open("w", encoding="utf-8"))

        def write(stream, record):
            nonlocal written_bytes
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            written_bytes += len(line.encode("utf-8"))
            if written_bytes > MAX_OUTPUT_BYTES:
                raise DatasetError("Sequence output exceeds the 256 MiB sample limit.")
            stream.write(line)

        for document in documents:
            notify("encoding")
            encoded = tokenizer.encode(document["text"], add_special_tokens=False)
            total_tokens += len(encoded.ids)
            if total_tokens > MAX_CONTENT_TOKENS:
                raise DatasetError("Encoding exceeds the 2,000,000 content-token sample limit. Use a smaller reviewed corpus.")
            if tokenizer.decode(encoded.ids, skip_special_tokens=False) != document["text"]:
                raise DatasetError("Document tokenization did not preserve the reviewed text.")
            ids = [2] + encoded.ids + [3]
            split = document["split"]
            stats = counts[split]
            stats["documents"] += 1
            stats["contentTokens"] += len(encoded.ids)
            stats["boundaryTokens"] += 2
            source = {key: document[key] for key in ("documentId", "recordIds", "pages", "filename", "split")}
            write(tokens_stream, {**source, "token_ids": ids})
            notify("packing")
            cursor = 0
            for ordinal, block in enumerate(build_blocks(ids, length), start=1):
                real = sum(block["attention_mask"])
                if block["input_ids"][:real] != ids[cursor:cursor + real]:
                    raise DatasetError("Sequence reconstruction failed.")
                write(streams[split], {**block, **source, "ordinal": ordinal, "tokenRange": [cursor, cursor + real]})
                cursor += real
                stats["sequences"] += 1
                stats["paddedTokens"] += length - real
            if cursor != len(ids):
                raise DatasetError("A document token was dropped during sequence generation.")
    for stats in counts.values():
        slots = stats["sequences"] * length
        stats["paddingRatio"] = stats["paddedTokens"] / slots if slots else 0
    return {"sequenceLength": length, "labelsPolicy": "unshifted; causal model/loss shifts once; padding=-100",
            "packing": "non-overlapping; source-document isolated; singleton tail repaired",
            "counts": counts, "contentTokens": total_tokens,
            "warnings": [f"{name} split is empty; no evaluation sequences were created." for name in ("validation", "test") if not counts[name]["documents"]],
            "artifacts": {**{name: describe_artifact(output / f"{name}.jsonl") for name in counts},
                          "tokens": describe_artifact(output / "documents.tokens.jsonl")}}


def package_bundle(output, tokenizer_files):
    for filename, path in tokenizer_files.items():
        shutil.copyfile(path, output / filename)
    paths = [output / name for name in ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
                                        "train.jsonl", "validation.jsonl", "test.jsonl", "documents.tokens.jsonl", "manifest.json")]
    with zipfile.ZipFile(output / "bundle.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path.name)
    if sum(p.stat().st_size for p in output.iterdir() if p.is_file()) > MAX_OUTPUT_BYTES:
        raise DatasetError("Sequence bundle exceeds the 256 MiB output limit.")
    return describe_artifact(output / "bundle.zip")
