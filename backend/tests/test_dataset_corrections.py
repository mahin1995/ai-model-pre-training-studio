import hashlib
import json
import threading
from uuid import uuid4

import psycopg
import pymupdf
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.datasets.corrections import safe_cleanup, suggestions
from app.datasets.storage import storage_path
from app.datasets.worker import claim_job, execute_job
from app.main import create_app

META = {'name': 'Correction sample', 'language': 'mixed', 'source': 'Test source',
        'licenseNote': 'Test fixture', 'permission': 'confirmed'}


def run_job(client, database):
    with psycopg.connect(database, autocommit=True, row_factory=dict_row) as conn:
        job = claim_job(conn, uuid4())
        assert job
        execute_job(conn, client.app.state.data_root, job, threading.Event())
        return job


@pytest.fixture
def review_client(test_database, tmp_path, monkeypatch):
    monkeypatch.setenv('STUDIO_DATA_DIR', str(tmp_path))
    with TestClient(create_app(test_database, enable_worker=False)) as client:
        yield client


def prepared(client, database, pdf=False, split=False):
    project = client.post('/api/projects', json={'id': str(uuid4()), 'name': 'Review tests'}).json()
    base = f"/api/projects/{project['id']}/datasets"
    if pdf:
        with pymupdf.open() as document:
            for text in ['First page', 'Second page', 'Third page']:
                document.new_page().insert_text((72, 72), text)
            content = document.tobytes()
        name = 'source.pdf'
    else:
        content = '\n'.join(json.dumps({'text': text, 'group_id': str(index) if split else 'one-document'}, ensure_ascii=False)
                            for index, text in enumerate(['এই rule-এর উদ্দেশ্য হললো:', 'Clause: 2.4.1.2.1\nMeaning: Test', 'শেষ পৃষ্ঠা।'])).encode()
        name = 'sample.jsonl'
    imported = client.post(base, data={'metadata': json.dumps(META)}, files=[('files', (name, content))])
    assert imported.status_code == 201, imported.text
    dataset = imported.json()
    path = f"{base}/{dataset['id']}"
    response = client.post(path + '/process', json={} if split else {'train': 100, 'validation': 0, 'test': 0})
    assert response.status_code == 202
    run_job(client, database)
    detail = client.get(path).json()
    version = detail['versions'][0]
    return path, detail, version


def save_all(client, path, version, replacements=None):
    url = f"{path}/versions/{version['id']}/corrections"
    revision = 0
    for number in range(1, 4):
        data = client.get(url + f'?page={number}').json()
        text = (replacements or {}).get(number, data['text'])
        response = client.put(url, json={'recordId': data['record']['id'], 'text': text, 'reviewed': True, 'revision': data['revision']})
        assert response.status_code == 200, response.text
        revision = response.json()['revision']
    return url, revision


def test_reviewed_version_publication_preserves_parent_and_exports(review_client, test_database):
    client = review_client
    path, detail, parent = prepared(client, test_database)
    original_files = {p: p.read_bytes() for p in client.app.state.data_root.rglob('*') if p.is_file()}
    url = f"{path}/versions/{parent['id']}/corrections"
    first = client.get(url).json()
    assert first['summary'] == {'total': 3, 'reviewed': 0, 'changed': 0}
    assert first['suggestions'][0]['after'] == 'হলো'
    assert client.post(url + '/publish', json={'revision': 0}).status_code == 409
    url, revision = save_all(client, path, parent, {1: 'এই rule-এর উদ্দেশ্য হলো:', 2: 'Requirement: Simulator training\nClause: 2.4.1.2.1\nMeaning: Test'})
    response = client.post(url + '/publish', json={'revision': revision})
    assert response.status_code == 202, response.text
    job = response.json()
    assert job['correctionParentVersionId'] == parent['id']
    # Freeze edits while this snapshot is queued/running.
    assert client.put(url, json={'recordId': first['record']['id'], 'text': 'replacement', 'reviewed': False, 'revision': revision}).status_code == 409
    run_job(client, test_database)
    assert client.get(path + f"/jobs/{job['id']}").json()['status'] == 'completed'
    updated = client.get(path).json()
    assert [v['version'] for v in updated['versions']] == [2, 1]
    assert updated['versions'][1] == parent
    child = updated['versions'][0]
    assert child['manifest']['parentVersionId'] == parent['id']
    assert child['manifest']['correction']['changedRecords'] == 2
    assert child['manifest']['counts']['output'] == 3
    assert child['manifest']['splits']['train']['recordCount'] == 3
    assert child['manifest']['splits']['validation']['recordCount'] == 0
    for file, content in original_files.items():
        assert file.read_bytes() == content
    download = f"{path}/versions/{child['id']}/download?artifact="
    for key in ('continuous', 'documents', 'corrections'):
        response = client.get(download + key)
        assert response.status_code == 200
        assert hashlib.sha256(response.content).hexdigest() == child['manifest']['artifacts'][key]['sha256']
    assert 'উদ্দেশ্য হলো:' in client.get(download + 'continuous').text
    report = client.get(download + 'corrections').json()
    assert len(report['changes']) == 2 and report['reviewedRecords'] == 3
    assert report['changes'][0]['before'] == first['text']
    # Successful snapshots cannot accidentally be published twice.
    assert client.post(url + '/publish', json={'revision': revision}).status_code == 409
    with TestClient(create_app(test_database, enable_worker=False)) as restarted:
        saved = restarted.get(url).json()
        assert saved['text'] == 'এই rule-এর উদ্দেশ্য হলো:'
        assert saved['summary']['reviewed'] == 3
    assert client.delete(path).status_code == 200  # FK cleanup also removes drafts.


def test_draft_conflicts_validation_and_project_isolation(review_client, test_database):
    client = review_client
    path, detail, parent = prepared(client, test_database)
    url = f"{path}/versions/{parent['id']}/corrections"
    first = client.get(url).json()
    edit = {'recordId': first['record']['id'], 'text': 'বাংলা\u200c\u200d', 'reviewed': False, 'revision': 0}
    saved = client.put(url, json=edit)
    assert saved.status_code == 200
    assert client.put(url, json=edit).status_code == 409
    assert client.get(url).json()['text'] == edit['text']
    assert client.post(url + '/publish', json={'revision': 1}).status_code == 409
    for patch in ({'text': '  '}, {'text': '\ud800'}, {'text': 'x' * (1024 * 1024 + 1)}, {'revision': True}, {'reviewed': 'true'}):
        # Use an ASCII-escaped JSON body so the invalid surrogate reaches validation.
        response = client.put(url, content=json.dumps({**edit, 'revision': 1, **patch}), headers={'Content-Type': 'application/json'})
        assert response.status_code == 422
    assert client.put(url, json={**edit, 'revision': 1, 'recordId': 'another-version:record'}).status_code == 404
    assert client.get(url + '?page=4').status_code == 404
    other = client.post('/api/projects', json={'id': str(uuid4()), 'name': 'Other'}).json()
    other_url = url.replace(detail['projectId'], other['id'])
    assert client.get(other_url).status_code == 404
    assert client.put(other_url, json=edit).status_code == 404
    assert client.post(other_url + '/publish', json={'revision': 1}).status_code == 404


def test_source_images_and_pdf_continuity(review_client, test_database):
    client = review_client
    path, detail, parent = prepared(client, test_database, pdf=True)
    url = f"{path}/versions/{parent['id']}/corrections"
    data = client.get(url + '?page=2').json()
    assert data['record']['provenance'][0]['page'] == 2
    image = client.get(data['sourceImageUrl'])
    assert image.status_code == 200 and image.content.startswith(b'\x89PNG\r\n')
    assert client.get(data['sourceImageUrl'].replace('/pages/2/', '/pages/100/')).status_code == 404
    assert client.get(data['sourceImageUrl'].replace(detail['files'][0]['id'], str(uuid4()))).status_code == 404
    url, revision = save_all(client, path, parent)
    assert client.post(url + '/publish', json={'revision': revision}).status_code == 202
    run_job(client, test_database)
    version = client.get(path).json()['versions'][0]
    download = f"{path}/versions/{version['id']}/download?artifact="
    docs = [json.loads(line) for line in client.get(download + 'documents').text.splitlines()]
    assert len(docs) == 1
    assert docs[0]['pages'] == [1, 2, 3]
    assert docs[0]['text'].index('First page') < docs[0]['text'].index('Second page') < docs[0]['text'].index('Third page')
    assert docs[0]['split'] == 'train'
    assert client.get(download + 'continuous').text == docs[0]['text']


def test_cancelled_correction_can_retry_without_touching_parent(review_client, test_database):
    client = review_client
    path, _, parent = prepared(client, test_database)
    url, revision = save_all(client, path, parent)
    job = client.post(url + '/publish', json={'revision': revision}).json()
    assert client.post(path + f"/jobs/{job['id']}/cancel").json()['status'] == 'cancelled'
    assert client.get(path).json()['versions'] == [parent]
    assert client.post(url + '/publish', json={'revision': revision}).status_code == 202
    run_job(client, test_database)
    assert client.get(path).json()['versionCount'] == 2


def test_cross_split_duplicate_correction_fails_without_publishing(review_client, test_database):
    client = review_client
    path, _, parent = prepared(client, test_database, split=True)
    url, revision = save_all(client, path, parent, {1: 'same', 2: 'same', 3: 'same'})
    job = client.post(url + '/publish', json={'revision': revision}).json()
    run_job(client, test_database)
    result = client.get(path + f"/jobs/{job['id']}").json()
    assert result['status'] == 'failed'
    assert 'identical text across splits' in result['error']
    assert client.get(path).json()['versions'] == [parent]
    assert not list(client.app.state.data_root.rglob('.tmp-*'))


def test_worker_uses_frozen_snapshot_and_rejects_corrupt_parent(review_client, test_database):
    client = review_client
    path, detail, parent = prepared(client, test_database)
    url, revision = save_all(client, path, parent, {1: 'এই rule-এর উদ্দেশ্য হলো:'})
    job = client.post(url + '/publish', json={'revision': revision}).json()
    # Even an out-of-band database change to a draft cannot rewrite queued input.
    with psycopg.connect(test_database) as conn:
        conn.execute("UPDATE dataset_correction_drafts SET edits='{}' WHERE dataset_id=%s", (detail['id'],))
    run_job(client, test_database)
    assert client.get(path + f"/jobs/{job['id']}").json()['status'] == 'completed'
    child = client.get(path).json()['versions'][0]
    assert 'উদ্দেশ্য হলো:' in client.get(f"{path}/versions/{child['id']}/download?artifact=continuous").text
    with psycopg.connect(test_database, row_factory=dict_row) as conn:
        row = conn.execute("SELECT storage_key FROM dataset_versions WHERE id=%s", (child['id'],)).fetchone()
    child_path = storage_path(client.app.state.data_root, row['storage_key']) / 'processed.jsonl'
    original = child_path.read_bytes()
    url, revision = save_all(client, path, child)
    response = client.post(url + '/publish', json={'revision': revision})
    assert response.status_code == 202, response.text
    job = response.json()
    child_path.write_bytes(original + b'\n')
    try:
        run_job(client, test_database)
        result = client.get(path + f"/jobs/{job['id']}").json()
        assert result['status'] == 'failed' and 'checksum mismatch' in result['error']
        assert client.get(path).json()['versionCount'] == 2
    finally:
        child_path.write_bytes(original)


def test_safe_text_helpers_preserve_bangla_and_only_suggest_whole_words():
    text = '  বাংলা\u200c\u200d\u200b\r\n e\u0301  '
    assert safe_cleanup(text) == 'বাংলা\u200c\u200d\né'
    assert suggestions('হললো: ককোননো? ভাললো।')[0]['after'] == 'হলো'
    assert suggestions('ভাললোটা কররোটা') == []
