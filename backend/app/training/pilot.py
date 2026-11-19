"""Versioned pilot order and coverage contracts. No Torch/API dependencies."""
import hashlib
import json
import math
import random

PROTOCOL = 'all-train-epochs-v1'


def record_identity(records):
    return hashlib.sha256(json.dumps(records, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def epoch_order(count, seed, epoch):
    order = list(range(count))
    random.Random(f'{PROTOCOL}:{seed}:{epoch}').shuffle(order)
    return order


def checkpoint_steps(count, epochs):
    slots = min(epochs, 4)
    return [math.ceil(k * epochs / slots) * count for k in range(1, slots + 1)]


def coverage(step, records, seed, records_sha=None):
    count = len(records)
    completed, offset = divmod(step, count)
    order = epoch_order(count, seed, completed)
    targets = [sum(r['attention_mask']) - 1 for r in records]
    return {'protocol': PROTOCOL, 'completedEpochs': completed, 'epochOffset': offset,
            'trainingBlocks': count, 'uniqueBlocksVisited': count if completed else offset,
            'targetTokensPerEpoch': sum(targets),
            'targetExposures': completed * sum(targets) + sum(targets[i] for i in order[:offset]),
            'blockExposures': step, 'order': order, 'nextOffset': offset,
            'recordsSha256': records_sha or record_identity(records)}
