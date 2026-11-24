from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StrictInt, StrictStr, model_validator

from ..schemas import Model

MAX_BLOCKS = 256
MAX_OUTPUT_BYTES = 128 * 1024**2
ACTIVE = ('queued','validating','loading','running','verifying')
RUNNING = ACTIVE[1:]


def valid_text(text, limit=4096):
    if '\x00' in text:raise ValueError('Text must not contain NUL characters.')
    try:
        if len(text.encode('utf-8')) > limit:
            raise ValueError(f'Text must be at most {limit} UTF-8 bytes.')
    except UnicodeEncodeError:
        raise ValueError('Text must contain valid Unicode.') from None


class Prompt(Model):
    text: Annotated[StrictStr, Field(max_length=4096)]
    notes: Annotated[StrictStr, Field(max_length=4000)] = ''

    @model_validator(mode='after')
    def text_valid(self):
        valid_text(self.text); valid_text(self.notes)
        return self


class PromptSetCreate(Model):
    id: UUID | None = None
    name: Annotated[StrictStr, Field(min_length=1,max_length=100)]
    language: Literal['bn','en','mixed'] = 'mixed'
    prompts: Annotated[list[Prompt], Field(min_length=1,max_length=20)]

    @model_validator(mode='after')
    def name_valid(self):
        valid_text(self.name)
        if not self.name.strip():raise ValueError('Prompt-set name must not be blank.')
        return self


class GenerationCreate(Model):
    checkpointId: UUID
    prompt: Annotated[StrictStr, Field(max_length=4096)]
    maxNewTokens: StrictInt = 32

    @model_validator(mode='after')
    def settings_valid(self):
        valid_text(self.prompt)
        if self.maxNewTokens not in (8,16,32,64,128):raise ValueError('Choose 8/16/32/64/128 new tokens.')
        return self


class EvaluationCreate(Model):
    checkpointIds: Annotated[list[UUID], Field(min_length=1,max_length=4)]
    promptSetVersionId: UUID
    maxNewTokens: StrictInt = 32
    metricScope: Literal['training','validation','test','external'] = 'training'
    externalDatasetVersionId: UUID | None = None

    @model_validator(mode='after')
    def settings_valid(self):
        if len(set(self.checkpointIds)) != len(self.checkpointIds):raise ValueError('Select distinct checkpoints.')
        if self.maxNewTokens not in (8,16,32,64,128):raise ValueError('Choose 8/16/32/64/128 new tokens.')
        if (self.metricScope=='external') != (self.externalDatasetVersionId is not None):
            raise ValueError('An external dataset version is required only for external evaluation.')
        return self


class PromptPreview(Model):
    checkpointId: UUID
    prompt: Annotated[StrictStr, Field(max_length=4096)]

    @model_validator(mode='after')
    def text_valid(self):valid_text(self.prompt); return self


class AnnotationEdit(Model):
    checkpointId: UUID
    promptIndex: Annotated[StrictInt, Field(ge=0,le=19)]
    revision: Annotated[StrictInt, Field(ge=0)]
    readability: Literal['not-reviewed','readable','needs-review'] = 'not-reviewed'
    repetition: Literal['not-reviewed','present','absent'] = 'not-reviewed'
    sourceAgreement: Literal['not-reviewed','matches-source','needs-review'] = 'not-reviewed'
    notes: Annotated[StrictStr, Field(max_length=4000)] = ''

    @model_validator(mode='after')
    def text_valid(self):valid_text(self.notes); return self
