import json

import pytest

from app.tokenizers.pipeline import load_tokenizer, train_tokenizer
from app.tokenizers.schemas import SPECIAL_TOKENS


def document(text, split="train", name="one"):
    return {"documentId": name, "text": text, "split": split, "recordIds": [name], "pages": [1], "filename": name + ".pdf"}


def test_byte_bpe_round_trip_special_ids_and_train_only_fit(tmp_path):
    texts = ["বাংলা English 👋 e\u0301\u200c\u200d\n  line\t.", "[EOS] [PAD] [UNK] [BOS]", "", "  "]
    docs = [document("hello hello hello Bangla বাংলা বাংলা")]
    validation_marker = "VALIDATIONEXCLUSIVEMARKER" * 20
    docs.append(document(validation_marker, "validation", "heldout"))
    result = train_tokenizer(docs, tmp_path, 8000)
    tokenizer = load_tokenizer(tmp_path / "tokenizer.json")
    assert result["trainingDocuments"] == 1
    assert result["trainingBytes"] == len(docs[0]["text"].encode())
    assert result["actualVocabSize"] <= 8000
    assert all(tokenizer.token_to_id(word) == index for word, index in SPECIAL_TOKENS.items())
    assert validation_marker not in tokenizer.get_vocab()
    for text in texts + [validation_marker]:
        encoded = tokenizer.encode(text, add_special_tokens=False)
        assert tokenizer.decode(encoded.ids, skip_special_tokens=False) == text
        assert all(index >= 4 for index in encoded.ids)
    only_train = tmp_path / 'only-train'; only_train.mkdir()
    train_tokenizer(docs[:1], only_train, 8000)
    trained_alone = load_tokenizer(only_train / 'tokenizer.json')
    assert tokenizer.get_vocab() == trained_alone.get_vocab()
    assert json.loads((tmp_path / 'tokenizer_config.json').read_text())['boundary_owner'] == 'sequence-builder'


def test_empty_fit_and_invalid_reserved_ids_are_rejected(tmp_path):
    from app.datasets.storage import DatasetError
    with pytest.raises(DatasetError, match='training documents'):
        train_tokenizer([document('held out', 'test')], tmp_path, 512)
    train_tokenizer([document('real data')], tmp_path, 512)
    data = json.loads((tmp_path/'tokenizer.json').read_text())
    data['added_tokens'][0]['content'] = 'not-the-reserved-token'
    data['model']['vocab'].pop('[PAD]')
    (tmp_path/'bad.json').write_text(json.dumps(data))
    with pytest.raises(DatasetError, match='special IDs'):
        load_tokenizer(tmp_path/'bad.json')
