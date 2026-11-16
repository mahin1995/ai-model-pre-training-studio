import json
from pathlib import Path
import sys

from ..training.data import write_json


def main(directory):
    directory=Path(directory)
    try:
        from .core import execute
        with (directory/'events.jsonl').open('w',encoding='utf-8') as stream:
            def emit(event):
                stream.write(json.dumps(event,allow_nan=False)+'\n');stream.flush()
            execute(directory,emit)
        return 0
    except Exception as exc:
        detail=str(exc) if type(exc) is ValueError else 'Inference failed. Check the isolated runtime and available CPU memory/storage.'
        if 'out of memory' in str(exc).lower():detail='Inference ran out of memory. Select a smaller model or shorter output.'
        write_json(directory/'error.json',{'detail':detail[:500]})
        return 1


if __name__=='__main__':sys.exit(main(sys.argv[1]))
