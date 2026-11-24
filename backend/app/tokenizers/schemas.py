from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StrictInt, StrictStr, model_validator

from ..schemas import Model

LIBRARY_VERSION = "0.22.2"
SPECIAL_TOKENS = {"[PAD]": 0, "[UNK]": 1, "[BOS]": 2, "[EOS]": 3}
ACTIVE = ("queued", "validating", "training", "encoding", "packing", "verifying")
RUNNING = ACTIVE[1:]
MAX_TEXT_BYTES = 20 * 1024 * 1024
MAX_RECORDS = 10_000
MAX_CONTENT_TOKENS = 2_000_000
MAX_OUTPUT_BYTES = 256 * 1024 * 1024
MIN_FREE_BYTES = 512 * 1024 * 1024


class TokenizerCreate(Model):
    datasetVersionId: UUID
    vocabSize: Annotated[StrictInt, Field(ge=260, le=32_000)] = 8_000


class SequenceCreate(Model):
    tokenizerRunId: UUID
    datasetVersionId: UUID | None = None
    objective: Literal["causal", "sft"] = "causal"
    sequenceLength: Literal[128, 256, 512, 1024] = 512

    @model_validator(mode="before")
    @classmethod
    def strict_length(cls, value):
        if isinstance(value, dict) and "sequenceLength" in value and type(value["sequenceLength"]) is not int:
            raise ValueError("sequenceLength must be an integer.")
        return value


class EncodeRequest(Model):
    text: Annotated[StrictStr, Field(max_length=16_384)]
    tokenPage: Annotated[StrictInt, Field(ge=1)] = 1

    @model_validator(mode="after")
    def valid_text(self):
        try:
            valid = len(self.text.encode("utf-8")) <= 16_384
        except UnicodeEncodeError:
            valid = False
        if not valid:
            raise ValueError("Preview text must be valid Unicode and at most 16 KiB UTF-8.")
        return self
