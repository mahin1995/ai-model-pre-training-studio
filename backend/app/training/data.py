"""Strict exported-sequence contract, usable without API dependencies."""
import hashlib
import json


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            value.update(chunk)
    return value.hexdigest()


def validate_record(record, vocab, length, assistant_only=False):
    arrays = [record.get(key) for key in ('input_ids', 'attention_mask', 'labels')]
    if any(not isinstance(a, list) or len(a) != length or any(type(v) is not int for v in a) for a in arrays):
        raise ValueError('Sequence arrays must contain fixed-length integers.')
    ids, mask, labels = arrays
    if any(v < 0 or v >= vocab for v in ids) or any(m not in (0, 1) for m in mask):
        raise ValueError('Sequence contains an out-of-range ID or invalid attention mask.')
    real = sum(mask)
    if real < 2 or mask != [1] * real + [0] * (length-real):
        raise ValueError('Every sequence needs at least two real tokens and right padding.')
    start = next((index for index, label in enumerate(labels[:real]) if label != -100), real) if assistant_only else 0
    if assistant_only and (not 1 <= start < real - 1 or ids[0] != 2 or ids[real - 1] != 3):
        raise ValueError('SFT requires a masked prompt, a supervised answer and EOS.')
    if ids[real:] != [0] * (length-real) or labels != [-100] * start + ids[start:real] + [-100] * (length-real):
        raise ValueError('Labels must match the supervised token span and mask all other positions.')
    if 0 in ids[:real] or 1 in ids[:real] or record.get('split') != 'train':
        raise ValueError('Only train records with real content/boundary IDs are accepted.')
    return real - max(1, start)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def describe(path):
    return {'filename': path.name, 'sizeBytes': path.stat().st_size, 'sha256': digest(path)}
