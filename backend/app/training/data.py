"""Strict exported-sequence contract, usable without API dependencies."""
import hashlib
import json


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            value.update(chunk)
    return value.hexdigest()


def validate_record(record, vocab, length):
    arrays = [record.get(key) for key in ('input_ids', 'attention_mask', 'labels')]
    if any(not isinstance(a, list) or len(a) != length or any(type(v) is not int for v in a) for a in arrays):
        raise ValueError('Sequence arrays must contain fixed-length integers.')
    ids, mask, labels = arrays
    if any(v < 0 or v >= vocab for v in ids) or any(m not in (0, 1) for m in mask):
        raise ValueError('Sequence contains an out-of-range ID or invalid attention mask.')
    real = sum(mask)
    if real < 2 or mask != [1] * real + [0] * (length-real):
        raise ValueError('Every sequence needs at least two real tokens and right padding.')
    if ids[real:] != [0] * (length-real) or labels != ids[:real] + [-100] * (length-real):
        raise ValueError('Labels must be unshifted real IDs and -100 at PAD positions.')
    if 0 in ids[:real] or 1 in ids[:real] or record.get('split') != 'train':
        raise ValueError('Only train records with real content/boundary IDs are accepted.')
    return real - 1


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def describe(path):
    return {'filename': path.name, 'sizeBytes': path.stat().st_size, 'sha256': digest(path)}
