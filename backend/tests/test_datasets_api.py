import hashlib
import json
import threading
import time
from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient
from psycopg.rows import dict_row
import pytest
import pymupdf

from app.main import create_app
from app.datasets.worker import DatasetWorker, claim_job, execute_job, recover_interrupted
from app.datasets.storage import storage_path

METADATA = {'name':'Bangla sample','language':'bn','source':'Public corpus','licenseNote':'Public domain confirmed','permission':'confirmed'}


@pytest.fixture
def dataset_client(test_database, tmp_path, monkeypatch):
    monkeypatch.setenv('STUDIO_DATA_DIR', str(tmp_path))
    with TestClient(create_app(test_database, enable_worker=False)) as client:
        yield client


def new_project(client):
    p=client.post('/api/projects',json={'id':str(uuid4()),'name':'Dataset tests'}).json()
    return f"/api/projects/{p['id']}/datasets"


def import_sample(client, base, metadata=None, count=25):
    text='\n'.join(json.dumps({'text':f'বাংলা document {i}','group_id':f'group-{i}'},ensure_ascii=False) for i in range(count))
    response=client.post(base,data={'metadata':json.dumps(metadata or METADATA)},files=[('files',('sample.jsonl',text.encode(),'application/octet-stream'))])
    assert response.status_code==201, response.text
    return response.json()


def run_one(test_database, root, stop=None):
    with psycopg.connect(test_database,autocommit=True,row_factory=dict_row) as conn:
        job=claim_job(conn,uuid4());assert job
        execute_job(conn,root,job,stop or threading.Event())
        return str(job['id'])


def test_upload_preview_validation_and_project_isolation(dataset_client, monkeypatch):
    client=dataset_client;base=new_project(client)
    d=import_sample(client,base);path=f"{base}/{d['id']}"
    assert d['recordCount']==25 and d['versionCount']==0
    assert len(client.get(path+'/preview').json()['records'])==20
    assert len(client.get(path+'/preview?page=2').json()['records'])==5
    assert client.get(path+'/preview?page_size=21').status_code==422
    assert len(client.get(base).json())==1
    assert client.get(new_project(client)+'/'+d['id']).status_code==404
    for content,filename in [(b'{bad}','bad.jsonl'),(b'\xff','encoding.txt'),(b'{"text":2}','bad.jsonl'),(b'text','bad.csv')]:
        response=client.post(base,data={'metadata':json.dumps(METADATA)},files=[('files',(filename,content))])
        assert response.status_code==422
    assert len(client.get(base).json())==1
    assert not list(client.app.state.data_root.rglob('.import-*'))
    response=client.post(base,data={'metadata':json.dumps(METADATA)},files=[('files',('../../outside.txt',b'raw text'))])
    assert response.status_code==201 and response.json()['files'][0]['name']=='outside.txt'
    assert not (client.app.state.data_root.parent/'outside.txt').exists()
    import app.datasets.router as router_module
    monkeypatch.setattr(router_module,'MAX_BYTES',4)
    response=client.post(base,data={'metadata':json.dumps(METADATA)},files=[('files',('test.txt',b'12345'))])
    assert response.status_code==413


def test_pdf_upload_preview_and_cleaning_end_to_end(dataset_client, test_database):
    client = dataset_client
    base = new_project(client)
    with pymupdf.open() as document:
        document.new_page().insert_text((72, 72), "  PPC Rule first page  ")
        document.new_page()
        document.new_page().insert_text((72, 72), "PPC Rule third page")
        content = document.tobytes()
    response = client.post(base, data={'metadata': json.dumps(METADATA)},
                           files=[('files', ('PPC Rule.pdf', content, 'application/pdf'))])
    assert response.status_code == 201, response.text
    detail = response.json()
    assert detail['recordCount'] == 2
    assert detail['files'][0]['pageCount'] == 3
    assert detail['files'][0]['skippedPages'] == [2]
    path = f"{base}/{detail['id']}"
    records = client.get(path + '/preview').json()['records']
    assert records[1]['provenance'][0]['page'] == 3
    assert 'PPC Rule first page' in records[0]['text']
    assert records[0]['group_id'] == records[1]['group_id']
    job = client.post(path + '/process', json={'train': 100, 'validation': 0, 'test': 0}).json()
    run_one(test_database, client.app.state.data_root)
    assert client.get(path + f"/jobs/{job['id']}").json()['status'] == 'completed'
    version = client.get(path).json()['versions'][0]
    result = client.get(path + f"/versions/{version['id']}/download?artifact=train")
    assert result.status_code == 200
    assert len(result.text.splitlines()) == 2
    assert version['manifest']['counts']['groups'] == 1


def test_markdown_upload_process_and_review_preserve_documents(dataset_client, test_database):
    client = dataset_client
    base = new_project(client)
    source = '# বাংলা\n\n| Item | Value |\n|---|---|\n| A | 123 |\n\n```text\n    indented code\n```'
    response = client.post(base, data={'metadata': json.dumps(METADATA)},
        files=[('files', ('manual.md', source.encode('utf-8'), 'text/markdown')),
               ('files', ('second.markdown', b'# Second\n\nSeparate document.', 'text/markdown'))])
    assert response.status_code == 201, response.text
    detail = response.json()
    assert detail['recordCount'] == 2 and [f['name'] for f in detail['files']] == ['manual.md', 'second.markdown']
    path = base + '/' + detail['id']
    records = client.get(path + '/preview').json()['records']
    assert records[0]['text'] == source
    assert records[0]['provenance'][0]['filename'] == 'manual.md'
    response = client.post(path + '/process', json={'train': 100, 'validation': 0, 'test': 0})
    assert response.status_code == 202, response.text
    run_one(test_database, client.app.state.data_root)
    version = client.get(path).json()['versions'][0]
    rows = [json.loads(line) for line in client.get(path + f"/versions/{version['id']}/download?artifact=processed").text.splitlines()]
    assert len(rows) == 2 and rows[0]['text'] == source
    assert client.get(path + f"/versions/{version['id']}/corrections?page=1").json()['text'] == source


@pytest.mark.parametrize('content,error', [(b'not a pdf', 'invalid or unreadable PDF')])
def test_invalid_pdf_upload_returns_422_and_cleans_staging(dataset_client, content, error):
    client = dataset_client
    base = new_project(client)
    response = client.post(base, data={'metadata': json.dumps(METADATA)},
                           files=[('files', ('PPC Rule.pdf', content, 'application/pdf'))])
    assert response.status_code == 422
    assert error in response.json()['detail']
    assert client.get(base).json() == []
    assert not list(client.app.state.data_root.rglob('.import-*'))


def test_delete_one_duplicate_preserves_other_upload_and_cleans_versions(dataset_client, test_database):
    client = dataset_client
    base = new_project(client)
    first = import_sample(client, base)
    duplicate = import_sample(client, base)
    path = f"{base}/{duplicate['id']}"
    root = client.app.state.data_root
    with psycopg.connect(test_database, row_factory=dict_row) as conn:
        first_key = conn.execute("SELECT storage_key FROM datasets WHERE id=%s", (first['id'],)).fetchone()['storage_key']
        duplicate_key = conn.execute("SELECT storage_key FROM datasets WHERE id=%s", (duplicate['id'],)).fetchone()['storage_key']
    retained = {file: file.read_bytes() for file in storage_path(root, first_key).rglob('*') if file.is_file()}
    job = client.post(path + '/process', json={}).json()
    run_one(test_database, root)
    version = client.get(path).json()['versions'][0]
    # The UUID must belong to the selected project, even for destructive calls.
    assert client.delete(new_project(client) + '/' + duplicate['id']).status_code == 404
    assert storage_path(root, duplicate_key).is_dir()
    response = client.delete(path)
    assert response.status_code == 200, response.text
    assert response.json() == {'id': duplicate['id'], 'deleted': True, 'cleanupWarning': None}
    assert client.get(path).status_code == 404
    assert client.get(path + f"/versions/{version['id']}/download").status_code == 404
    assert client.get(path + f"/jobs/{job['id']}").status_code == 404
    assert client.delete(path).status_code == 404
    assert [dataset['id'] for dataset in client.get(base).json()] == [first['id']]
    assert not storage_path(root, duplicate_key).exists()
    for file, content in retained.items():
        assert file.read_bytes() == content
    with psycopg.connect(test_database) as conn:
        assert conn.execute("SELECT count(*) FROM dataset_jobs WHERE dataset_id=%s", (duplicate['id'],)).fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM dataset_versions WHERE dataset_id=%s", (duplicate['id'],)).fetchone()[0] == 0


@pytest.mark.parametrize('status', ['queued', 'cleaning', 'deduplicating', 'splitting'])
def test_delete_blocks_active_jobs(dataset_client, test_database, status):
    client = dataset_client
    base = new_project(client)
    dataset = import_sample(client, base)
    path = f"{base}/{dataset['id']}"
    job = client.post(path + '/process', json={}).json()
    with psycopg.connect(test_database) as conn:
        conn.execute("UPDATE dataset_jobs SET status=%s WHERE id=%s", (status, job['id']))
    response = client.delete(path)
    assert response.status_code == 409
    assert 'Cancel or finish' in response.json()['detail']
    assert client.get(path).status_code == 200
    assert client.get(path + '/preview').json()['total'] == 25
    # The session database is shared: don't leave a queued fixture for a later
    # test's worker to claim instead of that test's own job.
    with psycopg.connect(test_database) as conn:
        conn.execute("UPDATE dataset_jobs SET status='cancelled', finished_at=now() WHERE id=%s", (job['id'],))


def test_delete_after_cancel_and_missing_files(dataset_client, test_database):
    import shutil
    client = dataset_client
    base = new_project(client)
    dataset = import_sample(client, base)
    path = f"{base}/{dataset['id']}"
    job = client.post(path + '/process', json={}).json()
    assert client.post(path + f"/jobs/{job['id']}/cancel").status_code == 200
    with psycopg.connect(test_database, row_factory=dict_row) as conn:
        key = conn.execute("SELECT storage_key FROM datasets WHERE id=%s", (dataset['id'],)).fetchone()['storage_key']
    shutil.rmtree(storage_path(client.app.state.data_root, key))
    assert client.delete(path).json()['deleted'] is True
    assert client.get(base).json() == []


def test_delete_reports_disk_cleanup_failure(dataset_client, monkeypatch):
    import app.datasets.router as router_module
    client = dataset_client
    base = new_project(client)
    dataset = import_sample(client, base)
    def blocked(*args, **kwargs):
        raise PermissionError('blocked')
    monkeypatch.setattr(router_module.shutil, 'rmtree', blocked)
    response = client.delete(f"{base}/{dataset['id']}")
    assert response.status_code == 200
    assert response.json()['deleted'] is True
    assert 'could not be cleaned up' in response.json()['cleanupWarning']
    assert client.get(base).json() == []


def test_permissions_active_job_cancel_and_metadata(dataset_client):
    client=dataset_client;base=new_project(client)
    d=import_sample(client,base,{**METADATA,'permission':'unknown'});path=f"{base}/{d['id']}"
    assert client.post(path+'/process',json={}).status_code==409
    assert client.patch(path,json=METADATA).status_code==200
    response=client.post(path+'/process',json={});assert response.status_code==202
    job=response.json();assert job['status']=='queued'
    assert client.post(path+'/process',json={}).status_code==409
    assert client.patch(path,json=METADATA).status_code==409
    assert client.post(path+'/process',json={'train':30}).status_code==422
    assert client.post(path+f"/jobs/{job['id']}/cancel").json()['status']=='cancelled'
    assert client.post(path+f"/jobs/{job['id']}/cancel").status_code==409
    assert client.get(new_project(client)+f"/{d['id']}/jobs/{job['id']}").status_code==404


def test_processing_versions_downloads_and_immutable_raw(dataset_client,test_database):
    client=dataset_client;base=new_project(client);d=import_sample(client,base);path=f"{base}/{d['id']}"
    root=client.app.state.data_root
    originals={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
    job=client.post(path+'/process',json={}).json()
    run_one(test_database,root)
    assert client.get(path+f"/jobs/{job['id']}").json()['status']=='completed'
    detail=client.get(path).json();version=detail['versions'][0]
    assert version['version']==1 and version['manifest']['counts']['output']==25
    manifest=client.get(path+f"/versions/{version['id']}/download").json()
    for split in ('train','validation','test'):
        response=client.get(path+f"/versions/{version['id']}/download?artifact={split}")
        assert response.status_code==200
        assert hashlib.sha256(response.content).hexdigest()==manifest['splits'][split]['sha256']
    assert client.get(path+f"/versions/{version['id']}/download?artifact=../raw").status_code==422
    assert client.get(path+f"/preview?version_id={version['id']}&split=train").json()['total']==manifest['splits']['train']['recordCount']
    assert client.get(new_project(client)+f"/{d['id']}/versions/{version['id']}/download").status_code==404
    client.post(path+'/process',json={'deduplicate':False});run_one(test_database,root)
    versions=client.get(path).json()['versions']
    assert [v['version'] for v in versions]==[2,1]
    assert versions[1]==version
    for file,content in originals.items():assert file.read_bytes()==content
    assert not list(root.rglob('.tmp-*'))


def test_running_cancel_failure_retry_and_lease_recovery(dataset_client,test_database,monkeypatch):
    client=dataset_client;base=new_project(client);d=import_sample(client,base);path=f"{base}/{d['id']}";root=client.app.state.data_root
    job=client.post(path+'/process',json={}).json()
    with psycopg.connect(test_database,autocommit=True,row_factory=dict_row) as conn:
        claimed=claim_job(conn,uuid4())
        assert client.post(path+f"/jobs/{job['id']}/cancel").json()['cancelRequested']
        execute_job(conn,root,claimed,threading.Event())
    assert client.get(path+f"/jobs/{job['id']}").json()['status']=='cancelled'
    assert client.get(path).json()['versionCount']==0
    assert not list(root.rglob('.tmp-*'))
    job=client.post(path+'/process',json={}).json()
    with psycopg.connect(test_database,autocommit=True,row_factory=dict_row) as conn:
        claim_job(conn,uuid4());recover_interrupted(conn)
        assert client.get(path+f"/jobs/{job['id']}").json()['status']=='cleaning'
        conn.execute("UPDATE dataset_jobs SET heartbeat_at=now()-interval '61 seconds' WHERE id=%s",(job['id'],))
        recover_interrupted(conn)
    assert client.get(path+f"/jobs/{job['id']}").json()['status']=='failed'
    client.post(path+'/process',json={});run_one(test_database,root)
    assert client.get(path).json()['versionCount']==1
    # A later failed run cannot damage the successful version.
    job=client.post(path+'/process',json={'grouping':'source'}).json();run_one(test_database,root)
    assert client.get(path+f"/jobs/{job['id']}").json()['status']=='failed'
    assert client.get(path).json()['versionCount']==1


def test_lifespan_worker_persists_queue_and_only_one_worker_processes(dataset_client,test_database,monkeypatch):
    import app.datasets.worker as module
    client=dataset_client;base=new_project(client)
    ds=[import_sample(client,base) for _ in range(2)]
    jobs=[client.post(f"{base}/{d['id']}/process",json={}).json() for d in ds]
    original=module.prepare;entered=threading.Event();release=threading.Event();lock=threading.Lock();running=0;maximum=0
    def slow_prepare(*args,**kwargs):
        nonlocal running,maximum
        with lock:running+=1;maximum=max(maximum,running)
        entered.set();release.wait(5)
        try:return original(*args,**kwargs)
        finally:
            with lock:running-=1
    monkeypatch.setattr(module,'prepare',slow_prepare)
    workers=[DatasetWorker(test_database,client.app.state.data_root) for _ in range(2)]
    try:
        for worker in workers:worker.start()
        assert entered.wait(5)
        time.sleep(.15)
        assert maximum==1
        release.set()
        for _ in range(100):
            states=[client.get(f"{base}/{d['id']}/jobs/{j['id']}").json()['status'] for d,j in zip(ds,jobs)]
            if states==['completed','completed']:break
            time.sleep(.05)
        assert states==['completed','completed'] and maximum==1
    finally:
        release.set()
        for worker in workers:worker.stop()


def test_streaming_body_file_count_and_document_limits(dataset_client, monkeypatch):
    client=dataset_client;base=new_project(client)
    fields={'metadata':json.dumps(METADATA)}
    response=client.post(base,data=fields,files=[('files',(f'{index}.txt',b'x')) for index in range(21)])
    assert response.status_code==400 and 'files' in response.json()['detail'].lower()
    response=client.post(base,data=fields,files=[('files',('large.txt',b'x'*(1024*1024+1)))])
    assert response.status_code==422 and '1 MiB' in response.json()['detail']
    import app.datasets.importing as importing
    monkeypatch.setattr(importing,'MAX_DOCUMENTS',2)
    response=client.post(base,data=fields,files=[('files',('many.jsonl',b'{"text":"x"}\n'*3))])
    assert response.status_code==422 and '10,000 document' in response.json()['detail']
    # No Content-Length: enforce the limit while consuming multipart bytes.
    import app.datasets.router as module
    monkeypatch.setattr(module,'MAX_BYTES',16)
    boundary='dataset-stream-boundary'
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n{json.dumps(METADATA)}\r\n--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="sample.txt"\r\nContent-Type: text/plain\r\n\r\n'.encode()+b'x'*300000+f'\r\n--{boundary}--\r\n'.encode())
    response=client.post(base,content=iter([body]),headers={'Content-Type':f'multipart/form-data; boundary={boundary}'})
    assert response.status_code==413, response.text
    assert not list(client.app.state.data_root.rglob('.import-*'))


def test_restart_reads_published_artifacts_and_expired_staging_is_removed(dataset_client,test_database):
    client=dataset_client;base=new_project(client);d=import_sample(client,base);path=f"{base}/{d['id']}";root=client.app.state.data_root
    client.post(path+'/process',json={});run_one(test_database,root)
    original=client.get(path).json()['versions'][0]
    with TestClient(create_app(test_database,enable_worker=False)) as restarted:
        assert restarted.get(path).json()['versions'][0]==original
        assert restarted.get(path+f"/versions/{original['id']}/download?artifact=train").status_code==200
    job=client.post(path+'/process',json={}).json()
    with psycopg.connect(test_database,autocommit=True,row_factory=dict_row) as conn:
        row=claim_job(conn,uuid4())
        staging=storage_path(root,row['storage_key'])/'versions'/f".tmp-{job['id']}"
        staging.mkdir();(staging/'unfinished').write_text('partial')
        conn.execute("UPDATE dataset_jobs SET heartbeat_at=now()-interval '61 seconds' WHERE id=%s",(job['id'],))
        recover_interrupted(conn,root)
        assert not staging.exists()
    assert client.get(path).json()['versions'][0]==original
