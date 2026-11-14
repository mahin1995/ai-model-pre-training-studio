import time

import tokenizers
from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers

from ..datasets.storage import DatasetError
from .schemas import LIBRARY_VERSION, SPECIAL_TOKENS
from .storage import describe_artifact, write_json


def load_tokenizer(path):
    if tokenizers.__version__ != LIBRARY_VERSION:
        raise DatasetError(f"Install tokenizers=={LIBRARY_VERSION} to use this saved tokenizer.")
    tokenizer = Tokenizer.from_file(str(path))
    # Literal spellings in source text remain content, not control token IDs.
    tokenizer.encode_special_tokens = True
    tokenizer.no_padding()
    tokenizer.no_truncation()
    if any(tokenizer.token_to_id(token) != index for token, index in SPECIAL_TOKENS.items()):
        raise DatasetError("Saved tokenizer special IDs do not match the configured contract.")
    return tokenizer


def train_tokenizer(documents, output, vocab_size, notify=lambda stage: None):
    if tokenizers.__version__ != LIBRARY_VERSION:
        raise DatasetError(f"Install tokenizers=={LIBRARY_VERSION} into the backend environment.")
    texts = [d["text"] for d in documents if d["split"] == "train"]
    if not texts:
        raise DatasetError("Tokenizer fitting requires nonempty training documents.")
    tokenizer = Tokenizer(models.BPE(unk_token="[UNK]"))
    tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tokenizer.decoder = decoders.ByteLevel()
    trainer = trainers.BpeTrainer(vocab_size=vocab_size, min_frequency=2,
        special_tokens=list(SPECIAL_TOKENS), initial_alphabet=pre_tokenizers.ByteLevel.alphabet(), show_progress=False)
    notify("training")
    started = time.monotonic()
    tokenizer.train_from_iterator(iter(texts), trainer=trainer, length=len(texts))
    training_seconds = time.monotonic() - started
    tokenizer.save(str(output / "tokenizer.json"))
    reloaded = load_tokenizer(output / "tokenizer.json")
    notify("verifying")
    train_tokens = 0
    for document in documents:
        encoding = reloaded.encode(document["text"], add_special_tokens=False)
        if reloaded.decode(encoding.ids, skip_special_tokens=False) != document["text"]:
            raise DatasetError("Tokenizer round-trip failed. The reviewed text must be preserved exactly.")
        if any(index < 4 for index in encoding.ids):
            raise DatasetError("Literal source text was encoded as a reserved control token.")
        if document["split"] == "train":
            train_tokens += len(encoding.ids)
    specials = {"pad_token": "[PAD]", "unk_token": "[UNK]", "bos_token": "[BOS]", "eos_token": "[EOS]"}
    config = {**specials, "tokenizer_class": "PreTrainedTokenizerFast", "clean_up_tokenization_spaces": False,
        "add_bos_token": False, "add_eos_token": False, "encode_special_tokens": True, "split_special_tokens": True,
        "boundary_owner": "sequence-builder", "normalization": "none", "special_token_ids": SPECIAL_TOKENS,
        "actual_vocab_size": reloaded.get_vocab_size(), "library_version": LIBRARY_VERSION}
    write_json(output / "tokenizer_config.json", config)
    write_json(output / "special_tokens_map.json", specials)
    return {"actualVocabSize": reloaded.get_vocab_size(), "requestedVocabSize": vocab_size,
            "trainingDocuments": len(texts), "trainingBytes": sum(len(t.encode("utf-8")) for t in texts),
            "trainingTokens": train_tokens, "trainingSeconds": round(training_seconds, 4), "specialIds": SPECIAL_TOKENS,
            "artifacts": {key: describe_artifact(output / filename) for key, filename in
                          (("tokenizer", "tokenizer.json"), ("config", "tokenizer_config.json"), ("special_tokens", "special_tokens_map.json"))}}
