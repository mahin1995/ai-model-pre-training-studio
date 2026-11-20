"""Read-only comparison of decoding strategies on existing CPU checkpoints."""
import hashlib
import json
from pathlib import Path

import torch
from tokenizers import Tokenizer
from transformers import GPT2LMHeadModel

root = Path('data')
project = '6c465258-3451-4421-a797-730b5d982760'
run_id = '78be46dd-652c-45db-8ea0-4b4734a7ebdf'
baseline = root / 'assessments/step-8-2026-11-20'
run = root / 'training' / project / run_id / 'checkpoints'
output = Path('artifacts/STEP_9_DECODING_PROBE.json')
torch.set_num_threads(2)
tokenizer = Tokenizer.from_file(str(baseline / 'baseline/tokenizer.json'))
tokenizer.encode_special_tokens = True
tokenizer.no_padding()
tokenizer.no_truncation()
prompts = json.loads((baseline / 'prompt-set.json').read_text())['prompts']
strategies = {
    'greedy': {'do_sample': False},
    'no_repeat_bigram': {'do_sample': False, 'no_repeat_ngram_size': 2},
    'sample_seed_42': {'do_sample': True, 'temperature': 0.8, 'top_k': 50},
    'sample_seed_43': {'do_sample': True, 'temperature': 0.8, 'top_k': 50},
    'sample_seed_44': {'do_sample': True, 'temperature': 0.8, 'top_k': 50},
}
result = {'runId': run_id, 'seedPolicy': 'seed = named seed + zero-based prompt index',
          'maxNewTokens': 32, 'promptSetVersionId': '608df22a-167d-46db-b676-e4c72c065881',
          'strategies': strategies, 'checkpoints': []}
for step in (21, 70):
    path = run / f'step-{step:06d}'
    sha = lambda: hashlib.sha256((path / 'model.safetensors').read_bytes()).hexdigest()
    original_hash = sha()
    model = GPT2LMHeadModel.from_pretrained(path, local_files_only=True, use_safetensors=True,
                                             attn_implementation='eager').eval()
    results = []
    with torch.inference_mode():
        for name, settings in strategies.items():
            entries = []
            for index, prompt in enumerate(prompts):
                ids = [2] + tokenizer.encode(prompt['text'], add_special_tokens=False).ids
                source = torch.tensor([ids], dtype=torch.long)
                if name.startswith('sample_'):
                    torch.manual_seed(int(name.rsplit('_', 1)[-1]) + index)
                generated = model.generate(input_ids=source, attention_mask=torch.ones_like(source),
                    max_new_tokens=32, use_cache=True, pad_token_id=0, bos_token_id=2,
                    eos_token_id=3, suppress_tokens=[0, 1, 2], **settings)
                new = generated[0, len(ids):].tolist()
                text = tokenizer.decode(new, skip_special_tokens=True)
                entries.append({'promptIndex': index, 'prompt': prompt['text'], 'newTokenIds': new,
                                'text': text, 'whitespaceOnly': not text.strip(),
                                'newlineTokens': new.count(202)})
            results.append({'strategy': name, 'outputs': entries})
    assert original_hash == sha(), 'Checkpoint file changed during test'
    result['checkpoints'].append({'step': step, 'modelSha256': original_hash, 'results': results})
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
for checkpoint in result['checkpoints']:
    for group in checkpoint['results']:
        outputs = group['outputs']
        print(checkpoint['step'], group['strategy'],
              'whitespace_only', sum(item['whitespaceOnly'] for item in outputs),
              'newline_tokens', sum(item['newlineTokens'] for item in outputs),
              'of', sum(len(item['newTokenIds']) for item in outputs))
