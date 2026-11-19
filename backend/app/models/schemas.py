from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StrictInt, StrictStr, model_validator

from ..schemas import Model


class TrainingSettings(Model):
    layers: StrictInt = 2
    hiddenSize: StrictInt = 128
    heads: StrictInt = 4
    learningRate: Annotated[float, Field(strict=True, ge=0.000001, le=0.01, allow_inf_nan=False)] = 0.0003
    seed: Annotated[StrictInt, Field(ge=0, le=2**31-1)] = 42
    device: Literal['auto', 'cpu', 'cuda'] = 'auto'
    timeLimitSeconds: Annotated[StrictInt, Field(ge=60, le=900)] = 900
    prompt: Annotated[StrictStr, Field(max_length=4096)] = 'একজন pilot'

    @model_validator(mode='after')
    def architecture(self):
        if self.layers not in (2, 4) or self.hiddenSize not in (64, 128, 256) or self.heads not in (2, 4, 8):
            raise ValueError('Choose a supported tiny-model layer, hidden-size and attention-head combination.')
        if self.hiddenSize % self.heads:
            raise ValueError('Hidden size must be divisible by attention heads.')
        try:
            if len(self.prompt.encode('utf-8')) > 4096:
                raise ValueError('Generation prompt must be at most 4096 UTF-8 bytes.')
        except UnicodeEncodeError:
            raise ValueError('Generation prompt must be valid Unicode.') from None
        return self


class SmokeSettings(TrainingSettings):
    maxSteps: Annotated[StrictInt, Field(ge=50, le=500)] = 200


class PilotSettings(TrainingSettings):
    device: Literal['cpu'] = 'cpu'
    epochs: Annotated[StrictInt, Field(ge=1, le=20)] = 3


class ConfigCreate(Model):
    trainingKind: Literal['smoke'] = 'smoke'
    sequenceRunId: UUID
    name: Annotated[StrictStr, Field(min_length=1, max_length=100)] = 'Tiny GPT-2 smoke test'
    settings: SmokeSettings = Field(default_factory=SmokeSettings)


class PilotConfigCreate(Model):
    trainingKind: Literal['pilot']
    sequenceRunId: UUID
    name: Annotated[StrictStr, Field(min_length=1, max_length=100)] = 'Whole-dataset pilot'
    settings: PilotSettings = Field(default_factory=PilotSettings)


class RunCreate(Model):
    modelConfigId: UUID


class ResumeCreate(Model):
    checkpointId: UUID


def parameter_count(vocab, context, settings):
    h = settings['hiddenSize']
    return vocab * h + context * h + settings['layers'] * (12 * h * h + 13 * h) + 2 * h


def configuration(settings, vocab, context):
    count = parameter_count(vocab, context, settings)
    if count > 10_000_000:
        raise ValueError('Smoke models are limited to 10 million parameters.')
    # Include uncompressed checkpoints and a ZIP copy in the bounded disk budget.
    checkpoint_count = (settings['maxSteps'] + 49) // 50
    storage = count * 16 * checkpoint_count * 3 + 32 * 1024**2
    if storage > 1024**3:
        raise ValueError('Estimated checkpoints and bundle exceed 1 GiB. Reduce model size or steps.')
    return {**settings, 'architecture': 'gpt2', 'vocabSize': vocab, 'contextLength': context,
            'specialIds': {'[PAD]': 0, '[UNK]': 1, '[BOS]': 2, '[EOS]': 3},
            'precision': 'fp32', 'dropout': 0.0, 'optimizer': 'AdamW', 'weightDecay': 0.0,
            'warmupSteps': 0, 'scheduler': 'constant', 'microBatchSize': 1, 'gradientAccumulation': 1,
            'gradientClip': 1.0, 'subsetSize': 2, 'checkpointEvery': 50, 'maxNewTokens': 32,
            'estimatedParameters': count, 'estimatedStorageBytes': storage}


def pilot_configuration(settings, vocab, context, records):
    from ..training.pilot import PROTOCOL, checkpoint_steps, record_identity
    count = len(records)
    steps = count * settings['epochs']
    if not 1 <= count <= 256 or steps > 2000:
        raise ValueError('Pilot supports 1–256 train blocks and at most 2,000 updates; no blocks were sampled.')
    total = parameter_count(vocab, context, settings)
    if total > 10_000_000:
        raise ValueError('Pilot models are limited to 10 million parameters.')
    checkpoints = checkpoint_steps(count, settings['epochs'])
    storage = total * 16 * len(checkpoints) * 3 + 32 * 1024**2
    if storage > 1024**3:
        raise ValueError('Estimated pilot checkpoints and bundle exceed 1 GiB. Reduce model size or epochs.')
    return {**settings, 'trainingKind': 'pilot', 'architecture': 'gpt2', 'vocabSize': vocab,
            'contextLength': context, 'maxSteps': steps, 'checkpointSteps': checkpoints,
            'trainingBlocks': count, 'recordsSha256': record_identity(records), 'coverageProtocol': PROTOCOL,
            'initialization': 'random', 'specialIds': {'[PAD]': 0, '[UNK]': 1, '[BOS]': 2, '[EOS]': 3},
            'precision': 'fp32', 'dropout': 0.0, 'optimizer': 'AdamW', 'weightDecay': 0.0,
            'warmupSteps': 0, 'scheduler': 'constant', 'microBatchSize': 1, 'gradientAccumulation': 1,
            'gradientClip': 1.0, 'maxNewTokens': 32, 'estimatedParameters': total,
            'estimatedStorageBytes': storage}
