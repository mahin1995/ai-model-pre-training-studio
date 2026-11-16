"""Numerical smoke executor; only the training interpreter imports this module."""
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import random
import time

import psutil
import torch
from transformers import GPT2Config, GPT2LMHeadModel

from .data import describe, digest, validate_record, write_json


def versions():
    return {**{name: importlib.metadata.version(name) for name in ('torch', 'transformers', 'tokenizers', 'safetensors')},
            'python': platform.python_version()}


def config_hash(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def new_model(config):
    return GPT2LMHeadModel(GPT2Config(vocab_size=config['vocabSize'], n_positions=config['contextLength'],
        n_ctx=config['contextLength'], n_embd=config['hiddenSize'], n_layer=config['layers'], n_head=config['heads'],
        n_inner=config['hiddenSize']*4, resid_pdrop=0, embd_pdrop=0, attn_pdrop=0,
        pad_token_id=0, bos_token_id=2, eos_token_id=3, use_cache=False, attn_implementation='eager'))


def batch(record, device):
    return {key: torch.tensor([record[key]], dtype=torch.long, device=device) for key in ('input_ids', 'attention_mask', 'labels')}


def evaluate(model, records, device):
    model.eval()
    weighted = targets = 0
    with torch.no_grad():
        for record in records:
            inputs = batch(record, device)
            count = (inputs['labels'][:, 1:] != -100).sum().item()
            loss = model(**inputs, use_cache=False).loss.item()
            if not math.isfinite(loss):
                raise ValueError('Evaluation produced a nonfinite loss.')
            weighted += loss * count
            targets += count
    return weighted / targets


def step_model(model, optimizer, record, device):
    model.train()
    optimizer.zero_grad(set_to_none=True)
    loss = model(**batch(record, device), use_cache=False).loss
    if not torch.isfinite(loss):
        raise ValueError('Nonfinite training loss; stop and inspect data/settings.')
    loss.backward()
    parameters = [p for p in model.parameters() if p.grad is not None]
    if not parameters or any(not torch.isfinite(p.grad).all() for p in parameters):
        raise ValueError('Nonfinite or missing gradients; training stopped.')
    norm = torch.nn.utils.clip_grad_norm_(parameters, 1.0, error_if_nonfinite=True)
    optimizer.step()
    if any(not torch.isfinite(p).all() for p in model.parameters()):
        raise ValueError('Optimizer produced nonfinite weights.')
    return loss.item(), norm.item()


def save_checkpoint(model, optimizer, directory, step, config, identity, device, initial_loss, subset_size):
    temporary = directory / f'.tmp-{step}'
    final = directory / f'step-{step:06d}'
    temporary.mkdir(parents=True, exist_ok=False)
    model.config._name_or_path = ''
    model.save_pretrained(temporary, safe_serialization=True)
    write_json(temporary / 'training-configuration.json', config)
    schedule = {'name': 'constant', 'warmupSteps': 0, 'learningRate': config['learningRate']}
    state = {'optimizer': optimizer.state_dict(), 'step': step, 'torchRng': torch.get_rng_state(),
             'cudaRng': [s.cpu() for s in torch.cuda.get_rng_state_all()] if device == 'cuda' else [],
             'pythonRng': random.getstate(), 'initialLoss': initial_loss, 'configHash': config_hash(config),
             'sourceIdentity': identity, 'versions': versions(), 'device': device,
             'deviceName': torch.cuda.get_device_name(0) if device == 'cuda' else 'CPU',
             'configuration': config, 'schedule': schedule, 'subsetSize': subset_size, 'subsetCursor': step % subset_size}
    torch.save(state, temporary / 'training-state.pt')
    files = {p.name: describe(p) for p in temporary.iterdir() if p.is_file()}
    write_json(temporary / 'checkpoint.json', {'step': step, 'configHash': config_hash(config),
               'sourceIdentity': identity, 'versions': versions(), 'device': device,
               'deviceName': state['deviceName'], 'schedule': schedule,
               'subsetSize': subset_size, 'subsetCursor': state['subsetCursor'], 'files': files})
    temporary.rename(final)
    return final


def load_checkpoint(path, config, identity, device):
    info = json.loads((path/'checkpoint.json').read_text())
    for filename, entry in info['files'].items():
        file = (path / filename).resolve()
        if not file.is_relative_to(path.resolve()) or file.stat().st_size != entry['sizeBytes'] or digest(file) != entry['sha256']:
            raise ValueError('Checkpoint integrity check failed.')
    if info['configHash'] != config_hash(config) or info['sourceIdentity'] != identity:
        raise ValueError('Checkpoint source/configuration differs from this run.')
    if info['versions'] != versions() or info['device'] != device:
        raise ValueError('Exact resume/reload requires the saved runtime versions and device.')
    if info['deviceName'] != (torch.cuda.get_device_name(0) if device == 'cuda' else 'CPU'):
        raise ValueError('Resume/reload requires the original device model.')
    model = GPT2LMHeadModel.from_pretrained(path, local_files_only=True, attn_implementation='eager').to(device)
    state = torch.load(path/'training-state.pt', weights_only=True, map_location='cpu')
    if state['configuration'] != config or state['schedule'] != {'name': 'constant', 'warmupSteps': 0, 'learningRate': config['learningRate']}:
        raise ValueError('Checkpoint training settings/schedule differ from this run.')
    optimizer = torch.optim.AdamW(model.parameters(), lr=config['learningRate'], weight_decay=0)
    optimizer.load_state_dict(state['optimizer'])
    torch.set_rng_state(state['torchRng'])
    if state['cudaRng']:
        torch.cuda.set_rng_state_all(state['cudaRng'])
    random.setstate(state['pythonRng'])
    return model, optimizer, state


def execute(directory, checkpoints, emit):
    config = json.loads((directory/'configuration.json').read_text())
    request = json.loads((directory/'request.json').read_text())
    records = [json.loads(line) for line in (directory/'subset.jsonl').read_text().splitlines()]
    if not records or len(records) > 2:
        raise ValueError('Expected one or two fixed training sequences.')
    targets = [validate_record(r, config['vocabSize'], config['contextLength']) for r in records]
    device = request['device']
    if device not in ('cpu', 'cuda'):
        raise ValueError('Unsupported training device.')
    torch.set_num_threads(2)
    torch.manual_seed(config['seed'])
    random.seed(config['seed'])
    torch.use_deterministic_algorithms(True)
    if device == 'cuda':
        if not torch.cuda.is_available():
            raise ValueError('CUDA became unavailable. Select CPU explicitly or repair CUDA.')
        torch.cuda.manual_seed_all(config['seed'])
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.cuda.reset_peak_memory_stats()
    emit({'stage': 'initializing'})
    started = time.monotonic()
    identity = request['sourceIdentity']
    if request.get('resumePath'):
        model, optimizer, state = load_checkpoint(Path(request['resumePath']), config, identity, device)
        start_step, initial_loss = state['step'], state['initialLoss']
        if state['subsetSize'] != len(records) or state['subsetCursor'] != start_step % len(records):
            raise ValueError('Checkpoint subset size/cursor differs from this run.')
    else:
        model = new_model(config).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=config['learningRate'], weight_decay=0)
        start_step = 0
        initial_loss = evaluate(model, records, device)
    if start_step >= config['maxSteps']:
        raise ValueError('Checkpoint already reached the requested total steps.')
    initial_weights = next(model.parameters()).detach().cpu().clone()
    resumed_start_loss = evaluate(model, records, device)
    measured = sum(p.numel() for p in model.parameters())
    if measured != config['estimatedParameters']:
        raise ValueError('Measured model size differs from validated configuration.')
    emit({'stage': 'training', 'step': start_step, 'maxSteps': config['maxSteps'], 'initialLoss': initial_loss,
          'startLoss': resumed_start_loss, 'parameters': measured, 'device': device})
    last_checkpoint = None
    for index in range(start_step, config['maxSteps']):
        if time.monotonic() - started > config['timeLimitSeconds']:
            raise ValueError('Smoke-test time limit exceeded; lower sequence length/model size or use a working GPU.')
        if device == 'cuda': torch.cuda.synchronize()
        tick = time.monotonic()
        position = index % len(records)
        loss, gradient_norm = step_model(model, optimizer, records[position], device)
        if device == 'cuda': torch.cuda.synchronize()
        duration = time.monotonic() - tick
        step = index + 1
        emit({'stage': 'training', 'step': step, 'maxSteps': config['maxSteps'], 'loss': loss,
              'gradientNorm': gradient_norm, 'stepSeconds': duration, 'targetTokensPerSecond': targets[position]/duration,
              'rssBytes': psutil.Process().memory_info().rss,
              'cudaPeakAllocatedBytes': torch.cuda.max_memory_allocated() if device == 'cuda' else None,
              'cudaPeakReservedBytes': torch.cuda.max_memory_reserved() if device == 'cuda' else None})
        if step % config['checkpointEvery'] == 0 or step == config['maxSteps']:
            last_checkpoint = save_checkpoint(model, optimizer, checkpoints, step, config, identity, device, initial_loss, len(records))
        if sum(p.stat().st_size for p in checkpoints.rglob('*') if p.is_file()) > 1024**3:
            raise ValueError('Checkpoint storage exceeded the 1 GiB run limit.')
    emit({'stage': 'verifying'})
    final_loss = evaluate(model, records, device)
    changed = not torch.equal(initial_weights, next(model.parameters()).detach().cpu())
    if not changed:
        raise ValueError('Training did not change model weights.')
    model.eval()
    with torch.no_grad():
        reference = model(**batch(records[0], device), use_cache=False)
    torch.save({'logits': reference.logits[:, :8].cpu(), 'loss': reference.loss.cpu()}, directory/'reload-reference.pt')
    result = {'initialLoss': initial_loss, 'startLoss': resumed_start_loss, 'finalLoss': final_loss,
              'lossDecreaseRatio': (initial_loss-final_loss)/initial_loss, 'weightsChanged': changed,
              'finiteGradients': True, 'parameters': measured, 'completedSteps': config['maxSteps'],
              'startingStep': start_step, 'subsetSequences': len(records), 'subsetTargets': sum(targets),
              'device': device, 'versions': versions(), 'finalCheckpoint': str(last_checkpoint),
              'trainingSeconds': time.monotonic()-started, 'scope': 'train-subset diagnostic; no held-out evaluation'}
    write_json(directory/'training-result.json', result)
    return result
