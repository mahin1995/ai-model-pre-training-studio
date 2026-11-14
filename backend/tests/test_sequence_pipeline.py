import json

import pytest

from app.datasets.storage import DatasetError
from app.tokenizers.pipeline import load_tokenizer, train_tokenizer
from app.tokenizers.sequences import build_blocks, generate_sequences
from test_tokenizer_pipeline import document


@pytest.mark.parametrize('size', [2, 127, 128, 129, 255, 256, 257, 513])
def test_nonoverlapping_blocks_keep_every_token_and_have_targets(size):
    ids = [2] + list(range(4, size + 2)) + [3]
    blocks = list(build_blocks(ids, 128))
    rebuilt = []
    for block in blocks:
        assert len(block['input_ids']) == len(block['labels']) == len(block['attention_mask']) == 128
        real = sum(block['attention_mask'])
        assert real >= 2
        assert block['labels'][:real] == block['input_ids'][:real]
        assert block['labels'][real:] == [-100] * (128-real)
        assert block['input_ids'][real:] == [0] * (128-real)
        rebuilt.extend(block['input_ids'][:real])
    assert rebuilt == ids
    if len(ids) % 128 == 1:
        assert sum(blocks[-1]['attention_mask']) == 2


def test_document_and_split_isolation_empty_splits_and_counts(tmp_path):
    docs = [document('বাংলা text ' * 80, name='a'), document('English test', 'test', 'b')]
    train_tokenizer(docs, tmp_path, 512)
    tokenizer = load_tokenizer(tmp_path/'tokenizer.json')
    result = generate_sequences(docs, tokenizer, tmp_path, 128)
    tokens = [json.loads(line) for line in (tmp_path/'documents.tokens.jsonl').read_text().splitlines()]
    assert (tmp_path/'validation.jsonl').read_bytes() == b''
    assert 'validation split is empty' in result['warnings'][0]
    for stream in tokens:
        records = [json.loads(line) for line in (tmp_path/(stream['split']+'.jsonl')).read_text().splitlines()]
        relevant = [r for r in records if r['documentId'] == stream['documentId']]
        reconstructed = [i for r in relevant for i, mask in zip(r['input_ids'],r['attention_mask']) if mask]
        assert reconstructed == stream['token_ids']
        assert reconstructed[0] == 2 and reconstructed[-1] == 3
        assert reconstructed.count(2) == 1 and reconstructed.count(3) == 1
        original = next(d['text'] for d in docs if d['documentId'] == stream['documentId'])
        assert tokenizer.decode(reconstructed[1:-1],skip_special_tokens=False) == original
    assert result['counts']['train']['documents'] == 1
    assert result['counts']['test']['documents'] == 1


def test_output_and_token_limits_are_errors_not_truncation(tmp_path, monkeypatch):
    import app.tokenizers.sequences as module
    docs=[document('hello world')]
    train_tokenizer(docs,tmp_path,512)
    tokenizer=load_tokenizer(tmp_path/'tokenizer.json')
    monkeypatch.setattr(module,'MAX_CONTENT_TOKENS',1)
    with pytest.raises(DatasetError,match='content-token sample limit'):
        generate_sequences(docs,tokenizer,tmp_path,128)
    monkeypatch.setattr(module,'MAX_CONTENT_TOKENS',2_000_000)
    monkeypatch.setattr(module,'MAX_OUTPUT_BYTES',1)
    with pytest.raises(DatasetError,match='output exceeds'):
        generate_sequences(docs,tokenizer,tmp_path,128)
