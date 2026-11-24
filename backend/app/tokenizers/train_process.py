"""Isolated CPU worker. Inputs are generated files, never credentials or user paths."""
import json
from pathlib import Path
import sys

from ..datasets.storage import DatasetError, read_jsonl
from .pipeline import load_tokenizer, train_tokenizer
from .sequences import generate_sequences
from .storage import write_json


def main(kind, directory):
    directory = Path(directory)

    def notify(stage):
        temporary = directory / "stage.tmp"
        write_json(temporary, {"stage": stage})
        temporary.replace(directory / "stage.json")

    try:
        settings = json.loads((directory / "settings.json").read_text())
        documents = list(read_jsonl(directory / "input.jsonl"))
        if kind == "tokenizer":
            result = train_tokenizer(documents, directory, settings["vocabSize"], notify)
        elif kind == "sequence":
            result = generate_sequences(documents, load_tokenizer(directory / "source-tokenizer.json"), directory,
                                        settings["sequenceLength"], notify, settings.get("objective", "causal"))
        else:
            raise DatasetError("Unknown preparation task.")
        write_json(directory / "result.json", result)
        return 0
    except Exception as exc:
        write_json(directory / "error.json", {"detail": str(exc) if isinstance(exc, DatasetError)
                                               else "Tokenizer preparation failed. Check the local dependencies and data files."})
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
