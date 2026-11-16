import json
import subprocess
import threading
import time
from uuid import uuid4

from fastapi.testclient import TestClient
import psycopg
from psycopg.rows import dict_row
import pytest

from app.main import create_app
from app.models.schemas import SmokeSettings, configuration
from app.training.jobs import claim_smoke, execute_smoke, recover_smoke
from app.training.runtime import child_environment
from test_tokenizers_api import source, train, execute


@pytest.fixture
def studio(test_database, tmp_path, monkeypatch):
    monkeypatch.setenv('STUDIO_DATA_DIR',str(tmp_path))
    with TestClient(create_app(test_database,enable_worker=False)) as client:
        yield client


def sequence_source(client,database):
    base,path,detail,version=source(client,database,pdf=True)
    tokenizer=train(client,database,base,version)
    response=client.post(base+'/sequence-runs',json={'tokenizerRunId':tokenizer['id'],'sequenceLength':128})
    assert response.status_code==202,response.text
    sequence=response.json()
    execute(client,database)
    return base,path,tokenizer,sequence


def config_source(client,database):
    base,path,tokenizer,sequence=sequence_source(client,database)
    response=client.post(base+'/model-configs',json={'sequenceRunId':sequence['id'],'settings':{'hiddenSize':64,'maxSteps':100,'device':'cpu','prompt':'Hello'}})
    assert response.status_code==201,response.text
    return base,path,tokenizer,sequence,response.json()


def runtime_stub(monkeypatch):
    report={'scope':'training-runtime','ready':True,'cpu':True,'cuda':False,'versions':{'torch':'test'},'action':'setup','message':'CPU tested'}
    monkeypatch.setattr('app.training.runtime.inspect_runtime',lambda **kwargs:report)
    return report


def test_immutable_config_derived_fields_and_project_isolation(studio,test_database):
    client=studio
    base,path,tokenizer,seq,config=config_source(client,test_database)
    assert config['configuration']['vocabSize']==tokenizer['manifest']['actualVocabSize']
    assert config['configuration']['contextLength']==128
    assert config['configuration']['specialIds']['[EOS]']==3
    assert config['source']['sequenceRunId']==seq['id']
    assert 'storage_key' not in json.dumps(config)
    assert client.get(base+'/model-configs/'+config['id']).json()==config
    assert client.get(base+'/model-configs/'+config['id']+'/export').json()==config
    assert client.patch(base+'/model-configs/'+config['id'],json={'name':'overwrite'}).status_code in (404,405)
    response=client.post(base+'/model-configs',json={'sequenceRunId':seq['id'],'name':'Second immutable revision'})
    assert response.status_code==201
    assert response.json()['revision']==config['revision']+1
    assert client.get(base+'/model-configs/'+config['id']).json()==config
    for bad in ({'layers':True},{'hiddenSize':65},{'heads':3},{'maxSteps':501},{'learningRate':0},{'prompt':'বাংলা'*2000}):
        assert client.post(base+'/model-configs',json={'sequenceRunId':seq['id'],'settings':bad}).status_code==422
    assert client.post(base+'/model-configs',json={'sequenceRunId':seq['id'],'settings':{'prompt':'x'*3000}}).status_code==409
    assert client.post(base+'/model-configs',json={'sequenceRunId':seq['id'],'vocabSize':8000}).status_code==422
    other='/api/projects/'+str(uuid4())
    assert client.get(other+'/model-configs/'+config['id']).status_code==404
    assert client.post(other+'/model-configs',json={'sequenceRunId':seq['id']}).status_code==404
    assert client.delete(base+'/sequence-runs/'+seq['id']).status_code==409
    assert client.delete(path).status_code==409


def test_missing_runtime_queue_cancel_retry_and_recovery(studio,test_database,monkeypatch):
    client=studio
    base,_,_,_,config=config_source(client,test_database)
    monkeypatch.setenv('STUDIO_TRAINING_PYTHON','/nonexistent/studio-python')
    assert client.get(base+'/training-runtime?refresh=true').json()['ready'] is False
    assert client.post(base+'/smoke-runs',json={'modelConfigId':config['id']}).status_code==409
    runtime_stub(monkeypatch)
    run=client.post(base+'/smoke-runs',json={'modelConfigId':config['id']})
    assert run.status_code==202,run.text
    run=run.json();url=base+'/smoke-runs/'+run['id']
    assert client.get('/api/projects/'+str(uuid4())+'/smoke-runs/'+run['id']).status_code==404
    assert client.post(url+'/retry').status_code==409
    assert client.delete(url).status_code==409
    assert client.delete(base+'/model-configs/'+config['id']).status_code==409
    assert client.get(url+'/download?artifact=../secret').status_code==422
    assert client.get(url+'/download').status_code==409
    assert client.get(url+'/metrics').json()['events']==[]
    assert client.post(url+'/cancel').json()['status']=='cancelled'
    assert client.post(url+'/resume',json={'checkpointId':str(uuid4())}).status_code==409
    next_run=client.post(url+'/retry').json()
    with psycopg.connect(test_database,autocommit=True,row_factory=dict_row) as conn:
        claimed=claim_smoke(conn,uuid4());assert str(claimed['id'])==next_run['id']
        conn.execute("UPDATE smoke_runs SET heartbeat_at=now()-interval '61 seconds',status='training' WHERE id=%s",(next_run['id'],))
        recover_smoke(conn,client.app.state.data_root)
    assert client.get(base+'/smoke-runs/'+next_run['id']).json()['status']=='failed'
    assert client.delete(url).status_code==200
    assert client.delete(base+'/smoke-runs/'+next_run['id']).status_code==200


def test_source_integrity_and_parameter_storage_caps(studio,test_database):
    client=studio
    base,_,_,sequence,config=config_source(client,test_database)
    with client.app.state.pool.connection() as conn:
        row=conn.execute('SELECT storage_key FROM sequence_runs WHERE id=%s',(sequence['id'],)).fetchone()
    target=client.app.state.data_root/row['storage_key']/'train.jsonl'
    target.write_text(target.read_text()+'\n')
    assert client.post(base+'/model-configs',json={'sequenceRunId':sequence['id']}).status_code==409
    with pytest.raises(ValueError,match='million'):
        configuration(SmokeSettings(layers=4,hiddenSize=256,maxSteps=500).model_dump(),32000,1024)
    with pytest.raises(ValueError,match='GiB'):
        configuration(SmokeSettings(hiddenSize=256,maxSteps=500).model_dump(),20000,1024)


def test_running_cancel_terminates_process_and_excludes_credentials(studio,test_database,monkeypatch):
    client=studio
    base,_,_,_,config=config_source(client,test_database)
    runtime_stub(monkeypatch)
    response=client.post(base+'/smoke-runs',json={'modelConfigId':config['id']});assert response.status_code==202,response.text
    run=response.json();started=threading.Event();children=[]
    real_popen=subprocess.Popen
    def slow_child(*args,**kwargs):
        child=real_popen([str(__import__('sys').executable),'-c','import time;time.sleep(30)'],**kwargs)
        children.append(child);started.set();return child
    monkeypatch.setattr('app.training.jobs.subprocess.Popen',slow_child)
    def worker():
        with psycopg.connect(test_database,autocommit=True,row_factory=dict_row) as conn:
            execute_smoke(conn,client.app.state.data_root,claim_smoke(conn,uuid4()),threading.Event())
    thread=threading.Thread(target=worker);thread.start()
    assert started.wait(10)
    tick=time.monotonic();assert client.post(base+'/smoke-runs/'+run['id']+'/cancel').status_code==200
    thread.join(8);assert not thread.is_alive() and time.monotonic()-tick<8
    assert children[0].poll() is not None
    assert client.get(base+'/smoke-runs/'+run['id']).json()['status']=='cancelled'
    monkeypatch.setenv('DATABASE_URL','secret');monkeypatch.setenv('HF_TOKEN','secret')
    assert 'DATABASE_URL' not in child_environment() and 'HF_TOKEN' not in child_environment() and 'HOME' not in child_environment()


def test_cuda_failures_and_resource_limits_are_actionable(studio,test_database,monkeypatch):
    from app.datasets.storage import DatasetError
    client=studio
    base,_,_,sequence,config=config_source(client,test_database)
    report=runtime_stub(monkeypatch)
    report['cudaError']='CUDA execution failed'
    auto=client.post(base+'/model-configs',json={'sequenceRunId':sequence['id'],'settings':{'prompt':'Hello','device':'auto'}}).json()
    assert client.post(base+'/smoke-runs',json={'modelConfigId':auto['id']}).status_code==409
    # Explicit CPU is available even when the GPU probe failed.
    queued=client.post(base+'/smoke-runs',json={'modelConfigId':config['id']});assert queued.status_code==202
    client.post(base+'/smoke-runs/'+queued.json()['id']+'/cancel')
    def no_resources(_):raise DatasetError('At least 5 GiB free artifact storage is required.')
    monkeypatch.setattr('app.training.router.check_resources',no_resources)
    response=client.post(base+'/smoke-runs',json={'modelConfigId':config['id']})
    assert response.status_code==409 and '5 GiB' in response.json()['detail']


def test_run_time_budget_stops_a_native_child(studio,test_database,monkeypatch):
    client=studio
    base,_,_,_,config=config_source(client,test_database)
    runtime_stub(monkeypatch)
    run=client.post(base+'/smoke-runs',json={'modelConfigId':config['id']}).json()
    real_popen=subprocess.Popen;children=[]
    def slow_child(*args,**kwargs):
        child=real_popen([str(__import__('sys').executable),'-c','import time;time.sleep(30)'],**kwargs)
        children.append(child);return child
    monkeypatch.setattr('app.training.jobs.subprocess.Popen',slow_child)
    with psycopg.connect(test_database,autocommit=True,row_factory=dict_row) as conn:
        claimed=claim_smoke(conn,uuid4());claimed['configuration']['timeLimitSeconds']=1
        execute_smoke(conn,client.app.state.data_root,claimed,threading.Event())
    result=client.get(base+'/smoke-runs/'+run['id']).json()
    assert result['status']=='failed' and 'time limit' in result['error']
    assert children[0].poll() is not None


def test_worker_runtime_probe_is_cancellable(monkeypatch):
    import sys
    from pathlib import Path
    from app.training.runtime import inspect_runtime
    from app.training.jobs import SmokeCancelled
    real_popen=subprocess.Popen;children=[]
    monkeypatch.setattr('app.training.runtime.training_python',lambda:Path(sys.executable))
    def slow_child(*args,**kwargs):
        child=real_popen([sys.executable,'-c','import time;time.sleep(30)'],**kwargs)
        children.append(child);return child
    monkeypatch.setattr('app.training.runtime.subprocess.Popen',slow_child)
    def cancelled():raise SmokeCancelled()
    tick=time.monotonic()
    with pytest.raises(SmokeCancelled):inspect_runtime(force=True,heartbeat=cancelled)
    assert time.monotonic()-tick<5 and children[0].poll() is not None
    from app.datasets.storage import DatasetError
    def expired():raise DatasetError('Smoke-test time limit exceeded.')
    with pytest.raises(DatasetError,match='time limit'):inspect_runtime(force=True,heartbeat=expired)
    assert children[-1].poll() is not None
