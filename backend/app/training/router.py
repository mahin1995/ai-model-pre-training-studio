from datetime import datetime, timezone
import json
import shutil
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from psycopg.types.json import Jsonb

from ..datasets.router import project_exists
from ..datasets.storage import DatasetError, storage_path
from ..models.router import find_config
from ..models.schemas import ResumeCreate, RunCreate
from ..models.source import current_permission, inspect_source
from .jobs import ACTIVE
from .runtime import inspect_runtime, select_runtime
from .storage import check_resources, checked_file, verify_checkpoint

router = APIRouter(prefix='/api/projects/{project_id}', tags=['smoke-training'])


def run_json(row, checkpoints=()):
    start, finish = row['started_at'], row['finished_at']
    return {'id':str(row['id']),'projectId':str(row['project_id']),'modelConfigId':str(row['model_config_id']),
        'parentRunId':str(row['parent_run_id']) if row['parent_run_id'] else None,
        'status':row['status'],'verdict':row['verdict'],'configuration':row['configuration'],'metrics':row['metrics'],
        'manifest':row['manifest'],'runtime':row['runtime_snapshot'],'error':row['error'],'cancelRequested':row['cancel_requested'],
        'createdAt':row['created_at'].isoformat(),'elapsedSeconds':((finish or datetime.now(timezone.utc))-start).total_seconds() if start else 0,
        'checkpoints':[{'id':str(c['id']),'step':c['step'],'sha256':c['manifest']['bundle']['sha256']} for c in checkpoints]}


def find_smoke(conn, project_id, run_id, lock=False):
    row = conn.execute('SELECT * FROM smoke_runs WHERE id=%s AND project_id=%s'+(' FOR UPDATE' if lock else ''),(run_id,project_id)).fetchone()
    if not row:
        raise HTTPException(404,'Smoke run not found in this project.')
    return row


def serialize_run(conn, row):
    return run_json(row, conn.execute('SELECT * FROM smoke_checkpoints WHERE run_id=%s ORDER BY step',(row['id'],)).fetchall())


def enqueue(conn, root, project_id, config, parent=None, checkpoint=None):
    try:
        check_resources(root)
        current_permission(conn, config['source_snapshot'])
        inspect_source(root, config['source_snapshot'], config['configuration'])
        runtime = select_runtime(config['configuration'])
        if checkpoint:
            verify_checkpoint(root, checkpoint)
            info = checkpoint['manifest']['checkpoint']
            if info['versions'] != runtime['versions'] or info['device'] != runtime['device'] or info['deviceName'] != runtime['deviceName']:
                raise DatasetError('Resume requires the original runtime versions and device. Start a fresh run instead.')
    except (DatasetError, OSError) as exc:
        raise HTTPException(409,str(exc) if isinstance(exc,DatasetError) else 'Training storage is unavailable.') from None
    run_id = uuid4()
    row = conn.execute('''INSERT INTO smoke_runs(id,project_id,model_config_id,parent_run_id,resume_checkpoint_id,
        storage_key,configuration,source_snapshot,runtime_snapshot) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
        (run_id,project_id,config['id'],parent['id'] if parent else None,checkpoint['id'] if checkpoint else None,
         f'training/{project_id}/{run_id}/results',Jsonb(config['configuration']),Jsonb(config['source_snapshot']),Jsonb(runtime))).fetchone()
    return run_json(row)


@router.get('/training-runtime')
def runtime_report(project_id: UUID, request: Request, refresh: bool=False):
    with request.app.state.pool.connection() as conn:
        project_exists(conn,project_id)
    return inspect_runtime(force=refresh)


@router.get('/smoke-runs')
def list_runs(project_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        project_exists(conn,project_id)
        return [serialize_run(conn,r) for r in conn.execute('SELECT * FROM smoke_runs WHERE project_id=%s ORDER BY created_at DESC',(project_id,)).fetchall()]


@router.post('/smoke-runs',status_code=202)
def create_run(project_id: UUID, body: RunCreate, request: Request):
    with request.app.state.pool.connection() as conn:
        config = find_config(conn,project_id,body.modelConfigId,lock=True)
        return enqueue(conn,request.app.state.data_root,project_id,config)


@router.get('/smoke-runs/{run_id}')
def get_run(project_id: UUID, run_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        return serialize_run(conn,find_smoke(conn,project_id,run_id))


@router.post('/smoke-runs/{run_id}/cancel')
def cancel_run(project_id: UUID, run_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        run = find_smoke(conn,project_id,run_id,lock=True)
        if run['status'] not in ACTIVE:
            raise HTTPException(409,'This run has already finished.')
        if run['status']=='queued':
            conn.execute("UPDATE smoke_runs SET status='cancelled',cancel_requested=true,finished_at=now() WHERE id=%s",(run_id,))
        else:
            conn.execute('UPDATE smoke_runs SET cancel_requested=true WHERE id=%s',(run_id,))
        return serialize_run(conn,find_smoke(conn,project_id,run_id))


@router.post('/smoke-runs/{run_id}/retry',status_code=202)
def retry_run(project_id: UUID, run_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        previous = find_smoke(conn,project_id,run_id,lock=True)
        if previous['status'] in ACTIVE:
            raise HTTPException(409,'Finish or cancel this run before retrying.')
        config = find_config(conn,project_id,previous['model_config_id'],lock=True)
        return enqueue(conn,request.app.state.data_root,project_id,config)


@router.post('/smoke-runs/{run_id}/resume',status_code=202)
def resume_run(project_id: UUID, run_id: UUID, body: ResumeCreate, request: Request):
    with request.app.state.pool.connection() as conn:
        parent = find_smoke(conn,project_id,run_id,lock=True)
        if parent['status']!='completed':
            raise HTTPException(409,'Resume verification requires a completed source run.')
        checkpoint = conn.execute('SELECT * FROM smoke_checkpoints WHERE id=%s AND run_id=%s',(body.checkpointId,run_id)).fetchone()
        if not checkpoint or checkpoint['step']>=parent['configuration']['maxSteps']:
            raise HTTPException(409,'Select an intermediate checkpoint from this run.')
        return enqueue(conn,request.app.state.data_root,project_id,find_config(conn,project_id,parent['model_config_id'],lock=True),parent,checkpoint)


@router.get('/smoke-runs/{run_id}/metrics')
def metrics(project_id: UUID, run_id: UUID, request: Request, afterStep: int=Query(-1,ge=-1,le=500)):
    with request.app.state.pool.connection() as conn:
        run = find_smoke(conn,project_id,run_id)
    final = storage_path(request.app.state.data_root,run['storage_key'])
    if run['status']=='completed':
        try:
            path = checked_file(request.app.state.data_root,run['storage_key'],run['manifest']['artifacts']['metrics'])
        except (DatasetError,OSError):
            raise HTTPException(409,'Saved metrics are missing or their checksum differs.') from None
    else:
        path = final.parent/'.tmp-results/metrics.jsonl'
        if not path.is_file():
            path = final.parent/'metrics.jsonl'
    events=[]
    if path.is_file():
        if path.stat().st_size>4*1024**2:
            raise HTTPException(409,'Metrics log exceeds the supported size.')
        for line in path.read_bytes().splitlines(keepends=True):
            if not line.endswith(b'\n'):
                continue
            event=json.loads(line)
            if event.get('step',-1)>afterStep and 'loss' in event:
                events.append(event)
    return {'events':events,'latest':run['metrics']}


@router.get('/smoke-runs/{run_id}/download')
def download(project_id: UUID, run_id: UUID, request: Request, artifact: str='bundle'):
    allowed={'bundle','report','sample','metrics','config','tokenizer','tokenizer_config','special_tokens','manifest'}
    if artifact not in allowed:
        raise HTTPException(422,'Unknown training artifact.')
    with request.app.state.pool.connection() as conn:
        run=find_smoke(conn,project_id,run_id)
    if run['status']!='completed':
        raise HTTPException(409,'This run has no final published results. Registered checkpoints remain available separately.')
    try:
        path=checked_file(request.app.state.data_root,run['storage_key'],run['manifest']['artifacts'][artifact])
    except (DatasetError,OSError):
        raise HTTPException(409,'Saved artifact is missing or its checksum differs.') from None
    return FileResponse(path,filename=path.name)


@router.get('/smoke-runs/{run_id}/checkpoints/{checkpoint_id}/download')
def download_checkpoint(project_id: UUID, run_id: UUID, checkpoint_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        find_smoke(conn,project_id,run_id)
        row=conn.execute('SELECT * FROM smoke_checkpoints WHERE id=%s AND run_id=%s',(checkpoint_id,run_id)).fetchone()
    if not row:
        raise HTTPException(404,'Checkpoint not found in this run.')
    try:
        path=verify_checkpoint(request.app.state.data_root,row)/'checkpoint.zip'
    except (DatasetError,OSError):
        raise HTTPException(409,'Checkpoint is missing or its checksum differs.') from None
    return FileResponse(path,filename=f'checkpoint-step-{row["step"]}.zip',media_type='application/zip')


@router.delete('/smoke-runs/{run_id}')
def delete_run(project_id: UUID, run_id: UUID, request: Request):
    with request.app.state.pool.connection() as conn:
        run=find_smoke(conn,project_id,run_id,lock=True)
        if run['status'] in ACTIVE:
            raise HTTPException(409,'Cancel or finish this run before deletion.')
        if conn.execute('SELECT 1 FROM smoke_runs WHERE parent_run_id=%s',(run_id,)).fetchone():
            raise HTTPException(409,'Delete dependent resumed runs before deleting this run and its checkpoints.')
        if conn.execute('SELECT 1 FROM inference_runs WHERE training_run_id=%s',(run_id,)).fetchone():
            raise HTTPException(409,'Delete dependent generation/evaluation runs before deleting this training run and its checkpoints.')
        conn.execute('DELETE FROM smoke_checkpoints WHERE run_id=%s',(run_id,))
        conn.execute('DELETE FROM smoke_runs WHERE id=%s',(run_id,))
    warning=None
    try:
        shutil.rmtree(storage_path(request.app.state.data_root,run['storage_key']).parent)
    except FileNotFoundError:
        pass
    except OSError:
        warning='Run deleted; some artifact files could not be removed. Check storage permissions.'
    return {'deleted':True,'cleanupWarning':warning}
