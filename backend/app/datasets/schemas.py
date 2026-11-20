from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr, model_validator

from ..schemas import Model

MAX_FILES = 20
MAX_BYTES = 20 * 1024 * 1024
MAX_RECORD_BYTES = 1024 * 1024
MAX_DOCUMENTS = 10_000
MAX_PDF_PAGES = 1_000
SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".jsonl", ".pdf"}
ACTIVE = ("queued", "cleaning", "deduplicating", "splitting")
RUNNING = ("cleaning", "deduplicating", "splitting")


class DatasetMetadata(Model):
    name: Annotated[StrictStr, Field(min_length=1, max_length=200)]
    language: Annotated[StrictStr, Field(min_length=1, max_length=80)]
    source: Annotated[StrictStr, Field(min_length=1, max_length=500)]
    licenseNote: Annotated[StrictStr, Field(min_length=1, max_length=4000)]
    permission: Literal["unknown", "needs-review", "confirmed"] = "unknown"

    @model_validator(mode="after")
    def meaningful(self):
        for key in ("name", "language", "source", "licenseNote"):
            if not getattr(self, key).strip():
                raise ValueError(f"{key} must not be blank.")
        return self


class ProcessingSettings(Model):
    normalizeUnicode: StrictBool = True
    normalizeNewlines: StrictBool = True
    trimWhitespace: StrictBool = True
    removeEmpty: StrictBool = True
    stripHtml: StrictBool = False
    collapseWhitespace: StrictBool = False
    deduplicate: StrictBool = True
    grouping: Literal["document", "source"] = "document"
    train: Annotated[StrictInt, Field(gt=0, le=100)] = 90
    validation: Annotated[StrictInt, Field(ge=0, le=100)] = 5
    test: Annotated[StrictInt, Field(ge=0, le=100)] = 5
    seed: Annotated[StrictInt, Field(ge=0, le=2147483647)] = 42

    @model_validator(mode="after")
    def ratios(self):
        if self.train + self.validation + self.test != 100:
            raise ValueError("Train, validation and test percentages must total 100.")
        return self


class CorrectionEdit(Model):
    recordId: Annotated[StrictStr, Field(min_length=1, max_length=200)]
    text: Annotated[StrictStr, Field(min_length=1, max_length=MAX_RECORD_BYTES)]
    reviewed: StrictBool = False
    revision: Annotated[StrictInt, Field(ge=0)]

    @model_validator(mode="after")
    def bounded_text(self):
        try:
            valid = bool(self.text.strip()) and len(self.text.encode("utf-8")) <= MAX_RECORD_BYTES
        except UnicodeEncodeError:
            valid = False
        if not valid:
            raise ValueError("Text must be nonempty valid Unicode and at most 1 MiB.")
        return self


class CorrectionPublish(Model):
    revision: Annotated[StrictInt, Field(ge=0)]
