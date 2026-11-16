"""Credential-free training entry point. Parent owns status and artifacts."""
import json
from pathlib import Path
import sys
import time

from .data import write_json


def main(directory, checkpoints):
    directory, checkpoints = Path(directory), Path(checkpoints)
    try:
        from .core import execute
        with (directory/'metrics.jsonl').open('w', encoding='utf-8') as events:
            def emit(event):
                events.write(json.dumps({**event, 'timestamp': time.time()}, allow_nan=False)+'\n')
                events.flush()
            execute(directory, checkpoints, emit)
        return 0
    except Exception as exc:
        # Controlled validation messages are safe. Native exceptions can contain
        # full paths/environment diagnostics and must not reach the API.
        detail = str(exc) if type(exc) is ValueError else 'Training failed. Check runtime compatibility, available memory and disk; try CPU or a smaller configuration.'
        if 'out of memory' in str(exc).lower():
            detail = 'Training ran out of memory. Generate shorter sequences or choose a smaller model and retry.'
        write_json(directory/'error.json', {'detail': detail[:500]})
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
