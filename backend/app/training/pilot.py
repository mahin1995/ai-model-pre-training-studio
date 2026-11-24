"""Versioned pilot order and coverage contracts. No Torch/API dependencies."""
import hashlib
import json
import math
import random

PROTOCOL = 'all-train-epochs-v1'
PILOT_BLOCK_LIMIT = 256
PILOT_STEP_LIMIT = 2_000
FULL_BLOCK_LIMIT = 2_048
FULL_STEP_LIMIT = 10_000


def run_limits(profile):
    return (FULL_BLOCK_LIMIT, FULL_STEP_LIMIT) if profile == 'full' else (PILOT_BLOCK_LIMIT, PILOT_STEP_LIMIT)


def record_identity(records):
    return hashlib.sha256(json.dumps(records, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def epoch_order(count, seed, epoch):
    order = list(range(count))
    random.Random(f'{PROTOCOL}:{seed}:{epoch}').shuffle(order)
    return order


def checkpoint_steps(count, epochs):
    slots = min(epochs, 4)
    return [math.ceil(k * epochs / slots) * count for k in range(1, slots + 1)]


def coverage(step, records, seed, records_sha=None, *, targets=None):
    count = len(records)
    completed, offset = divmod(step, count)
    order = epoch_order(count, seed, completed)
    if targets is None:
        targets = [sum(label != -100 for label in record['labels'][1:]) for record in records]
    epoch_targets = sum(targets)
    return {'protocol': PROTOCOL, 'completedEpochs': completed, 'epochOffset': offset,
            'trainingBlocks': count, 'uniqueBlocksVisited': count if completed else offset,
            'targetTokensPerEpoch': epoch_targets,
            'targetExposures': completed * epoch_targets + sum(targets[i] for i in order[:offset]),
            'blockExposures': step, 'order': order, 'nextOffset': offset,
            'recordsSha256': records_sha or record_identity(records)}
