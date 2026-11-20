import json
from pathlib import Path

import pymupdf

from .schemas import MAX_BYTES, MAX_DOCUMENTS, MAX_PDF_PAGES, MAX_RECORD_BYTES, SUPPORTED_EXTENSIONS, DatasetMetadata
from .storage import DatasetError, checksum


def records_from_file(path: Path, filename: str, file_id: str, metadata: DatasetMetadata, info: dict | None = None):
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise DatasetError(f"{filename}: only TXT, Markdown, JSONL and PDF files are supported.")
    if suffix == ".pdf":
        yield from records_from_pdf(path, filename, file_id, metadata, info)
        return
    if suffix in {".txt", ".md", ".markdown"}:
        label = "TXT" if suffix == ".txt" else "Markdown"
        if path.stat().st_size > MAX_RECORD_BYTES:
            raise DatasetError(f"{filename}, document 1: {label} files are one document and must not exceed 1 MiB.")
        try:
            text = path.read_bytes().decode("utf-8-sig")
        except UnicodeDecodeError:
            raise DatasetError(f"{filename}, document 1: expected UTF-8 or UTF-8 BOM encoding.") from None
        yield make_record(text, {}, file_id, filename, 1, metadata)
        return
    with path.open("rb") as stream:
        line_number = 0
        while line := stream.readline(MAX_RECORD_BYTES + 1):
            line_number += 1
            if len(line) > MAX_RECORD_BYTES:
                raise DatasetError(f"{filename}, line {line_number}: record exceeds 1 MiB.")
            try:
                line_text = line.decode("utf-8-sig" if line_number == 1 else "utf-8")
            except UnicodeDecodeError:
                raise DatasetError(f"{filename}, line {line_number}: expected UTF-8 encoding.") from None
            if not line_text.strip():
                continue
            try:
                value = json.loads(line_text)
            except (ValueError, RecursionError):
                raise DatasetError(f"{filename}, line {line_number}: invalid JSON.") from None
            if not isinstance(value, dict) or not isinstance(value.get("text"), str):
                raise DatasetError(f"{filename}, line {line_number}: each record must contain a string text field.")
            for field in ("source", "language", "group_id"):
                if field in value and not isinstance(value[field], str):
                    raise DatasetError(f"{filename}, line {line_number}: optional {field} must be a string.")
            try:
                json.dumps(value, ensure_ascii=False).encode("utf-8")
            except UnicodeEncodeError:
                raise DatasetError(f"{filename}, line {line_number}: text contains an invalid Unicode surrogate.") from None
            yield make_record(value["text"], value, file_id, filename, line_number, metadata)


def records_from_pdf(path: Path, filename: str, file_id: str, metadata: DatasetMetadata, info: dict | None = None):
    """Keep PDF pages inspectable and group the entire source to avoid split leakage."""
    try:
        with pymupdf.open(path) as document:
            if not document.is_pdf:
                raise DatasetError(f"{filename}: not a valid PDF file.")
            if document.needs_pass:
                raise DatasetError(f"{filename}: password-protected PDF. Upload an unlocked copy.")
            if document.page_count > MAX_PDF_PAGES:
                raise DatasetError(f"{filename}: PDF exceeds the {MAX_PDF_PAGES:,} page limit.")
            if info is not None:
                info.update(pageCount=document.page_count, skippedPages=[])
            group = "pdf:" + checksum(path)
            extracted_bytes = count = 0
            for number, page in enumerate(document, start=1):
                try:
                    text = page.get_text("text", sort=True)
                except (RuntimeError, ValueError) as exc:
                    raise DatasetError(f"{filename}, page {number}: could not extract text.") from exc
                if not text.strip():
                    if info is not None:
                        info["skippedPages"].append(number)
                    continue
                size = len(text.encode("utf-8"))
                if size > MAX_RECORD_BYTES:
                    raise DatasetError(f"{filename}, page {number}: extracted text exceeds 1 MiB.")
                extracted_bytes += size
                if extracted_bytes > MAX_BYTES:
                    raise DatasetError(f"{filename}: extracted text exceeds the 20 MiB limit. Upload a smaller PDF.")
                record = make_record(text, {"group_id": group}, file_id, filename, number, metadata)
                record["provenance"][0]["page"] = number
                count += 1
                yield record
            if not count:
                raise DatasetError(f"{filename}: no selectable text found. Scanned/image PDFs need OCR before import.")
    except DatasetError:
        raise
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        raise DatasetError(f"{filename}: invalid or unreadable PDF. Upload a valid, unlocked PDF.") from exc


def make_record(text: str, value: dict, file_id: str, filename: str, line: int, metadata: DatasetMetadata):
    return {"id": f"{file_id}:{line}", "text": text,
            "source": value.get("source", metadata.source), "language": value.get("language", metadata.language),
            "group_id": value.get("group_id", ""),
            "provenance": [{"fileId": file_id, "filename": filename, "line": line,
                            "source": value.get("source", metadata.source), "language": value.get("language", metadata.language),
                            "group_id": value.get("group_id", "")} ]}


def parse_import(directory: Path, files: list[dict], metadata: DatasetMetadata) -> tuple[int, int]:
    count = empty = 0
    with (directory / "records.jsonl").open("w", encoding="utf-8", newline="\n") as output:
        for file in files:
            file_count = 0
            for record in records_from_file(directory / file["storedName"], file["name"], file["id"], metadata, file):
                count += 1
                file_count += 1
                if count > MAX_DOCUMENTS:
                    raise DatasetError("Import exceeds the 10,000 document limit. Upload a smaller sample.")
                empty += not record["text"].strip()
                output.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            file["recordCount"] = file_count
    if count == 0:
        raise DatasetError("No documents found. JSONL files must contain at least one text record.")
    return count, empty
