import json
from pathlib import Path

import pytest

from app.datasets.importing import parse_import, records_from_file
from app.datasets.pipeline import clean_text, prepare
from app.datasets.schemas import DatasetMetadata, ProcessingSettings
from app.datasets.storage import DatasetError, checksum, read_jsonl, write_jsonl

META = DatasetMetadata(name="Sample", language="bn", source="Corpus", licenseNote="Public domain", permission="confirmed")


def raw_record(index, text, group="", source="Corpus"):
    return {"id": str(index), "text": text, "group_id": group, "source": source, "language": "bn",
            "provenance": [{"fileId": "f", "filename": "sample.jsonl", "line": index + 1, "source": source, "language": "bn", "group_id": group}]}


def test_utf8_bom_txt_is_one_document_and_jsonl_preserves_metadata(tmp_path):
    path = tmp_path / "text.txt"
    original = "\ufeffবাংলা\r\nদ্বিতীয় লাইন".encode()
    path.write_bytes(original)
    records = list(records_from_file(path, "text.txt", "file1", META))
    assert len(records) == 1 and records[0]["text"] == "বাংলা\r\nদ্বিতীয় লাইন"
    assert path.read_bytes() == original
    path.write_bytes(b'\xef\xbb\xbf'+json.dumps({"text": "হ্যালো", "source": "Books", "language": "mixed", "group_id": "book-1"}).encode()+b'\n\n')
    record = list(records_from_file(path, "records.jsonl", "file2", META))[0]
    assert record["group_id"] == "book-1" and record["source"] == "Books" and record["language"] == "mixed"


@pytest.mark.parametrize("content,fragment", [(b'{bad}\n', 'line 1: invalid JSON'), (b'{"text":2}\n', 'string text'), (b'{"text":"x","group_id":2}\n','group_id must be a string'), (b'\xff','UTF-8'), (b'{"text":"\\ud800"}','invalid Unicode')])
def test_import_reports_filename_and_line(tmp_path, content, fragment):
    path = tmp_path / "raw"; path.write_bytes(content)
    with pytest.raises(DatasetError, match=fragment):
        list(records_from_file(path, "bad.jsonl", "f", META))


def test_file_and_document_limits_and_empty_counts(tmp_path, monkeypatch):
    import app.datasets.importing as importing
    path = tmp_path / "f.jsonl"
    path.write_text('{"text":""}\n{"text":"   "}\n{"text":"valid"}\n')
    files = [{"storedName": "f.jsonl", "name": "sample.jsonl", "id": "f"}]
    assert parse_import(tmp_path, files, META) == (3, 2)
    monkeypatch.setattr(importing, "MAX_DOCUMENTS", 2)
    with pytest.raises(DatasetError, match="document limit"):
        parse_import(tmp_path, files, META)
    monkeypatch.setattr(importing, "MAX_RECORD_BYTES", 4)
    with pytest.raises(DatasetError, match="exceeds 1 MiB"):
        list(records_from_file(path, "sample.jsonl", "f", META))
    with pytest.raises(DatasetError, match="TXT files are one document"):
        list(records_from_file(path, "sample.txt", "f", META))


def test_bangla_cleaning_preserves_meaningful_characters():
    text = '  বাংলা\u200c\u200d\r\n e\u0301  '
    assert clean_text(text, ProcessingSettings()) == 'বাংলা\u200c\u200d\n é'
    assert clean_text('<p>বাংলা</p><script>bad()</script><style>bad</style><p> text </p>', ProcessingSettings(stripHtml=True, collapseWhitespace=True)) == 'বাংলা text'


def test_dedup_retains_first_and_transitive_group_connections(tmp_path):
    records = [raw_record(0,"duplicate","A"), raw_record(1,"duplicate","B"), raw_record(2,"A unique","A"), raw_record(3,"B unique","B"), raw_record(4,"independent C"), raw_record(5,"independent D"), raw_record(6,"   ")]
    raw = tmp_path / 'records.jsonl'; write_jsonl(raw, records); original = checksum(raw)
    output = tmp_path / 'v1'; output.mkdir()
    manifest = prepare(raw, output, ProcessingSettings())
    assert manifest['counts'] == {'input':7,'changed':1,'emptyRemoved':1,'duplicatesRemoved':1,'output':5,'groups':3}
    processed = list(read_jsonl(output/'processed.jsonl'))
    assert processed[0]['id']=='0' and len(processed[0]['provenance'])==2
    locations = {r['text']: name for name in ('train','validation','test') for r in read_jsonl(output/f'{name}.jsonl')}
    assert locations['duplicate']==locations['A unique']==locations['B unique']
    assert checksum(raw)==original
    assert sum(v['recordCount'] for v in manifest['splits'].values())==5


def test_dedup_off_still_prevents_identical_text_leakage(tmp_path):
    raw=tmp_path/'records.jsonl';write_jsonl(raw,[raw_record(0,'same'),raw_record(1,'same'),raw_record(2,'other'),raw_record(3,'last')])
    output=tmp_path/'out';output.mkdir()
    manifest=prepare(raw,output,ProcessingSettings(deduplicate=False))
    assert manifest['counts']['output']==4 and manifest['counts']['duplicatesRemoved']==0
    same_splits=[name for name in ('train','validation','test') for r in read_jsonl(output/f'{name}.jsonl') if r['text']=='same']
    assert len(same_splits)==2 and len(set(same_splits))==1


def test_seed_reproducibility_source_groups_and_small_split_failure(tmp_path):
    raw=tmp_path/'records.jsonl';write_jsonl(raw,[raw_record(i,f'doc {i}',source=f'source-{i//3}') for i in range(30)])
    outputs=[]
    for name in ('one','two'):
        output=tmp_path/name;output.mkdir();prepare(raw,output,ProcessingSettings(grouping='source'))
        outputs.append({split:(output/f'{split}.jsonl').read_bytes() for split in ('train','validation','test')})
    assert outputs[0]==outputs[1]
    source_locations={}
    for split, content in outputs[0].items():
        for line in content.decode().splitlines():
            record=json.loads(line)
            assert record['source'] not in source_locations or source_locations[record['source']]==split
            source_locations[record['source']]=split
    write_jsonl(raw,[raw_record(i,f'text {i}') for i in range(3)])
    with pytest.raises(DatasetError,match='Only 1 independent group'):
        prepare(raw,tmp_path/'one',ProcessingSettings(grouping='source'))
    assert prepare(raw,tmp_path/'one',ProcessingSettings(grouping='source',train=100,validation=0,test=0))['splits']['train']['recordCount']==3


def test_all_empty_cleaned_data_and_invalid_ratios(tmp_path):
    raw=tmp_path/'records.jsonl';write_jsonl(raw,[raw_record(0,' ')])
    with pytest.raises(DatasetError,match='No documents remain'):
        prepare(raw,tmp_path,ProcessingSettings())
    for settings in ({'train':80},{'seed':True},{'train':90.5},{'seed':-1},{'train':0,'validation':50,'test':50}):
        with pytest.raises(ValueError):ProcessingSettings(**settings)
