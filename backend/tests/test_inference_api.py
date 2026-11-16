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
from app.inference.jobs import claim_inference,execute_inference,recover_inference
from app.training.jobs import claim_smoke,execute_smoke
from test_dataset_corrections import prepared,run_job,save_all
from test_tokenizers_api import execute,train,source

pytestmark=pytest.mark.skipif(not (Path(__file__).resolve().parents[2]/'.venv-training/studio-runtime.json').exists(),reason='Explicit training runtime is required for real inference tests.')

TRAIN_TEXT={i:('Training page '+str(i)+'. Alpha beta gamma delta epsilon. ')*80 for i in (1,2,3)}


def make_checkpoint(client,database,steps=100):
    path,detail,parent=prepared(client,database,pdf=True)
    url,revision=save_all(client,path,parent,TRAIN_TEXT)
    assert client.post(url+'/publish',json={'revision':revision}).status_code==202
    run_job(client,database)
    version=client.get(path).json()['versions'][0];base=f"/api/projects/{detail['projectId']}"
    tokenizer=train(client,database,base,version)
    sequence=client.post(base+'/sequence-runs',json={'tokenizerRunId':tokenizer['id'],'sequenceLength':128}).json();execute(client,database)
    config=client.post(base+'/model-configs',json={'sequenceRunId':sequence['id'],'settings':{'hiddenSize':64,'maxSteps':steps,'device':'cpu','prompt':'Training'}})
    assert config.status_code==201,config.text
    run=client.post(base+'/smoke-runs',json={'modelConfigId':config.json()['id']});assert run.status_code==202,run.text
    with psycopg.connect(database,autocommit=True,row_factory=dict_row) as conn:
        execute_smoke(conn,client.app.state.data_root,claim_smoke(conn,uuid4()),threading.Event())
    run=client.get(base+'/smoke-runs/'+run.json()['id']).json();assert run['status']=='completed',run['error']
    return {'base':base,'dataset':path,'run':run,'sequence':sequence,'version':version}


@pytest.fixture(scope='module')
def workspace(test_database,tmp_path_factory):
    root=tmp_path_factory.mktemp('inference-data');old=os.environ.get('STUDIO_DATA_DIR');os.environ['STUDIO_DATA_DIR']=str(root)
    try:
        with TestClient(create_app(test_database,enable_worker=False)) as client:
            data=make_checkpoint(client,test_database)
            data['original']={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
            yield client,data
    finally:
        if old is None:os.environ.pop('STUDIO_DATA_DIR',None)
        else:os.environ['STUDIO_DATA_DIR']=old


def run_inference(client,database):
    with psycopg.connect(database,autocommit=True,row_factory=dict_row) as conn:
        job=claim_inference(conn,uuid4());assert job
        execute_inference(conn,client.app.state.data_root,job,threading.Event())


def prompt_set(client,base):
    response=client.post(base+'/prompt-sets',json={'name':'Comparison','language':'mixed','prompts':[{'text':'Training [EOS] বাংলা','notes':'Check repetition'}]})
    assert response.status_code==201,response.text
    return response.json()


def test_generation_prompt_budget_determinism_and_protected_deletion(workspace,test_database):
    client,data=workspace;base=data['base'];cp=data['run']['checkpoints'][-1]
    sources=client.get(base+'/inference-sources').json();assert sources[0]['trainingBlocks']>2
    assert sources[0]['checkpoints'][-1]['id']==cp['id']
    text='Training [EOS] বাংলা'
    preview=client.post(base+'/inference-preview',json={'checkpointId':cp['id'],'prompt':text})
    assert preview.status_code==200,preview.text
    assert preview.json()['roundTripMatches'] and preview.json()['promptTokens']>0
    outputs=[]
    for _ in range(2):
        response=client.post(base+'/generation-runs',json={'checkpointId':cp['id'],'prompt':text,'maxNewTokens':8});assert response.status_code==202,response.text
        url=base+'/generation-runs/'+response.json()['id'];run_inference(client,test_database)
        result=client.get(url).json();assert result['status']=='completed',result['error']
        output=result['manifest']['report']['results'][0];assert output['weightsUnchanged']
        generated=output['generations'][0];assert generated['generatedTokenCount']<=8 and generated['prompt']==text
        outputs.append(generated['newTokenIds'])
    assert outputs[0]==outputs[1]
    assert client.delete(base+'/smoke-runs/'+data['run']['id']).status_code==409
    bundle=client.get(url+'/download?artifact=bundle');assert bundle.status_code==200
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
        assert archive.testzip() is None and {'report.json','outputs.jsonl','events.jsonl','manifest.json'}==set(archive.namelist())
    assert client.get(url+'/download?artifact=../config').status_code==422
    for p,digest in data['original'].items():assert hashlib.sha256(p.read_bytes()).hexdigest()==digest


def test_prompt_versions_full_training_diagnostic_empty_validation_and_notes(workspace,test_database):
    client,data=workspace;base=data['base'];saved=prompt_set(client,base)
    revised=client.post(base+'/prompt-sets',json={'id':saved['promptSetId'],'name':'New comparison','language':'en','prompts':[{'text':'Alpha','notes':''}]}).json()
    old=client.get(base+f"/prompt-sets/{saved['promptSetId']}/versions/1").json();assert old==saved and revised['version']==2
    body={'checkpointIds':[c['id'] for c in data['run']['checkpoints']],'promptSetVersionId':saved['id'],'maxNewTokens':8,'metricScope':'training'}
    response=client.post(base+'/evaluation-runs',json=body);assert response.status_code==202,response.text
    url=base+'/evaluation-runs/'+response.json()['id'];run_inference(client,test_database)
    result=client.get(url).json();assert result['status']=='completed',result['error']
    report=result['manifest']['report'];assert len(report['results'])==2
    expected=client.get(base+'/sequence-runs/'+data['sequence']['id']).json()['manifest']['counts']['train']['sequences']
    for row in report['results']:
        assert row['metrics']['primary']['blocks']==expected and expected>2
        assert row['metrics']['trainedSubset']['blocks']==2
        assert not row['metrics']['heldOutAvailable']
    assert client.delete(base+'/prompt-sets/'+saved['promptSetId']).status_code==409
    note={'checkpointId':data['run']['checkpoints'][0]['id'],'promptIndex':0,'revision':0,'notes':'Readable but needs source review','readability':'readable'}
    assert client.put(url+'/annotations',json=note).json()['revision']==1
    assert client.put(url+'/annotations',json=note).status_code==409
    notes=client.get(url+'/annotations').json();assert notes[0]['notes']==note['notes']
    assert client.get(url+'/annotations/export').json()['annotations']==notes
    assert client.get(url+'/download?artifact=report').json()==report
    response=client.post(base+'/evaluation-runs',json={**body,'metricScope':'validation'});assert response.status_code==202,response.text
    empty_url=base+'/evaluation-runs/'+response.json()['id'];run_inference(client,test_database)
    empty=client.get(empty_url).json();assert empty['status']=='completed',empty['error']
    assert all(r['metrics']['primary']['loss'] is None and r['metrics']['primary']['perplexity'] is None for r in empty['manifest']['report']['results'])


def test_external_frozen_encoding_and_overlap_rejection(workspace,test_database):
    client,data=workspace;base=data['base'];saved=prompt_set(client,base)
    body={'checkpointIds':[data['run']['checkpoints'][-1]['id']],'promptSetVersionId':saved['id'],'maxNewTokens':8,'metricScope':'external'}
    assert client.post(base+'/evaluation-runs',json={**body,'externalDatasetVersionId':data['version']['id']}).status_code==409
    # Independent reviewed content with a different file hash and document lineage.
    ext_base,ext_path,_,version=source(client,test_database,pdf=False)
    # Source fixture creates its own project. Copying references across projects is forbidden.
    assert client.post(base+'/evaluation-runs',json={**body,'externalDatasetVersionId':version['id']}).status_code==404
    # Import a reviewed independent corpus into the model's project.
    from test_dataset_corrections import META
    raw='\n'.join(json.dumps({'text':f'Independent astronomy observation {i}: planets orbit distant stars.','group_id':str(i)}) for i in range(3)).encode()
    imported=client.post(base+'/datasets',data={'metadata':json.dumps({**META,'name':'Independent evaluation'})},files=[('files',('external.jsonl',raw))])
    assert imported.status_code==201,imported.text
    path=base+'/datasets/'+imported.json()['id']
    client.post(path+'/process',json={'train':100,'validation':0,'test':0});run_job(client,test_database)
    parent=client.get(path).json()['versions'][0];edit,rev=save_all(client,path,parent)
    client.post(edit+'/publish',json={'revision':rev});run_job(client,test_database)
    independent=client.get(path).json()['versions'][0]
    response=client.post(base+'/evaluation-runs',json={**body,'externalDatasetVersionId':independent['id']});assert response.status_code==202,response.text
    url=base+'/evaluation-runs/'+response.json()['id'];run_inference(client,test_database)
    result=client.get(url).json();assert result['status']=='completed',result['error']
    metric=result['manifest']['report']['results'][0]['metrics'];assert metric['heldOutAvailable'] and metric['primary']['available'] and metric['primary']['documents']==3
    assert client.delete(path).status_code==409
    assert client.delete(url).status_code==200
    # A different file/dataset can still repeat cleaned training content.
    edit,rev=save_all(client,path,independent,{1:TRAIN_TEXT[1].strip()})
    assert client.post(edit+'/publish',json={'revision':rev}).status_code==202
    run_job(client,test_database)
    overlapping=client.get(path).json()['versions'][0]
    rejected=client.post(base+'/evaluation-runs',json={**body,'externalDatasetVersionId':overlapping['id']})
    assert rejected.status_code==409 and 'duplicates cleaned' in rejected.json()['detail']
    assert client.delete(path).status_code==200


def test_validation_isolation_cancel_retry_and_recovery(workspace,test_database):
    client,data=workspace;base=data['base'];cp=data['run']['checkpoints'][0]['id']
    for invalid in (7,True,129):assert client.post(base+'/generation-runs',json={'checkpointId':cp,'prompt':'','maxNewTokens':invalid}).status_code==422
    assert client.post(base+'/generation-runs',json={'checkpointId':cp,'prompt':'\x00','maxNewTokens':8}).status_code==422
    assert client.post(base+'/generation-runs',json={'checkpointId':cp,'prompt':'x '*2000,'maxNewTokens':8}).status_code==409
    assert client.post(base+'/generation-runs',content=json.dumps({'checkpointId':cp,'prompt':'\ud800'}),headers={'Content-Type':'application/json'}).status_code==422
    assert client.post('/api/projects/'+str(uuid4())+'/generation-runs',json={'checkpointId':cp,'prompt':'Hello'}).status_code==404
    response=client.post(base+'/generation-runs',json={'checkpointId':cp,'prompt':'Alpha','maxNewTokens':8});assert response.status_code==202,response.text
    url=base+'/generation-runs/'+response.json()['id']
    assert client.delete(url).status_code==409
    assert client.post(url+'/cancel').json()['status']=='cancelled'
    retry=client.post(url+'/retry');assert retry.status_code==202,retry.text
    retry_url=base+'/generation-runs/'+retry.json()['id']
    with psycopg.connect(test_database,autocommit=True,row_factory=dict_row) as conn:
        job=claim_inference(conn,uuid4());assert str(job['id'])==retry.json()['id']
        conn.execute("UPDATE inference_runs SET heartbeat_at=now()-interval '61 seconds' WHERE id=%s",(job['id'],));recover_inference(conn,client.app.state.data_root)
    assert client.get(retry_url).json()['status']=='failed'
    assert client.delete(retry_url).status_code==200


def test_running_native_cancel_is_bounded(workspace,test_database,monkeypatch):
    client,data=workspace;base=data['base'];cp=data['run']['checkpoints'][0]['id']
    response=client.post(base+'/generation-runs',json={'checkpointId':cp,'prompt':'Alpha','maxNewTokens':8});assert response.status_code==202,response.text
    url=base+'/generation-runs/'+response.json()['id'];started=threading.Event();children=[];real=subprocess.Popen
    # Runtime validation already passed separately; delay just the inference child.
    from app.training.runtime import select_runtime
    runtime=select_runtime({'device':'cpu'})
    monkeypatch.setattr('app.inference.jobs.select_runtime',lambda *args,**kwargs:runtime)
    def slow(*args,**kwargs):
        child=real([str(__import__('sys').executable),'-c','import time;time.sleep(30)'],**kwargs);children.append(child);started.set();return child
    monkeypatch.setattr('app.inference.jobs.subprocess.Popen',slow)
    thread=threading.Thread(target=run_inference,args=(client,test_database));thread.start();assert started.wait(10)
    tick=time.monotonic();client.post(url+'/cancel');thread.join(8)
    assert not thread.is_alive() and time.monotonic()-tick<8 and children[0].poll() is not None
    assert client.get(url).json()['status']=='cancelled'


def test_runtime_mismatch_and_artifact_corruption_are_rejected(workspace,monkeypatch):
    client,data=workspace;base=data['base'];cp=data['run']['checkpoints'][0]['id']
    from app.training.runtime import select_runtime
    runtime=select_runtime({'device':'cpu'});runtime={**runtime,'versions':{**runtime['versions'],'torch':'different'}}
    with monkeypatch.context() as patch:
        patch.setattr('app.inference.router.select_runtime',lambda *a,**k:runtime)
        assert client.post(base+'/generation-runs',json={'checkpointId':cp,'prompt':'Alpha','maxNewTokens':8}).status_code==409
    with client.app.state.pool.connection() as conn:
        row=conn.execute('SELECT storage_key FROM smoke_checkpoints WHERE id=%s',(cp,)).fetchone()
    weights=client.app.state.data_root/row['storage_key']/'model.safetensors';original=weights.read_bytes()
    try:
        weights.write_bytes(b'corrupt')
        assert client.post(base+'/generation-runs',json={'checkpointId':cp,'prompt':'Alpha','maxNewTokens':8}).status_code==409
    finally:weights.write_bytes(original)
    completed=next(r for r in client.get(base+'/generation-runs').json() if r['status']=='completed')
    with client.app.state.pool.connection() as conn:
        row=conn.execute('SELECT storage_key FROM inference_runs WHERE id=%s',(completed['id'],)).fetchone()
    report=client.app.state.data_root/row['storage_key']/'report.json';original=report.read_bytes()
    try:
        report.write_bytes(b'corrupt')
        assert client.get(base+'/generation-runs/'+completed['id']+'/download?artifact=report').status_code==409
    finally:report.write_bytes(original)


def test_nonempty_original_validation_is_scored_with_frozen_tokenizer(workspace,test_database):
    client,_=workspace
    path,detail,_=prepared(client,test_database,pdf=False,split=True)
    client.post(path+'/process',json={'train':34,'validation':33,'test':33});run_job(client,test_database)
    parent=client.get(path).json()['versions'][0]
    edit,rev=save_all(client,path,parent);client.post(edit+'/publish',json={'revision':rev});run_job(client,test_database)
    version=client.get(path).json()['versions'][0];base='/api/projects/'+detail['projectId']
    tokenizer=train(client,test_database,base,version)
    sequence=client.post(base+'/sequence-runs',json={'tokenizerRunId':tokenizer['id'],'sequenceLength':128}).json();execute(client,test_database)
    config=client.post(base+'/model-configs',json={'sequenceRunId':sequence['id'],'settings':{'hiddenSize':64,'maxSteps':50,'device':'cpu','prompt':'Hello'}}).json()
    run=client.post(base+'/smoke-runs',json={'modelConfigId':config['id']}).json()
    with psycopg.connect(test_database,autocommit=True,row_factory=dict_row) as conn:execute_smoke(conn,client.app.state.data_root,claim_smoke(conn,uuid4()),threading.Event())
    run=client.get(base+'/smoke-runs/'+run['id']).json();assert run['status']=='completed',run['error']
    prompts=prompt_set(client,base)
    response=client.post(base+'/evaluation-runs',json={'checkpointIds':[run['checkpoints'][0]['id']],'promptSetVersionId':prompts['id'],'maxNewTokens':8,'metricScope':'validation'})
    assert response.status_code==202,response.text
    url=base+'/evaluation-runs/'+response.json()['id'];run_inference(client,test_database)
    result=client.get(url).json();assert result['status']=='completed',result['error']
    metric=result['manifest']['report']['results'][0]['metrics']
    assert metric['heldOutAvailable'] and metric['primary']['available'] and metric['primary']['targetTokens']>0
