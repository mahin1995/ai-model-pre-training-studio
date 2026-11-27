"""Fresh-process reload and bounded generation using the saved tokenizer."""
import json
from pathlib import Path
import sys

from .data import write_json


def main(directory):
    import torch
    from .core import batch, load_checkpoint
    from tokenizers import Tokenizer
    directory = Path(directory)
    config = json.loads((directory/'configuration.json').read_text())
    request = json.loads((directory/'request.json').read_text())
    result = json.loads((directory/'training-result.json').read_text())
    filename = 'train.jsonl' if config.get('trainingKind') == 'pilot' else 'subset.jsonl'
    records = [json.loads(line) for line in (directory/filename).read_text().splitlines()]
    torch.set_num_threads(2)
    model, _, _ = load_checkpoint(Path(result['finalCheckpoint']), config, request['sourceIdentity'], request['device'])
    reference = torch.load(directory/'reload-reference.pt', weights_only=True, map_location='cpu')
    model.eval()
    tolerance = 1e-6 if request['device'] == 'cpu' else 1e-4
    with torch.no_grad():
        output = model(**batch(records[0], request['device']), use_cache=False)
        torch.testing.assert_close(output.logits[:, :8].cpu(), reference['logits'], rtol=tolerance, atol=tolerance)
        torch.testing.assert_close(output.loss.cpu(), reference['loss'], rtol=tolerance, atol=tolerance)
        tokenizer = Tokenizer.from_file(str(directory/'tokenizer.json'))
        tokenizer.encode_special_tokens = True
        tokenizer.no_truncation(); tokenizer.no_padding()
        prompt = config['prompt']
        if config.get('objective') == 'sft':
            first = records[0]
            prompt_end = next(index for index, label in enumerate(first['labels']) if label != -100)
            ids = first['input_ids'][:prompt_end]
            prompt = tokenizer.decode(ids[1:], skip_special_tokens=False)
        else:
            ids = [2] + tokenizer.encode(prompt, add_special_tokens=False).ids
        maximum = min(32, config['contextLength'] - len(ids))
        if maximum < 1:
            raise ValueError('Prompt exceeds the generation context budget. Save a shorter prompt.')
        source = torch.tensor([ids], device=request['device'])
        generated = model.generate(input_ids=source, attention_mask=torch.ones_like(source),
            max_new_tokens=maximum, do_sample=False, use_cache=True, pad_token_id=0, bos_token_id=2, eos_token_id=3,
            suppress_tokens=[0, 1, 2])
        full = generated[0].tolist()
        if len(full) > len(ids)+maximum or any(t < 0 or t >= config['vocabSize'] for t in full):
            raise ValueError('Generation produced invalid output IDs.')
    write_json(directory/'verification.json', {'reloadMatches': True, 'tolerance': tolerance,
        'generationValid': True, 'sample': {'prompt': prompt, 'tokenIds': full,
        'newTokenIds': full[len(ids):], 'text': tokenizer.decode(full[len(ids):], skip_special_tokens=True).replace('\x00', r'\u0000')}})


if __name__ == '__main__':
    try:
        main(sys.argv[1])
    except Exception:
        write_json(Path(sys.argv[1])/'error.json', {'detail': 'Fresh-process checkpoint reload or generation verification failed. Inspect runtime and checkpoint integrity.'})
        sys.exit(1)
