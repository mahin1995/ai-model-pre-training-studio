import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from uuid import uuid4
import zipfile

from fastapi.testclient import TestClient
import psycopg
from psycopg.rows import dict_row
import pytest

from app.main import create_app
from app.models.schemas import PilotSettings, pilot_configuration
from app.training.jobs import claim_smoke, execute_smoke, recover_smoke
from app.inference.jobs import claim_inference, execute_inference
from test_dataset_corrections import prepared, run_job, save_all
from test_tokenizers_api import execute, train, source

pytestmark = pytest.mark.skipif(not (Path(__file__).resolve().parents[2] / '.venv-training/studio-runtime.json').exists(),
                                 reason='Explicit CPU training runtime required.')


def run_training(client, database):
    with psycopg.connect(database, autocommit=True, row_factory=dict_row) as conn:
        row = claim_smoke(conn, uuid4())
        assert row
        execute_smoke(conn, client.app.state.data_root, row, threading.Event())


def run_inference(client, database):
    with psycopg.connect(database, autocommit=True, row_factory=dict_row) as conn:
        row = claim_inference(conn, uuid4())
        assert row
        execute_inference(conn, client.app.state.data_root, row, threading.Event())


@pytest.fixture(scope='module')
def pilot_workspace(test_database, tmp_path_factory):
    root = tmp_path_factory.mktemp('pilot-data')
    previous = os.environ.get('STUDIO_DATA_DIR')
    os.environ['STUDIO_DATA_DIR'] = str(root)
    try:
        with TestClient(create_app(test_database, enable_worker=False)) as client:
            path, detail, parent = prepared(client, test_database, pdf=True)
            texts = {i: (f'Training page {i}. Alpha beta gamma delta epsilon. ' * 80) for i in (1, 2, 3)}
            url, revision = save_all(client, path, parent, texts)
            assert client.post(url + '/publish', json={'revision': revision}).status_code == 202
            run_job(client, test_database)
            version = client.get(path).json()['versions'][0]
            base = f"/api/projects/{detail['projectId']}"
            tokenizer = train(client, test_database, base, version)
            sequence = client.post(base + '/sequence-runs', json={'tokenizerRunId': tokenizer['id'], 'sequenceLength': 128}).json()
            execute(client, test_database)
            response = client.post(base + '/model-configs', json={'trainingKind': 'pilot', 'name': 'All blocks',
                'sequenceRunId': sequence['id'], 'settings': {'hiddenSize': 64, 'epochs': 3, 'prompt': 'Training'}})
            assert response.status_code == 201, response.text
            config = response.json()
            original = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
            yield client, {'base': base, 'config': config, 'sequence': sequence, 'dataset': path, 'version': version,
                           'tokenizer': tokenizer, 'original': original}
    finally:
        if previous is None:
            os.environ.pop('STUDIO_DATA_DIR', None)
        else:
            os.environ['STUDIO_DATA_DIR'] = previous


def test_pilot_preview_limits_and_mode_isolation(pilot_workspace, test_database):
    client, data = pilot_workspace
    base, config = data['base'], data['config']
    count = config['configuration']['trainingBlocks']
    assert count > 2 and config['trainingKind'] == 'pilot'
    assert config['configuration']['maxSteps'] == count * 3
    assert config['configuration']['checkpointSteps'] == [count, count*2, count*3]
    assert 'subsetSize' not in config['configuration']
    response = client.post(base + '/pilot-preview', json={'modelConfigId': config['id']})
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview['totalSteps'] == count * 3 and preview['trainingDocuments'] == 1
    assert preview['targetTokensPerEpoch'] > 0
    assert client.get(base + '/pilot-runs').json() == []
    assert client.post(base + '/smoke-runs', json={'modelConfigId': config['id']}).status_code == 409
    for bad in ({'epochs': True}, {'epochs': 0}, {'epochs': 21}, {'device': 'cuda'}, {'maxSteps': 100}):
        response = client.post(base + '/model-configs', json={'trainingKind': 'pilot', 'sequenceRunId': data['sequence']['id'], 'settings': bad})
        assert response.status_code == 422, response.text
    assert client.post('/api/projects/' + str(uuid4()) + '/pilot-preview', json={'modelConfigId': config['id']}).status_code == 404
    rows = [{'attention_mask': [1, 1]}] * 256
    with pytest.raises(ValueError, match='2,000'):
        pilot_configuration(PilotSettings(epochs=20).model_dump(), 260, 128, rows)
    with pytest.raises(ValueError, match='256'):
        pilot_configuration(PilotSettings().model_dump(), 260, 128, rows + rows)
    with pytest.raises(ValueError, match='GiB'):
        pilot_configuration(PilotSettings(hiddenSize=256, epochs=4).model_dump(), 23000, 128, rows[:3])


def test_real_all_blocks_export_resume_and_existing_inference(pilot_workspace, test_database):
    client, data = pilot_workspace
    base, config = data['base'], data['config']
    count = config['configuration']['trainingBlocks']
    response = client.post(base + '/pilot-runs', json={'modelConfigId': config['id']})
    assert response.status_code == 202, response.text
    url = base + '/pilot-runs/' + response.json()['id']
    run_training(client, test_database)
    run = client.get(url).json()
    assert run['status'] == 'completed', run['error']
    data['run'] = run
    assert run['verdict'] is None
    report = run['manifest']['report']
    assert report['reloadMatches'] and report['weightsChanged'] and report['finiteGradients']
    assert report['coverage']['completedEpochs'] == 3
    assert report['coverage']['uniqueBlocksVisited'] == count
    assert report['coverage']['blockExposures'] == 3*count
    assert 'subsetSequences' not in report
    events = client.get(url + '/metrics').json()['events']
    assert len(events) == count*3
    for offset in range(3):
        assert sorted(e['blockIndex'] for e in events[offset*count:(offset+1)*count]) == list(range(count))
    assert report['coverage']['targetExposures'] == 3 * sum(e['targetTokensPerEpoch'] for e in events[:1])
    bundle = client.get(url + '/download').content
    assert hashlib.sha256(bundle).hexdigest() == run['manifest']['artifacts']['bundle']['sha256']
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        assert archive.testzip() is None
        assert 'coverage.json' in archive.namelist() and 'USAGE.txt' in archive.namelist()
        assert 'train.jsonl' not in archive.namelist() and 'request.json' not in archive.namelist()
    assert client.get(url + '/download?artifact=coverage').json() == report['coverage']
    assert client.get(base + '/smoke-runs/' + run['id']).status_code == 404
    assert not any(r['id'] == run['id'] for r in client.get(base + '/smoke-runs').json())
    resume = client.post(url + '/resume', json={'checkpointId': run['checkpoints'][0]['id']})
    assert resume.status_code == 202, resume.text
    assert client.delete(url).status_code == 409
    run_training(client, test_database)
    child = client.get(base + '/pilot-runs/' + resume.json()['id']).json()
    assert child['status'] == 'completed', child['error']
    assert child['manifest']['report']['startingStep'] == count
    assert child['manifest']['report']['coverage'] == report['coverage']
    assert child['manifest']['report']['finalLoss'] == pytest.approx(report['finalLoss'], abs=1e-7)
    assert client.post(url + '/resume', json={'checkpointId': run['checkpoints'][-1]['id']}).status_code == 409
    cp = run['checkpoints'][-1]
    generation = client.post(base + '/generation-runs', json={'checkpointId': cp['id'], 'prompt': 'Training', 'maxNewTokens': 8})
    assert generation.status_code == 202, generation.text
    run_inference(client, test_database)
    generated = client.get(base + '/generation-runs/' + generation.json()['id']).json()
    assert generated['status'] == 'completed', generated['error']
    prompts = client.post(base + '/prompt-sets', json={'name': 'Pilot prompts', 'prompts': [{'text': 'Training'}]}).json()
    for scope in ('training', 'validation'):
        evaluation = client.post(base + '/evaluation-runs', json={'checkpointIds': [cp['id']], 'promptSetVersionId': prompts['id'], 'maxNewTokens': 8, 'metricScope': scope})
        assert evaluation.status_code == 202, evaluation.text
        run_inference(client, test_database)
        evaluated = client.get(base + '/evaluation-runs/' + evaluation.json()['id']).json()
        assert evaluated['status'] == 'completed', evaluated['error']
        metrics = evaluated['manifest']['report']['results'][0]['metrics']
        assert metrics['trainedSubset']['blocks'] == count
        assert metrics['primary']['blocks'] == (count if scope == 'training' else 0)
        if scope == 'validation':
            assert metrics['primary']['loss'] is None
    from test_dataset_corrections import META
    raw = '\n'.join(json.dumps({'text': f'Independent astronomy record {i}: distant stars and planets.', 'group_id': str(i)}) for i in range(3)).encode()
    imported = client.post(base + '/datasets', data={'metadata': json.dumps({**META, 'name': 'Pilot external evaluation'})},
                           files=[('files', ('external.jsonl', raw))])
    assert imported.status_code == 201, imported.text
    external_path = base + '/datasets/' + imported.json()['id']
    assert client.post(external_path + '/process', json={'train': 100, 'validation': 0, 'test': 0}).status_code == 202
    run_job(client, test_database)
    parent = client.get(external_path).json()['versions'][0]
    edit, revision = save_all(client, external_path, parent)
    assert client.post(edit + '/publish', json={'revision': revision}).status_code == 202
    run_job(client, test_database)
    external = client.get(external_path).json()['versions'][0]
    evaluation = client.post(base + '/evaluation-runs', json={'checkpointIds': [cp['id']], 'promptSetVersionId': prompts['id'],
                             'maxNewTokens': 8, 'metricScope': 'external', 'externalDatasetVersionId': external['id']})
    assert evaluation.status_code == 202, evaluation.text
    run_inference(client, test_database)
    evaluated = client.get(base + '/evaluation-runs/' + evaluation.json()['id']).json()
    assert evaluated['status'] == 'completed', evaluated['error']
    metric = evaluated['manifest']['report']['results'][0]['metrics']
    assert metric['heldOutAvailable'] and metric['primary']['documents'] == 3
    assert metric['trainedSubset']['blocks'] == count
    for path, digest in data['original'].items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert client.delete(base + '/model-configs/' + config['id']).status_code == 409
    assert client.delete(data['dataset']).status_code == 409
    assert client.delete(base + '/sequence-runs/' + data['sequence']['id']).status_code == 409


def test_pilot_queued_cancel_retry_recovery_and_hash_gate(pilot_workspace, test_database, monkeypatch):
    client, data = pilot_workspace
    base, config = data['base'], data['config']
    response = client.post(base + '/pilot-runs', json={'modelConfigId': config['id']})
    assert response.status_code == 202, response.text
    url = base + '/pilot-runs/' + response.json()['id']
    assert client.post(url + '/retry').status_code == 409
    assert client.post(url + '/cancel').json()['status'] == 'cancelled'
    retry = client.post(url + '/retry').json()
    with psycopg.connect(test_database, autocommit=True, row_factory=dict_row) as conn:
        claimed = claim_smoke(conn, uuid4())
        assert str(claimed['id']) == retry['id']
        conn.execute("UPDATE smoke_runs SET heartbeat_at=now()-interval '61 seconds' WHERE id=%s", (retry['id'],))
        recover_smoke(conn, client.app.state.data_root)
        row = conn.execute('SELECT storage_key FROM sequence_runs WHERE id=%s', (data['sequence']['id'],)).fetchone()
    assert client.get(base + '/pilot-runs/' + retry['id']).json()['status'] == 'failed'
    target = client.app.state.data_root / row['storage_key'] / 'train.jsonl'
    original = target.read_bytes()
    try:
        target.write_bytes(original + b'\n')
        assert client.post(base + '/pilot-preview', json={'modelConfigId': config['id']}).status_code == 409
        assert client.post(base + '/pilot-runs', json={'modelConfigId': config['id']}).status_code == 409
    finally:
        target.write_bytes(original)


def test_failed_parent_checkpoint_resume_and_runtime_integrity(pilot_workspace, test_database, monkeypatch):
    client, data = pilot_workspace
    base, config = data['base'], data['config']
    response = client.post(base + '/pilot-runs', json={'modelConfigId': config['id']})
    assert response.status_code == 202, response.text
    url = base + '/pilot-runs/' + response.json()['id']
    real_popen = subprocess.Popen
    def fail_verification(args, **kwargs):
        if 'app.training.verify_process' in args:
            return real_popen([str(__import__('sys').executable), '-c', 'raise SystemExit(1)'], **kwargs)
        return real_popen(args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr('app.training.jobs.subprocess.Popen', fail_verification)
        run_training(client, test_database)
    failed = client.get(url).json()
    assert failed['status'] == 'failed' and len(failed['checkpoints']) == 3
    cp = failed['checkpoints'][0]
    with psycopg.connect(test_database, autocommit=True, row_factory=dict_row) as conn:
        row = conn.execute('SELECT * FROM smoke_checkpoints WHERE id=%s', (cp['id'],)).fetchone()
    weights = client.app.state.data_root / row['storage_key'] / 'model.safetensors'
    original = weights.read_bytes()
    try:
        weights.write_bytes(b'corrupt')
        assert client.post(url + '/resume', json={'checkpointId': cp['id']}).status_code == 409
    finally:
        weights.write_bytes(original)
    from app.training.runtime import inspect_runtime
    runtime = inspect_runtime()
    with monkeypatch.context() as patch:
        patch.setattr('app.training.runtime.inspect_runtime', lambda **kwargs: {**runtime, 'versions': {'torch': 'different'}})
        assert client.post(url + '/resume', json={'checkpointId': cp['id']}).status_code == 409
    resume = client.post(url + '/resume', json={'checkpointId': cp['id']})
    assert resume.status_code == 202, resume.text
    run_training(client, test_database)
    child = client.get(base + '/pilot-runs/' + resume.json()['id']).json()
    assert child['status'] == 'completed', child['error']
    assert child['manifest']['report']['coverage']['completedEpochs'] == 3
    with psycopg.connect(test_database, autocommit=True, row_factory=dict_row) as conn:
        parent_cp = conn.execute('SELECT manifest FROM smoke_checkpoints WHERE id=%s', (failed['checkpoints'][-1]['id'],)).fetchone()
        child_cp = conn.execute('SELECT manifest FROM smoke_checkpoints WHERE id=%s', (child['checkpoints'][-1]['id'],)).fetchone()
    assert parent_cp['manifest']['checkpoint']['files']['model.safetensors']['sha256'] == child_cp['manifest']['checkpoint']['files']['model.safetensors']['sha256']


def test_native_pilot_cancel_and_timeout(pilot_workspace, test_database, monkeypatch):
    from test_smoke_api import runtime_stub
    client, data = pilot_workspace
    base, config = data['base'], data['config']
    runtime_stub(monkeypatch)
    real_popen = subprocess.Popen
    children = []
    started = threading.Event()
    def sleeping_child(*args, **kwargs):
        child = real_popen([str(__import__('sys').executable), '-c', 'import time;time.sleep(30)'], **kwargs)
        children.append(child)
        started.set()
        return child
    monkeypatch.setattr('app.training.jobs.subprocess.Popen', sleeping_child)
    response = client.post(base + '/pilot-runs', json={'modelConfigId': config['id']})
    assert response.status_code == 202, response.text
    url = base + '/pilot-runs/' + response.json()['id']
    worker = threading.Thread(target=run_training, args=(client, test_database))
    worker.start()
    assert started.wait(10)
    assert client.post(url + '/cancel').status_code == 200
    worker.join(8)
    assert not worker.is_alive() and children[-1].poll() is not None
    assert client.get(url).json()['status'] == 'cancelled'
    response = client.post(url + '/retry')
    assert response.status_code == 202, response.text
    with psycopg.connect(test_database, autocommit=True, row_factory=dict_row) as conn:
        claimed = claim_smoke(conn, uuid4())
        claimed['configuration']['timeLimitSeconds'] = 1
        execute_smoke(conn, client.app.state.data_root, claimed, threading.Event())
    timed = client.get(base + '/pilot-runs/' + response.json()['id']).json()
    assert timed['status'] == 'failed' and 'time limit' in timed['error']
    assert children[-1].poll() is not None
