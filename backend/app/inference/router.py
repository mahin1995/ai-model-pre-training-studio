from datetime import datetime, timezone
import json
import shutil
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response
from psycopg.types.json import Jsonb

from ..datasets.router import project_exists
from ..datasets.storage import DatasetError, storage_path
from ..training.runtime import select_runtime
from ..training.storage import check_resources, checked_file
from .jobs import compatible_runtime
from .schemas import ACTIVE, AnnotationEdit, EvaluationCreate, GenerationCreate, PromptPreview, PromptSetCreate
from .source import checkpoint_snapshot, check_prompts, external_snapshot, frozen_tokenizer, prepare_inputs

router=APIRouter(prefix='/api/projects/{project_id}',tags=['inference'])


def public_prompt_version(row):
    return {'id':str(row['id']),'promptSetId':str(row['prompt_set_id']),'version':row['version'],
            **row['document'],'createdAt':row['created_at'].isoformat()}


def prompt_version(conn,project_id,version_id):
    row=conn.execute('''SELECT v.* FROM prompt_set_versions v JOIN prompt_sets p ON p.id=v.prompt_set_id
        WHERE v.id=%s AND p.project_id=%s''',(version_id,project_id)).fetchone()
    if not row:raise HTTPException(404,'Prompt-set version not found in this project.')
    return row


@router.get('/inference-sources')
def sources(project_id: UUID,request: Request):
    with request.app.state.pool.connection() as conn:
        project_exists(conn,project_id)
        runs=conn.execute('''SELECT r.*,d.metadata FROM smoke_runs r JOIN model_configs m ON m.id=r.model_config_id
            JOIN datasets d ON d.id=m.dataset_id WHERE r.project_id=%s ORDER BY r.created_at DESC''',(project_id,)).fetchall()
        result=[]
        for run in runs:
            cps=conn.execute('SELECT * FROM smoke_checkpoints WHERE run_id=%s ORDER BY step',(run['id'],)).fetchall()
            result.append({'id':str(run['id']),'createdAt':run['created_at'].isoformat(),'status':run['status'],
                'datasetName':run['source_snapshot']['datasetName'],'currentDatasetName':run['metadata']['name'],
                'datasetVersion':run['source_snapshot']['datasetVersion'],
                'configuration':run['configuration'],'runtime':run['runtime_snapshot'],
                'tokenizerSha256':run['source_snapshot']['tokenizer']['manifest']['artifacts']['tokenizer']['sha256'],
                'trainingBlocks':run['source_snapshot']['sequence']['manifest']['counts']['train']['sequences'],
                'validationBlocks':run['source_snapshot']['sequence']['manifest']['counts']['validation']['sequences'],
                'checkpoints':[{'id':str(c['id']),'step':c['step'],'eligible':run['status']=='completed' and run['metadata']['permission']=='confirmed' and c['manifest']['checkpoint']['device']=='cpu',
                    'reason':None if run['status']=='completed' and run['metadata']['permission']=='confirmed' and c['manifest']['checkpoint']['device']=='cpu' else 'Requires a completed CPU-trained run and confirmed source permission.'} for c in cps]})
        return result


@router.post('/inference-preview')
def preview(project_id: UUID,body: PromptPreview,request: Request):
    try:
        with request.app.state.pool.connection() as conn:snapshot=checkpoint_snapshot(conn,request.app.state.data_root,project_id,[body.checkpointId])
        tokenizer,_=frozen_tokenizer(request.app.state.data_root,snapshot)
        ids=tokenizer.encode(body.prompt,add_special_tokens=False).ids
        return {'promptTokens':len(ids),'bosTokens':1,'contextLength':snapshot['configuration']['contextLength'],
                'availableNewTokens':max(0,snapshot['configuration']['contextLength']-len(ids)-1),'roundTripMatches':tokenizer.decode(ids,skip_special_tokens=False)==body.prompt}
    except (DatasetError,OSError) as exc:raise HTTPException(409,str(exc) if isinstance(exc,DatasetError) else 'Saved checkpoint files are unavailable.') from None


@router.get('/prompt-sets')
def list_prompt_sets(project_id: UUID,request: Request):
    with request.app.state.pool.connection() as conn:
        project_exists(conn,project_id)
        return [public_prompt_version(r) for r in conn.execute('''SELECT v.* FROM prompt_set_versions v JOIN prompt_sets p ON p.id=v.prompt_set_id
            WHERE p.project_id=%s ORDER BY v.created_at DESC,v.version DESC''',(project_id,)).fetchall()]


@router.post('/prompt-sets',status_code=201)
def save_prompt_set(project_id: UUID,body: PromptSetCreate,request: Request):
    with request.app.state.pool.connection() as conn:
        project_exists(conn,project_id)
        if body.id:
            parent=conn.execute('SELECT * FROM prompt_sets WHERE id=%s AND project_id=%s FOR UPDATE',(body.id,project_id)).fetchone()
            if not parent:raise HTTPException(404,'Prompt set not found in this project.')
            version=parent['last_version']+1
            conn.execute('UPDATE prompt_sets SET last_version=%s,name=%s,language=%s WHERE id=%s',(version,body.name,body.language,body.id))
            set_id=body.id
        else:
            set_id=uuid4();version=1
            conn.execute('INSERT INTO prompt_sets(id,project_id,name,language) VALUES(%s,%s,%s,%s)',(set_id,project_id,body.name,body.language))
        row=conn.execute('INSERT INTO prompt_set_versions(id,prompt_set_id,version,document) VALUES(%s,%s,%s,%s) RETURNING *',
            (uuid4(),set_id,version,Jsonb(body.model_dump(mode='json',exclude={'id'})))).fetchone()
        return public_prompt_version(row)


@router.get('/prompt-sets/{set_id}/versions/{version}')
def get_prompt_set(project_id: UUID,set_id: UUID,version: int,request: Request):
    with request.app.state.pool.connection() as conn:
        row=conn.execute('''SELECT v.* FROM prompt_set_versions v JOIN prompt_sets p ON p.id=v.prompt_set_id
            WHERE p.project_id=%s AND p.id=%s AND v.version=%s''',(project_id,set_id,version)).fetchone()
        if not row:raise HTTPException(404,'Prompt-set version not found.')
        return public_prompt_version(row)


@router.get('/prompt-sets/{set_id}/versions/{version}/export')
def export_prompt_set(project_id: UUID,set_id: UUID,version: int,request: Request):
    value=get_prompt_set(project_id,set_id,version,request)
    return Response(json.dumps(value,ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="prompt-set-v{version}.json"'})


@router.delete('/prompt-sets/{set_id}')
def delete_prompt_set(project_id: UUID,set_id: UUID,request: Request):
    with request.app.state.pool.connection() as conn:
        row=conn.execute('SELECT id FROM prompt_sets WHERE id=%s AND project_id=%s FOR UPDATE',(set_id,project_id)).fetchone()
        if not row:raise HTTPException(404,'Prompt set not found.')
        if conn.execute('''SELECT 1 FROM inference_runs r JOIN prompt_set_versions v ON v.id=r.prompt_set_version_id
            WHERE v.prompt_set_id=%s''',(set_id,)).fetchone():raise HTTPException(409,'Delete dependent evaluation runs before this prompt set.')
        conn.execute('DELETE FROM prompt_set_versions WHERE prompt_set_id=%s',(set_id,));conn.execute('DELETE FROM prompt_sets WHERE id=%s',(set_id,))
    return {'deleted':True}


def enqueue(conn,root,project_id,snapshot,settings,prompts=None):
    check_resources(root)
    prepare_inputs(root,snapshot,settings)
    runtime=select_runtime({'device':'cpu'});compatible_runtime(snapshot,runtime)
    run_id=uuid4();external=snapshot.get('externalSource')
    row=conn.execute('''INSERT INTO inference_runs(id,project_id,kind,training_run_id,prompt_set_version_id,
        external_dataset_id,external_dataset_version_id,settings,source_snapshot,runtime_snapshot,storage_key)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
        (run_id,project_id,settings['kind'],snapshot['trainingRunId'],prompts['id'] if prompts else None,
         external['datasetId'] if external else None,external['datasetVersionId'] if external else None,
         Jsonb(settings),Jsonb(snapshot),Jsonb(runtime),f'inference/{project_id}/{run_id}')).fetchone()
    for cp in snapshot['checkpoints']:conn.execute('INSERT INTO inference_checkpoint_refs VALUES(%s,%s)',(run_id,cp['id']))
    return run_json(row)


@router.post('/generation-runs',status_code=202)
def create_generation(project_id: UUID,body: GenerationCreate,request: Request):
    try:
        with request.app.state.pool.connection() as conn:
            snapshot=checkpoint_snapshot(conn,request.app.state.data_root,project_id,[body.checkpointId])
            return enqueue(conn,request.app.state.data_root,project_id,snapshot,
                {'kind':'generation','maxNewTokens':body.maxNewTokens,'prompts':[{'text':body.prompt,'notes':''}]})
    except (DatasetError,OSError) as exc:raise HTTPException(409,str(exc) if isinstance(exc,DatasetError) else 'Inference storage is unavailable.') from None


@router.post('/evaluation-runs',status_code=202)
def create_evaluation(project_id: UUID,body: EvaluationCreate,request: Request):
    try:
        with request.app.state.pool.connection() as conn:
            # Lock prompt-set identity before taking a version reference, so delete
            # cannot race the FK insert. Versions themselves are immutable.
            prompts=prompt_version(conn,project_id,body.promptSetVersionId)
            locked=conn.execute('SELECT id FROM prompt_sets WHERE id=%s FOR UPDATE',(prompts['prompt_set_id'],)).fetchone()
            if not locked:raise HTTPException(404,'Prompt set was deleted before submission. Reload prompt sets.')
            snapshot=checkpoint_snapshot(conn,request.app.state.data_root,project_id,body.checkpointIds)
            if body.externalDatasetVersionId:
                snapshot['externalSource']=external_snapshot(conn,request.app.state.data_root,project_id,body.externalDatasetVersionId)
            return enqueue(conn,request.app.state.data_root,project_id,snapshot,
                {'kind':'evaluation','maxNewTokens':body.maxNewTokens,'prompts':prompts['document']['prompts'],
                 'promptSet':public_prompt_version(prompts),'metricScope':body.metricScope},prompts)
    except (DatasetError,OSError) as exc:raise HTTPException(409,str(exc) if isinstance(exc,DatasetError) else 'Evaluation source files are unavailable.') from None


def run_json(row):
    start,end=row['started_at'],row['finished_at']
    snapshot=row['source_snapshot']
    return {'id':str(row['id']),'kind':row['kind'],'status':row['status'],'settings':row['settings'],
        'trainingRunId':str(row['training_run_id']),'checkpoints':[{'id':c['id'],'step':c['step']} for c in snapshot['checkpoints']],
        'metrics':row['metrics'],'manifest':row['manifest'],'error':row['error'],'cancelRequested':row['cancel_requested'],
        'createdAt':row['created_at'].isoformat(),'elapsedSeconds':((end or datetime.now(timezone.utc))-start).total_seconds() if start else 0}


def find_inference(conn,project_id,run_id,kind,lock=False):
    row=conn.execute('SELECT * FROM inference_runs WHERE id=%s AND project_id=%s AND kind=%s'+(' FOR UPDATE' if lock else ''),(run_id,project_id,kind)).fetchone()
    if not row:raise HTTPException(404,'Inference run not found in this project.')
    return row


def register_runs(path,kind):
    @router.get(path)
    def list_runs(project_id: UUID,request: Request):
        with request.app.state.pool.connection() as conn:
            project_exists(conn,project_id)
            return [run_json(r) for r in conn.execute('SELECT * FROM inference_runs WHERE project_id=%s AND kind=%s ORDER BY created_at DESC',(project_id,kind)).fetchall()]

    @router.get(path+'/{run_id}')
    def get_run(project_id: UUID,run_id: UUID,request: Request):
        with request.app.state.pool.connection() as conn:return run_json(find_inference(conn,project_id,run_id,kind))

    @router.post(path+'/{run_id}/cancel')
    def cancel(project_id: UUID,run_id: UUID,request: Request):
        with request.app.state.pool.connection() as conn:
            row=find_inference(conn,project_id,run_id,kind,lock=True)
            if row['status'] not in ACTIVE:raise HTTPException(409,'This run has already finished.')
            if row['status']=='queued':conn.execute("UPDATE inference_runs SET status='cancelled',cancel_requested=true,finished_at=now() WHERE id=%s",(run_id,))
            else:conn.execute('UPDATE inference_runs SET cancel_requested=true WHERE id=%s',(run_id,))
            return run_json(find_inference(conn,project_id,run_id,kind))

    @router.post(path+'/{run_id}/retry',status_code=202)
    def retry(project_id: UUID,run_id: UUID,request: Request):
        try:
            with request.app.state.pool.connection() as conn:
                old=find_inference(conn,project_id,run_id,kind,lock=True)
                if old['status'] in ACTIVE:raise HTTPException(409,'Finish or cancel this run before retrying.')
                snapshot=checkpoint_snapshot(conn,request.app.state.data_root,project_id,[c['id'] for c in old['source_snapshot']['checkpoints']])
                if old['external_dataset_version_id']:snapshot['externalSource']=external_snapshot(conn,request.app.state.data_root,project_id,old['external_dataset_version_id'])
                prompts=prompt_version(conn,project_id,old['prompt_set_version_id']) if old['prompt_set_version_id'] else None
                return enqueue(conn,request.app.state.data_root,project_id,snapshot,old['settings'],prompts)
        except (DatasetError,OSError) as exc:raise HTTPException(409,str(exc) if isinstance(exc,DatasetError) else 'Source storage unavailable.') from None

    @router.get(path+'/{run_id}/download')
    def download(project_id: UUID,run_id: UUID,request: Request,artifact: str='bundle'):
        if artifact not in ('bundle','report','outputs','manifest','events'):raise HTTPException(422,'Unknown inference artifact.')
        with request.app.state.pool.connection() as conn:row=find_inference(conn,project_id,run_id,kind)
        if row['status']!='completed':raise HTTPException(409,'No final results have been published yet.')
        try:target=checked_file(request.app.state.data_root,row['storage_key'],row['manifest']['artifacts'][artifact])
        except (DatasetError,OSError):raise HTTPException(409,'Saved inference artifact is missing or its checksum differs.') from None
        return FileResponse(target,filename=target.name)

    @router.delete(path+'/{run_id}')
    def delete(project_id: UUID,run_id: UUID,request: Request):
        with request.app.state.pool.connection() as conn:
            row=find_inference(conn,project_id,run_id,kind,lock=True)
            if row['status'] in ACTIVE:raise HTTPException(409,'Cancel or finish the run before deleting it.')
            conn.execute('DELETE FROM inference_annotations WHERE run_id=%s',(run_id,))
            conn.execute('DELETE FROM inference_checkpoint_refs WHERE inference_run_id=%s',(run_id,))
            conn.execute('DELETE FROM inference_runs WHERE id=%s',(run_id,))
        warning=None
        try:shutil.rmtree(storage_path(request.app.state.data_root,row['storage_key']))
        except FileNotFoundError:pass
        except OSError:warning='Run deleted; some files could not be removed. Check storage permissions.'
        return {'deleted':True,'cleanupWarning':warning}


@router.get('/evaluation-runs/{run_id}/annotations')
def annotations(project_id: UUID,run_id: UUID,request: Request):
    with request.app.state.pool.connection() as conn:
        find_inference(conn,project_id,run_id,'evaluation')
        rows=conn.execute('SELECT * FROM inference_annotations WHERE run_id=%s ORDER BY checkpoint_id,prompt_index',(run_id,)).fetchall()
        return [{'checkpointId':str(r['checkpoint_id']),'promptIndex':r['prompt_index'],'revision':r['revision'],
                 **r['document'],'updatedAt':r['updated_at'].isoformat()} for r in rows]


@router.put('/evaluation-runs/{run_id}/annotations')
def annotate(project_id: UUID,run_id: UUID,body: AnnotationEdit,request: Request):
    with request.app.state.pool.connection() as conn:
        row=find_inference(conn,project_id,run_id,'evaluation',lock=True)
        if row['status']!='completed':raise HTTPException(409,'Review a completed evaluation run.')
        if str(body.checkpointId) not in {c['id'] for c in row['source_snapshot']['checkpoints']} or body.promptIndex>=len(row['settings']['prompts']):
            raise HTTPException(422,'Annotation target does not belong to this evaluation.')
        old=conn.execute('SELECT * FROM inference_annotations WHERE run_id=%s AND checkpoint_id=%s AND prompt_index=%s',
                         (run_id,body.checkpointId,body.promptIndex)).fetchone()
        if body.revision!=(old['revision'] if old else 0):raise HTTPException(409,'Review notes changed elsewhere. Reload before saving.')
        document=body.model_dump(exclude={'checkpointId','promptIndex','revision'})
        conn.execute('''INSERT INTO inference_annotations(run_id,checkpoint_id,prompt_index,revision,document) VALUES(%s,%s,%s,%s,%s)
            ON CONFLICT(run_id,checkpoint_id,prompt_index) DO UPDATE SET revision=EXCLUDED.revision,document=EXCLUDED.document,updated_at=now()''',
            (run_id,body.checkpointId,body.promptIndex,body.revision+1,Jsonb(document)))
        return {**body.model_dump(mode='json'),'revision':body.revision+1}


@router.get('/evaluation-runs/{run_id}/annotations/export')
def export_annotations(project_id: UUID,run_id: UUID,request: Request):
    return Response(json.dumps({'runId':str(run_id),'annotations':annotations(project_id,run_id,request)},ensure_ascii=False,indent=2),media_type='application/json',
                    headers={'Content-Disposition':'attachment; filename="manual-annotations.json"'})


register_runs('/generation-runs','generation')
register_runs('/evaluation-runs','evaluation')
