import hashlib
import io
import json
from pathlib import Path
import threading
import time
from uuid import uuid4
import zipfile

from fastapi.testclient import TestClient
import psycopg
from psycopg.rows import dict_row
import pytest

from app.datasets.storage import storage_path
from app.main import create_app
from app.models.source import current_permission, take_snapshot
from app.tokenizers.jobs import child_environment, claim_preparation, execute_preparation, recover_preparation
from test_dataset_corrections import prepared, run_job, save_all


@pytest.fixture
def studio(test_database, tmp_path, monkeypatch):
    monkeypatch.setenv('STUDIO_DATA_DIR', str(tmp_path))
    with TestClient(create_app(test_database, enable_worker=False)) as client:
        yield client


def source(client, database, pdf=False, split=False):
    path, detail, parent = prepared(client, database, pdf=pdf, split=split)
    url, revision = save_all(client, path, parent)
    assert client.post(url+'/publish', json={'revision': revision}).status_code == 202
    run_job(client, database)
    version = client.get(path).json()['versions'][0]
    return f"/api/projects/{detail['projectId']}", path, detail, version


def execute(client, database):
    with psycopg.connect(database, autocommit=True, row_factory=dict_row) as conn:
        next_run = claim_preparation(conn, uuid4())
        assert next_run
        kind, run = next_run
        execute_preparation(conn, client.app.state.data_root, kind, run, threading.Event())
        return kind, run


def train(client, database, base, version):
    response = client.post(base+'/tokenizers', json={'datasetVersionId':version['id'],'vocabSize':512})
    assert response.status_code == 202, response.text
    run = response.json()
    execute(client, database)
    result = client.get(base+'/tokenizers/'+run['id']).json()
    assert result['status']=='completed', result['error']
    return result


def test_reviewed_source_train_encode_sequence_bundle_and_deletion(studio, test_database):
    client = studio
    base, dataset_path, detail, version = source(client, test_database, pdf=True)
    originals = {p:p.read_bytes() for p in client.app.state.data_root.rglob('*') if p.is_file()}
    # A newer ordinary processing version must not replace the reviewed input.
    client.post(dataset_path+'/process', json={'train':100,'validation':0,'test':0})
    run_job(client,test_database)
    choices = client.get(base+'/tokenizers/sources').json()
    assert choices[0]['eligible'] is False
    assert next(choice for choice in choices if choice['eligible'])['versionId'] == version['id']
    assert client.post(base+'/tokenizers',json={'datasetVersionId':choices[0]['versionId']}).status_code == 409
    tokenizer = train(client,test_database,base,version)
    assert tokenizer['datasetVersionId']==version['id']
    assert tokenizer['manifest']['trainingDocuments']==1  # whole PDF, not three page-documents
    path = base+'/tokenizers/'+tokenizer['id']
    for text in ['বাংলা English 👋 [EOS] [PAD] e\u0301\u200c\u200d', '', 'line\n  next']:
        preview = client.post(path+'/encode',json={'text':text})
        assert preview.status_code==200, preview.text
        assert preview.json()['decodedText']==text and preview.json()['roundTripMatches']
        assert all(token['id']>=4 for token in preview.json()['tokens'])
    assert client.post(path+'/encode',json={'text':'x'*16385}).status_code==422
    assert client.post(path+'/encode',json={'text':'বাংলা'*2000}).status_code==422
    assert client.post(path+'/encode',content='{"text":"\\ud800"}',headers={'Content-Type':'application/json'}).status_code==422
    for key in ('tokenizer','config','special_tokens','manifest'):
        download=client.get(path+'/download?artifact='+key)
        assert download.status_code==200
        assert hashlib.sha256(download.content).hexdigest()==tokenizer['manifest']['artifacts'][key]['sha256']
    assert client.get(path+'/download?artifact=../input').status_code==422
    assert client.delete(dataset_path).status_code==409
    response=client.post(base+'/sequence-runs',json={'tokenizerRunId':tokenizer['id'],'sequenceLength':128})
    assert response.status_code==202, response.text
    sequence=response.json()
    execute(client,test_database)
    seq_path=base+'/sequence-runs/'+sequence['id']
    sequence=client.get(seq_path).json()
    assert sequence['status']=='completed', sequence['error']
    assert client.delete(path).status_code==409
    preview=client.get(seq_path+'/preview').json()
    assert preview['records'][0]['pages']==[1,2,3]
    assert len(preview['records'][0]['input_ids'])==128
    assert client.get(seq_path+'/preview?split=validation').json()['records']==[]
    assert client.get(seq_path+'/preview?split=bad').status_code==422
    archive=client.get(seq_path+'/download?artifact=bundle')
    assert archive.status_code==200
    with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
        assert bundle.testzip() is None
        assert {'tokenizer.json','tokenizer_config.json','special_tokens_map.json','manifest.json','documents.tokens.jsonl','train.jsonl','validation.jsonl','test.jsonl'}==set(bundle.namelist())
        tokens=json.loads(bundle.read('documents.tokens.jsonl').decode().splitlines()[0])
        rows=[json.loads(line) for line in bundle.read('train.jsonl').decode().splitlines()]
        assert [token for row in rows for token,mask in zip(row['input_ids'],row['attention_mask']) if mask]==tokens['token_ids']
        assert bundle.read('validation.jsonl')==b''
    with TestClient(create_app(test_database,enable_worker=False)) as restarted:
        assert restarted.get(path).json()['manifest']==tokenizer['manifest']
        assert restarted.get(seq_path+'/download?artifact=bundle').content==archive.content
    for file,content in originals.items(): assert file.read_bytes()==content
    assert client.delete(seq_path).status_code==200
    assert client.delete(path).status_code==200
    assert client.delete(dataset_path).status_code==200


def test_project_isolation_validation_and_queued_cancel_retry(studio,test_database):
    client=studio
    base,_,_,version=source(client,test_database)
    for invalid in (True,259,32001,8000.5):
        assert client.post(base+'/tokenizers',json={'datasetVersionId':version['id'],'vocabSize':invalid}).status_code==422
    run=client.post(base+'/tokenizers',json={'datasetVersionId':version['id']}).json()
    path=base+'/tokenizers/'+run['id']
    assert client.post(path+'/encode',json={'text':'x'}).status_code==409
    assert client.delete(path).status_code==409
    assert client.post(base+'/sequence-runs',json={'tokenizerRunId':run['id']}).status_code==409
    other=client.post('/api/projects',json={'id':str(uuid4()),'name':'Other tokenizer project'}).json()
    otherbase='/api/projects/'+other['id']
    assert client.get(otherbase+'/tokenizers/'+run['id']).status_code==404
    assert client.post(otherbase+'/tokenizers/'+run['id']+'/cancel').status_code==404
    assert client.delete(otherbase+'/tokenizers/'+run['id']).status_code==404
    assert client.post(otherbase+'/tokenizers',json={'datasetVersionId':version['id']}).status_code==404
    assert client.post(path+'/cancel').json()['status']=='cancelled'
    retried=client.post(path+'/retry')
    assert retried.status_code==202
    assert retried.json()['id']!=run['id'] and retried.json()['datasetVersionId']==version['id']
    execute(client,test_database)
    ready=client.get(base+'/tokenizers/'+retried.json()['id']).json()
    assert ready['status']=='completed',ready['error']
    for invalid in (True,128.0,129,'128'):
        assert client.post(base+'/sequence-runs',json={'tokenizerRunId':ready['id'],'sequenceLength':invalid}).status_code==422


def test_corrupt_source_and_artifacts_fail_without_mutating_prior_outputs(studio,test_database):
    client=studio
    base,_,_,version=source(client,test_database)
    tokenizer=train(client,test_database,base,version)
    with psycopg.connect(test_database,row_factory=dict_row) as conn:
        stored=conn.execute('SELECT * FROM tokenizer_runs WHERE id=%s',(tokenizer['id'],)).fetchone()
    tokenizer_path=storage_path(client.app.state.data_root,stored['storage_key'])/'tokenizer.json'
    raw=tokenizer_path.read_bytes()
    tokenizer_path.write_bytes(raw+b' ')
    try:
        assert client.post(base+'/tokenizers/'+tokenizer['id']+'/encode',json={'text':'test'}).status_code==409
    finally: tokenizer_path.write_bytes(raw)
    source_file=storage_path(client.app.state.data_root,stored['source_snapshot']['storageKey'])/'train.jsonl'
    original=source_file.read_bytes()
    retry=client.post(base+'/tokenizers/'+tokenizer['id']+'/retry').json()
    source_file.write_bytes(original+b' ')
    try:
        execute(client,test_database)
        failed=client.get(base+'/tokenizers/'+retry['id']).json()
        assert failed['status']=='failed' and 'checksum mismatch' in failed['error']
        assert tokenizer_path.read_bytes()==raw
        assert not list(client.app.state.data_root.rglob('.tmp-*'))
    finally: source_file.write_bytes(original)


def test_running_cancellation_terminates_child_and_recovery_preserves_queue(studio,test_database,monkeypatch):
    import app.tokenizers.jobs as jobs
    client=studio
    base,_,_,version=source(client,test_database)
    run=client.post(base+'/tokenizers',json={'datasetVersionId':version['id']}).json()
    entered=threading.Event(); processes=[]
    original_popen=jobs.subprocess.Popen
    def slow_child(args,**kwargs):
        process=original_popen([args[0],'-c','import time; time.sleep(30)'],**kwargs)
        processes.append(process);entered.set();return process
    monkeypatch.setattr(jobs.subprocess,'Popen',slow_child)
    thread=threading.Thread(target=execute,args=(client,test_database))
    thread.start()
    assert entered.wait(5)
    assert client.post(base+'/tokenizers/'+run['id']+'/cancel').status_code==200
    thread.join(5)
    assert not thread.is_alive() and processes[0].poll() is not None
    assert client.get(base+'/tokenizers/'+run['id']).json()['status']=='cancelled'
    assert not list(client.app.state.data_root.rglob('.tmp-*'))
    monkeypatch.setattr(jobs.subprocess,'Popen',original_popen)
    retry=client.post(base+'/tokenizers/'+run['id']+'/retry').json()
    with psycopg.connect(test_database,autocommit=True,row_factory=dict_row) as conn:
        claimed=claim_preparation(conn,uuid4());assert claimed
        conn.execute("UPDATE tokenizer_runs SET heartbeat_at=now()-interval '61 seconds' WHERE id=%s",(retry['id'],))
        recover_preparation(conn,client.app.state.data_root)
    assert client.get(base+'/tokenizers/'+retry['id']).json()['status']=='failed'
    queued=client.post(base+'/tokenizers/'+retry['id']+'/retry').json()
    with TestClient(create_app(test_database,enable_worker=False)) as restarted:
        assert restarted.get(base+'/tokenizers/'+queued['id']).json()['status']=='queued'
    assert client.post(base+'/tokenizers/'+queued['id']+'/cancel').status_code==200


def test_low_disk_preflight_and_child_has_no_credentials(studio,test_database,monkeypatch):
    import app.tokenizers.storage as storage
    client=studio
    base,_,_,version=source(client,test_database)
    monkeypatch.setattr(storage,'MIN_FREE_BYTES',10**30)
    response=client.post(base+'/tokenizers',json={'datasetVersionId':version['id']})
    assert response.status_code==507
    assert client.get(base+'/tokenizers').json()==[]
    monkeypatch.setenv('DATABASE_URL','private-credential')
    monkeypatch.setenv('HF_TOKEN','private-token')
    environment=child_environment()
    assert 'DATABASE_URL' not in environment and 'HF_TOKEN' not in environment


def test_source_qa_preview_masks_prompt_and_padding(studio, test_database):
    base, _, _, version = source(studio, test_database)
    tokenizer = train(studio, test_database, base, version)
    path = f"{base}/tokenizers/{tokenizer['id']}/sft-preview"
    body = {"question": "নিয়ম কী?", "excerpt": "Clause 1 [EOS]", "answer": "Clause 1 applies.", "contextLength": 256}
    response = studio.post(path, json=body)
    assert response.status_code == 200, response.text
    preview = response.json()
    start = preview["promptTokens"]
    end = start + preview["supervisedTokens"]
    assert preview["templateVersion"] == "source-qa-v1"
    assert preview["inputIds"][0] == 2
    assert preview["inputIds"][end - 1] == 3
    assert all(token >= 4 for token in preview["inputIds"][1:end - 1])
    assert preview["inputIds"][end:] == [0] * (256 - end)
    assert preview["attentionMask"] == [1] * end + [0] * (256 - end)
    assert preview["labels"] == [-100] * start + preview["inputIds"][start:end] + [-100] * (256 - end)
    assert studio.post(path, json={**body, "contextLength": 8}).status_code == 422
    assert studio.post(path, json={**body, "answer": " "}).status_code == 422
    assert studio.post(path.replace(base, f"/api/projects/{uuid4()}"), json=body).status_code == 404


def test_frozen_tokenizer_encodes_separate_reviewed_version(studio, test_database):
    base, path, _, original = source(studio, test_database)
    tokenizer = train(studio, test_database, base, original)
    correction, revision = save_all(studio, path, original, {1: "নতুন সংস্করণ"})
    assert studio.post(correction + "/publish", json={"revision": revision}).status_code == 202
    run_job(studio, test_database)
    revised = studio.get(path).json()["versions"][0]
    assert revised["id"] != original["id"]

    api = base + "/sequence-runs"
    body = {"tokenizerRunId": tokenizer["id"], "sequenceLength": 128}
    assert studio.post(api, json={**body, "datasetVersionId": str(uuid4())}).status_code == 404
    result = studio.post(api, json={**body, "datasetVersionId": revised["id"]})
    assert result.status_code == 202, result.text
    execute(studio, test_database)
    completed = studio.get(f"{api}/{result.json()['id']}").json()
    assert completed["status"] == "completed", completed["error"]
    manifest = completed["manifest"]
    assert manifest["source"]["datasetVersionId"] == revised["id"]
    assert manifest["tokenizerSource"]["datasetVersionId"] == original["id"]
    assert manifest["tokenizerSha256"] == tokenizer["manifest"]["artifacts"]["tokenizer"]["sha256"]

    with psycopg.connect(test_database, row_factory=dict_row) as conn:
        snapshot = take_snapshot(conn, studio.app.state.data_root, base.rsplit("/", 1)[-1], completed["id"])
        assert snapshot["tokenizerFitSource"]["datasetVersionId"] == original["id"]
        current_permission(conn, snapshot)


def test_reserved_test_inputs_match_published_test_split(studio, test_database):
    from app.inference.source import prepare_inputs

    base, _, detail, version = source(studio, test_database, split=True)
    tokenizer = train(studio, test_database, base, version)
    response = studio.post(base + "/sequence-runs", json={"tokenizerRunId": tokenizer["id"], "sequenceLength": 128})
    assert response.status_code == 202, response.text
    execute(studio, test_database)
    root = studio.app.state.data_root
    with psycopg.connect(test_database, row_factory=dict_row) as conn:
        snapshot = take_snapshot(conn, root, detail["projectId"], response.json()["id"])
    config = {"contextLength": 128, "vocabSize": tokenizer["manifest"]["actualVocabSize"], "prompt": "Test"}
    settings = {"kind": "evaluation", "metricScope": "test", "prompts": [{"text": "Test"}], "maxNewTokens": 8}
    result = prepare_inputs(root, {"trainingSource": snapshot, "configuration": config}, settings)
    assert result["heldOutAvailable"]
    assert len(result["records"]) == snapshot["sequence"]["manifest"]["counts"]["test"]["sequences"]
    assert {record["split"] for record in result["records"]} == {"test"}


def test_reviewed_qa_sequences_are_verified_and_require_a_parent(studio, test_database):
    base, path, _, original = source(studio, test_database)
    tokenizer = train(studio, test_database, base, original)
    examples = {i: json.dumps({"question": f"What is rule {i}?", "excerpt": f"Rule {i} applies.", "answer": f"Rule {i}."})
                for i in range(1, 4)}
    correction, revision = save_all(studio, path, original, examples)
    assert studio.post(correction + "/publish", json={"revision": revision}).status_code == 202
    run_job(studio, test_database)
    revised = studio.get(path).json()["versions"][0]
    response = studio.post(base + "/sequence-runs", json={"tokenizerRunId": tokenizer["id"],
        "datasetVersionId": revised["id"], "sequenceLength": 128, "objective": "sft"})
    assert response.status_code == 202, response.text
    run_id = response.json()["id"]
    execute(studio, test_database)
    sequence = studio.get(f"{base}/sequence-runs/{run_id}").json()
    assert sequence["status"] == "completed", sequence["error"]
    assert sequence["manifest"]["templateVersion"] == "source-qa-v1"
    record = studio.get(f"{base}/sequence-runs/{run_id}/preview").json()["records"][0]
    assert record["labels"][0] == -100
    assert [label for label in record["labels"] if label != -100][-1] == 3
    model = studio.post(base + "/model-configs", json={"trainingKind": "pilot", "sequenceRunId": run_id,
        "settings": {"hiddenSize": 64, "epochs": 1}})
    assert model.status_code == 201, model.text
    assert model.json()["configuration"]["objective"] == "sft"
    run = studio.post(base + "/pilot-runs", json={"modelConfigId": model.json()["id"]})
    assert run.status_code == 409
    assert "parent checkpoint" in run.json()["detail"]
