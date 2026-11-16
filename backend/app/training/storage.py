import json
import shutil
import zipfile

import psutil

from ..datasets.storage import DatasetError, checksum, storage_path
from .data import describe

MAX_BYTES = 1024**3


def check_resources(root):
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < 5 * 1024**3:
        raise DatasetError('Smoke training requires at least 5 GiB free artifact storage.')
    if psutil.virtual_memory().available < 2 * 1024**3:
        raise DatasetError('Smoke training requires at least 2 GiB available system RAM.')


def checked_file(root, key, entry):
    path = storage_path(root, key + '/' + entry['filename'])
    if not path.is_file() or path.stat().st_size != entry['sizeBytes'] or checksum(path) != entry['sha256']:
        raise DatasetError('Training artifact is missing or its checksum differs. Restore storage or retry.')
    return path


def verify_checkpoint(root, row):
    base = storage_path(root, row['storage_key'])
    manifest = row['manifest']
    checked_file(root, row['storage_key'], manifest['descriptor'])
    info = json.loads((base/'checkpoint.json').read_text())
    if info != manifest['checkpoint']:
        raise DatasetError('Checkpoint metadata changed after publication.')
    for entry in info['files'].values():
        checked_file(root, row['storage_key'], entry)
    checked_file(root, row['storage_key'], manifest['bundle'])
    return base


def make_zip(path, files):
    temporary = path.with_suffix('.tmp')
    with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for file, name in files:
            archive.write(file, name)
    temporary.replace(path)
    return describe(path)
