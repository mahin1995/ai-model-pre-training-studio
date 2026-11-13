from pathlib import Path

import pymupdf
import pytest

from app.datasets.importing import parse_import, records_from_file
from app.datasets.pipeline import prepare
from app.datasets.schemas import DatasetMetadata, ProcessingSettings
from app.datasets.storage import DatasetError, read_jsonl


META = DatasetMetadata(name="PDF", language="mixed", source="Books", licenseNote="Test fixture", permission="confirmed")


def pdf_bytes(texts, encrypted=False):
    with pymupdf.open() as document:
        for text in texts:
            page = document.new_page()
            if text:
                page.insert_text((72, 72), text)
        options = {"encryption": pymupdf.PDF_ENCRYPT_AES_256, "owner_pw": "owner", "user_pw": "secret"} if encrypted else {}
        return document.tobytes(**options)


def test_pdf_page_provenance_skipped_pages_and_original_preserved(tmp_path):
    content = pdf_bytes(["First page text", "", "Third page text"])
    path = tmp_path / "original.pdf"
    path.write_bytes(content)
    files = [{"storedName": path.name, "name": "PPC Rule.PDF", "id": "pdf1"}]
    assert parse_import(tmp_path, files, META) == (2, 0)
    assert files[0]["pageCount"] == 3
    assert files[0]["skippedPages"] == [2]
    records = list(read_jsonl(tmp_path / "records.jsonl"))
    assert [r["provenance"][0]["page"] for r in records] == [1, 3]
    assert records[0]["text"].strip() == "First page text"
    assert records[1]["text"].strip() == "Third page text"
    assert records[0]["group_id"] == records[1]["group_id"]
    assert records[0]["source"] == "Books"
    assert records[0]["language"] == "mixed"
    assert path.read_bytes() == content


def test_duplicate_pdf_bytes_keep_same_group_across_filenames(tmp_path):
    path = tmp_path / "source.pdf"
    path.write_bytes(pdf_bytes(["One page", "Another page"]))
    first = list(records_from_file(path, "first.pdf", "first", META))
    duplicate = list(records_from_file(path, "duplicate.pdf", "second", META))
    assert first[0]["group_id"] == duplicate[0]["group_id"]
    from app.datasets.storage import write_jsonl
    raw = tmp_path / "records.jsonl"
    write_jsonl(raw, first + duplicate)
    output = tmp_path / "version"
    output.mkdir()
    with pytest.raises(DatasetError, match="Only 1 independent group"):
        prepare(raw, output, ProcessingSettings())
    manifest = prepare(raw, output, ProcessingSettings(train=100, validation=0, test=0))
    assert manifest["counts"]["groups"] == 1
    assert manifest["splits"]["train"]["recordCount"] == 2


@pytest.mark.parametrize("content,error", [
    (b"not a PDF", "invalid or unreadable PDF"),
    (b"", "invalid or unreadable PDF"),
    (pdf_bytes([""]), "no selectable text.*OCR"),
    (pdf_bytes(["Locked"], encrypted=True), "password-protected"),
])
def test_bad_pdf_has_actionable_filename_error(tmp_path, content, error):
    path = tmp_path / "input.pdf"
    path.write_bytes(content)
    with pytest.raises(DatasetError, match="PPC Rule.pdf: " + error):
        list(records_from_file(path, "PPC Rule.pdf", "id", META))


def test_pdf_limits_report_page_context(tmp_path, monkeypatch):
    import app.datasets.importing as module
    path = tmp_path / "input.pdf"
    path.write_bytes(pdf_bytes(["First page", "Second page"]))
    monkeypatch.setattr(module, "MAX_PDF_PAGES", 1)
    with pytest.raises(DatasetError, match="page limit"):
        list(records_from_file(path, path.name, "id", META))
    monkeypatch.setattr(module, "MAX_PDF_PAGES", 1000)
    monkeypatch.setattr(module, "MAX_RECORD_BYTES", 4)
    with pytest.raises(DatasetError, match="page 1: extracted text exceeds"):
        list(records_from_file(path, path.name, "id", META))
    monkeypatch.setattr(module, "MAX_RECORD_BYTES", 1024 * 1024)
    monkeypatch.setattr(module, "MAX_BYTES", 1)
    with pytest.raises(DatasetError, match="extracted text exceeds the 20 MiB"):
        list(records_from_file(path, path.name, "id", META))


def test_pdf_bangla_selectable_text_round_trip(tmp_path):
    path = tmp_path / "bangla.pdf"
    text = "বাংলা ভাষা শেখার উদাহরণ।"
    font_path = Path('/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf')
    if not font_path.is_file():
        pytest.skip('Bangla PDF fixture requires the Noto Sans Bengali font')
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_font(fontname='bangla', fontfile=str(font_path))
        page.insert_text((40, 72), text, fontname='bangla')
        document.save(path)
    records = list(records_from_file(path, path.name, "id", META))
    assert "".join(records[0]["text"].split()) == "".join(text.split())
