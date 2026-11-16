"""Real isolated executor integration. Explicit setup is required for this suite."""
import hashlib
import io
import json
from pathlib import Path
import threading
from uuid import uuid4
import zipfile

import psycopg
from psycopg.rows import dict_row
import pytest

from app.training.jobs import claim_smoke, execute_smoke
from app.training.runtime import inspect_runtime
from test_smoke_api import studio, config_source

pytestmark=pytest.mark.skipif(not (Path(__file__).resolve().parents[2]/'.venv-training/studio-runtime.json').exists(),
                             reason='Explicit .venv-training setup required; this is not a passed numerical test.')


def run_next(client,database):
    with psycopg.connect(database,autocommit=True,row_factory=dict_row) as conn:
        row=claim_smoke(conn,uuid4());assert row
        execute_smoke(conn,client.app.state.data_root,row,threading.Event())


def test_real_cpu_smoke_reload_resume_download_and_lineage(studio,test_database):
    client=studio
    base,dataset_path,tokenizer,sequence,config=config_source(client,test_database)
    original={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in client.app.state.data_root.rglob('*') if p.is_file()}
    response=client.post(base+'/smoke-runs',json={'modelConfigId':config['id']});assert response.status_code==202,response.text
    run=response.json();url=base+'/smoke-runs/'+run['id']
    run_next(client,test_database)
    run=client.get(url).json();assert run['status']=='completed',run['error']
    report=run['manifest']['report']
    assert report['finiteGradients'] and report['weightsChanged'] and report['reloadMatches']
    assert report['completedSteps']==100 and report['parameters']==config['configuration']['estimatedParameters']
    assert report['finalLoss']<report['initialLoss'] and run['verdict']=='passed'
    assert [c['step'] for c in run['checkpoints']]==[50,100]
    events=client.get(url+'/metrics?afterStep=50').json()['events'];assert len(events)==50 and events[0]['step']==51
    complete=client.get(url+'/download?artifact=bundle');assert complete.status_code==200
    assert hashlib.sha256(complete.content).hexdigest()==run['manifest']['artifacts']['bundle']['sha256']
    with zipfile.ZipFile(io.BytesIO(complete.content)) as archive:
        assert archive.testzip() is None
        assert 'checkpoints/step-000100/model.safetensors' in archive.namelist()
        assert 'checkpoints/step-000100/training-state.pt' in archive.namelist()
        assert json.loads(archive.read('checkpoints/step-000100/training-configuration.json'))==config['configuration']
        assert 'subset.jsonl' not in archive.namelist() and 'request.json' not in archive.namelist()
    cp=run['checkpoints'][0]
    download=client.get(url+'/checkpoints/'+cp['id']+'/download');assert download.status_code==200
    assert hashlib.sha256(download.content).hexdigest()==cp['sha256']
    resume=client.post(url+'/resume',json={'checkpointId':cp['id']});assert resume.status_code==202,resume.text
    child_url=base+'/smoke-runs/'+resume.json()['id']
    assert client.delete(url).status_code==409
    run_next(client,test_database)
    child=client.get(child_url).json();assert child['status']=='completed',child['error']
    assert child['parentRunId']==run['id'] and child['manifest']['report']['startingStep']==50
    assert child['manifest']['report']['finalLoss']==pytest.approx(report['finalLoss'],abs=1e-7)
    for p,digest in original.items():assert hashlib.sha256(p.read_bytes()).hexdigest()==digest
    assert client.delete(base+'/sequence-runs/'+sequence['id']).status_code==409
    assert client.delete(base+'/model-configs/'+config['id']).status_code==409
    assert client.delete(child_url).status_code==200
    assert client.delete(url).status_code==200
    assert client.delete(base+'/model-configs/'+config['id']).status_code==200
    assert client.delete(base+'/sequence-runs/'+sequence['id']).status_code==200
    assert client.delete(base+'/tokenizers/'+tokenizer['id']).status_code==200
    assert client.delete(dataset_path).status_code==200


def test_real_cuda_smoke_when_runtime_supports_it(studio,test_database):
    report=inspect_runtime(force=True)
    if not report.get('cuda'):
        pytest.skip('CUDA runtime unavailable; CPU coverage is separate and GPU is not marked verified.')
    base,_,_,sequence,_=config_source(studio,test_database)
    response=studio.post(base+'/model-configs',json={'sequenceRunId':sequence['id'],'settings':{'hiddenSize':64,'maxSteps':50,'device':'cuda','prompt':'Hello'}})
    assert response.status_code==201,response.text
    response=studio.post(base+'/smoke-runs',json={'modelConfigId':response.json()['id']});assert response.status_code==202,response.text
    url=base+'/smoke-runs/'+response.json()['id'];run_next(studio,test_database)
    run=studio.get(url).json();assert run['status']=='completed',run['error']
    assert run['manifest']['report']['device']=='cuda' and run['manifest']['report']['reloadMatches']
    assert run['metrics']['cudaPeakAllocatedBytes']>0 and run['metrics']['cudaPeakReservedBytes']>0
