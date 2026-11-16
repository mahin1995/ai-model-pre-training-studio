import json
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from psycopg.types.json import Jsonb

from ..datasets.router import project_exists
from ..datasets.storage import DatasetError
from .schemas import ConfigCreate, configuration
from .source import inspect_source, take_snapshot

router = APIRouter(prefix='/api/projects/{project_id}/model-configs', tags=['model-configuration'])


def config_json(row):
    source = row['source_snapshot']
    return {'id':str(row['id']), 'projectId':str(row['project_id']), 'revision':row['revision'], 'name':row['name'],
        'configuration':row['configuration'], 'source':{k:v for k,v in source.items() if k not in ('dataset','sequence','tokenizer')},
        'createdAt':row['created_at'].isoformat()}


def find_config(conn, project_id, config_id, lock=False):
    row = conn.execute('SELECT * FROM model_configs WHERE id=%s AND project_id=%s'+(' FOR UPDATE' if lock else ''), (config_id,project_id)).fetchone()
    if not row:
        raise HTTPException(404, 'Model configuration not found in this project.')
    return row


@router.get('')
def list_configs(project_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        project_exists(conn, project_id)
        return [config_json(r) for r in conn.execute('SELECT * FROM model_configs WHERE project_id=%s ORDER BY revision DESC',(project_id,)).fetchall()]


@router.post('', status_code=201)
def create_config(project_id: UUID, body: ConfigCreate, request: Request):
    with request.app.state.pool.connection() as conn:
        project_exists(conn, project_id)
        snapshot = take_snapshot(conn, request.app.state.data_root, project_id, body.sequenceRunId)
        try:
            source = inspect_source(request.app.state.data_root, snapshot)
            config = configuration(body.settings.model_dump(), source['vocabSize'], source['contextLength'])
            inspect_source(request.app.state.data_root, snapshot, config)
        except (ValueError, OSError) as exc:
            raise HTTPException(409, str(exc) if isinstance(exc,ValueError) else 'Saved source files are unavailable.') from None
        conn.execute('SELECT id FROM projects WHERE id=%s FOR UPDATE', (project_id,))
        revision = conn.execute('''INSERT INTO model_config_revisions(project_id,last_revision) VALUES(%s,1)
            ON CONFLICT(project_id) DO UPDATE SET last_revision=model_config_revisions.last_revision+1 RETURNING last_revision''',
            (project_id,)).fetchone()['last_revision']
        row = conn.execute('''INSERT INTO model_configs(id,project_id,revision,name,dataset_id,dataset_version_id,
            tokenizer_run_id,sequence_run_id,configuration,source_snapshot) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
            (uuid4(),project_id,revision,body.name,snapshot['datasetId'],snapshot['datasetVersionId'],snapshot['tokenizerRunId'],
             body.sequenceRunId,Jsonb(config),Jsonb(snapshot))).fetchone()
        return config_json(row)


@router.get('/{config_id}')
def get_config(project_id: UUID, config_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        return config_json(find_config(conn,project_id,config_id))


@router.get('/{config_id}/export')
def export_config(project_id: UUID, config_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        value = config_json(find_config(conn,project_id,config_id))
    return Response(json.dumps(value,ensure_ascii=False,indent=2), media_type='application/json',
                    headers={'Content-Disposition':f'attachment; filename="model-config-{value["revision"]}.json"'})


@router.delete('/{config_id}')
def delete_config(project_id: UUID, config_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        find_config(conn,project_id,config_id,lock=True)
        if conn.execute('SELECT 1 FROM smoke_runs WHERE model_config_id=%s',(config_id,)).fetchone():
            raise HTTPException(409, 'Delete dependent smoke runs before deleting this configuration.')
        conn.execute('DELETE FROM model_configs WHERE id=%s',(config_id,))
    return {'deleted':True}
