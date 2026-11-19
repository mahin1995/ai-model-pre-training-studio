import copy
import json

import pytest
import torch

from app.training.core import execute, load_checkpoint
from app.training.data import write_json
from app.training.pilot import checkpoint_steps, coverage, epoch_order, record_identity
from test_numerical_smoke import records, settings


def test_every_block_coverage_padding_and_exact_resume(tmp_path):
    rows = records() + [copy.deepcopy(records()[0])]
    rows[-1]['input_ids'][1] = rows[-1]['labels'][1] = 20
    cfg = {**settings(), 'trainingKind': 'pilot', 'epochs': 3, 'maxSteps': 9,
           'trainingBlocks': 3, 'recordsSha256': record_identity(rows), 'checkpointSteps': [3, 6, 9]}

    def run(name, resume=None, stop=False):
        directory = tmp_path / name
        directory.mkdir()
        checkpoints = directory / 'checkpoints'
        checkpoints.mkdir()
        write_json(directory / 'configuration.json', cfg)
        write_json(directory / 'request.json', {'device': 'cpu', 'sourceIdentity': 'pilot-fixture',
                                               'resumePath': str(resume) if resume else None})
        (directory / 'train.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        events = []
        def emit(event):
            events.append(event)
            if stop and event.get('step') == 5:
                raise ValueError('interrupted fixture')
        if stop:
            with pytest.raises(ValueError, match='interrupted fixture'):
                execute(directory, checkpoints, emit)
            return checkpoints, events, None
        result = execute(directory, checkpoints, emit)
        return checkpoints, events, result

    full, events, report = run('full')
    assert report['coverage']['completedEpochs'] == 3
    assert report['coverage']['uniqueBlocksVisited'] == 3
    assert report['coverage']['targetTokensPerEpoch'] == 14
    assert report['coverage']['targetExposures'] == 42
    updates = [e for e in events if 'loss' in e]
    assert len(updates) == 9
    for epoch in range(3):
        assert [e['blockIndex'] for e in updates[epoch*3:(epoch+1)*3]] == epoch_order(3, 42, epoch)
    partial, _, _ = run('interrupted', stop=True)
    resumed, _, other_report = run('resumed', partial / 'step-000003')
    first, opt, state = load_checkpoint(full / 'step-000009', cfg, 'pilot-fixture', 'cpu')
    other, other_opt, other_state = load_checkpoint(resumed / 'step-000009', cfg, 'pilot-fixture', 'cpu')
    assert other_report['startingStep'] == 3 and other_report['coverage'] == report['coverage']
    assert other_report['finalLoss'] == pytest.approx(report['finalLoss'], abs=1e-8)
    assert state['coverage'] == other_state['coverage'] == coverage(9, rows, 42)
    assert 'subsetSize' not in state
    for key, value in first.state_dict().items():
        torch.testing.assert_close(value, other.state_dict()[key], rtol=0, atol=0)
    for key, value in opt.state_dict()['state'].items():
        for field, tensor in value.items():
            torch.testing.assert_close(tensor, other_opt.state_dict()['state'][key][field], rtol=0, atol=0)
    # Same checkpoint bytes cannot be resumed with a modified immutable config.
    with pytest.raises(ValueError, match='configuration'):
        load_checkpoint(full / 'step-000009', {**cfg, 'epochs': 4}, 'pilot-fixture', 'cpu')


def test_checkpoint_budget_and_partial_coverage():
    assert checkpoint_steps(7, 3) == [7, 14, 21]
    assert checkpoint_steps(7, 20) == [35, 70, 105, 140]
    assert checkpoint_steps(7, 1) == [7]
    value = coverage(1, records(), 42)
    assert value['completedEpochs'] == 0 and value['epochOffset'] == 1
    assert value['uniqueBlocksVisited'] == 1 and value['blockExposures'] == 1
