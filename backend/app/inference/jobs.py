import json
import os
import shutil
import subprocess
import time
from uuid import uuid4

from psycopg.types.json import Jsonb

from ..datasets.storage import DatasetError, storage_path, write_jsonl
from ..models.source import current_permission
from ..tokenizers.jobs import stop_child
from ..training.data import describe, write_json
from ..training.runtime import BACKEND, child_environment, select_runtime, training_python
from ..training.storage import check_resources, make_zip, verify_checkpoint
from .schemas import ACTIVE, MAX_OUTPUT_BYTES, RUNNING
from .source import prepare_inputs


class InferenceCancelled(Exception):pass


def claim_inference(conn,worker_id):
    with conn.transaction():
        row=conn.execute("SELECT * FROM inference_runs WHERE status='queued' ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
        if row:conn.execute("UPDATE inference_runs SET status='validating',started_at=now(),heartbeat_at=now(),worker_id=%s WHERE id=%s",(worker_id,row['id']))
        return row


def recover_inference(conn,root):
    rows=conn.execute("""UPDATE inference_runs SET status='failed',finished_at=now(),error='Inference was interrupted. Retry to create a new run.'
        WHERE status=ANY(%s) AND (heartbeat_at IS NULL OR heartbeat_at<now()-interval '60 seconds') RETURNING storage_key""",(list(RUNNING),)).fetchall()
    for row in rows:
        final=storage_path(root,row['storage_key']);shutil.rmtree(final.parent/('.tmp-'+final.name),ignore_errors=True)


def compatible_runtime(snapshot,runtime):
    for cp in snapshot['checkpoints']:
        saved=cp['manifest']['checkpoint']
        if saved['device']!='cpu' or saved['versions']!=runtime['versions']:
            raise DatasetError('Inference requires a CPU-trained checkpoint and its pinned runtime versions. Recheck the training environment.')


def execute_inference(conn,root,run,stopping):
    final=storage_path(root,run['storage_key']);stage=final.parent/('.tmp-'+final.name)
    process=None;offset=0;metrics={};deadline=time.monotonic()+900
    def heartbeat(status=None):
        if stopping.is_set():raise DatasetError('Inference stopped during shutdown. Retry this run.')
        row=conn.execute('SELECT cancel_requested FROM inference_runs WHERE id=%s',(run['id'],)).fetchone()
        if not row or row['cancel_requested']:raise InferenceCancelled()
        if time.monotonic()>deadline:raise DatasetError('Inference exceeded the 15-minute time limit.')
        conn.execute('UPDATE inference_runs SET heartbeat_at=now(),metrics=%s'+(',status=%s' if status else '')+' WHERE id=%s',
                     (Jsonb(metrics),status,run['id']) if status else (Jsonb(metrics),run['id']))
    def events():
        nonlocal offset
        path=stage/'events.jsonl'
        if not path.exists():return None
        if path.stat().st_size>2*1024**2:raise DatasetError('Inference event log exceeded its limit.')
        with path.open('rb') as stream:stream.seek(offset);pending=stream.read()
        end=pending.rfind(b'\n')+1;offset+=end;status=None
        for line in pending[:end].splitlines():
            event=json.loads(line);metrics.update(event)
            if event.get('stage') in RUNNING:status=event['stage']
        return status
    try:
        check_resources(root);heartbeat('validating')
        snapshot=run['source_snapshot']
        current_permission(conn,snapshot['trainingSource'])
        if snapshot.get('externalSource'):current_permission(conn,snapshot['externalSource'])
        prepared=prepare_inputs(root,snapshot,run['settings']);heartbeat()
        runtime=select_runtime({'device':'cpu'},force=True,heartbeat=heartbeat)
        compatible_runtime(snapshot,runtime)
        if runtime['versions']!=run['runtime_snapshot']['versions']:raise DatasetError('Runtime changed after submission. Retry after checking the environment.')
        stage.mkdir(parents=True,exist_ok=False)
        shutil.copyfile(prepared['tokenizerPath'],stage/'tokenizer.json')
        checkpoints=[]
        for cp in snapshot['checkpoints']:
            verified=verify_checkpoint(root,cp)
            target=stage/'checkpoints'/cp['id'];target.mkdir(parents=True)
            # No optimizer/RNG tensor state is copied or loaded for inference.
            for name in ('config.json','model.safetensors','generation_config.json'):
                if (verified/name).is_file():shutil.copyfile(verified/name,target/name)
            checkpoints.append({'id':cp['id'],'step':cp['step']})
        write_jsonl(stage/'records.jsonl',prepared['records']);write_jsonl(stage/'subset.jsonl',prepared['subsetRecords'])
        write_json(stage/'request.json',{'configuration':snapshot['configuration'],'settings':run['settings'],
            'checkpoints':checkpoints,'runtime':runtime,'heldOutAvailable':prepared['heldOutAvailable'],'warnings':prepared['warnings']})
        heartbeat('loading')
        process=subprocess.Popen([str(training_python()),'-m','app.inference.process',str(stage)],cwd=BACKEND,
            env=child_environment(),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=os.name=='posix')
        while process.poll() is None:
            heartbeat(events());stopping.wait(.25)
        heartbeat(events())
        if process.returncode:
            detail=json.loads((stage/'error.json').read_text())['detail'] if (stage/'error.json').exists() else 'Inference process failed. Check the runtime.'
            raise DatasetError(detail)
        heartbeat('verifying')
        report=json.loads((stage/'report.json').read_text())
        if len(report['results'])!=len(snapshot['checkpoints']) or not all(r['weightsUnchanged'] for r in report['results']):
            raise DatasetError('Inference report did not pass integrity verification.')
        # Revalidate original artifacts after executing the child.
        for cp in snapshot['checkpoints']:verify_checkpoint(root,cp)
        write_jsonl(stage/'outputs.jsonl',[{'checkpointId':r['checkpointId'],'step':r['step'],**g} for r in report['results'] for g in r['generations']])
        shutil.rmtree(stage/'checkpoints')
        for private in ('records.jsonl','subset.jsonl','request.json','tokenizer.json'):(stage/private).unlink()
        artifacts={key:describe(stage/name) for key,name in (('report','report.json'),('outputs','outputs.jsonl'),('events','events.jsonl'))}
        manifest={'schemaVersion':1,'kind':run['kind'],'runId':str(run['id']),'trainingRunId':snapshot['trainingRunId'],
            'source':{**{k:snapshot['trainingSource'][k] for k in ('datasetId','datasetVersionId','datasetVersion','datasetName','sequenceRunId','tokenizerRunId','sourceIdentity')},
                      'datasetManifestSha256':snapshot['trainingSource']['dataset']['manifestSha256']},
            'checkpoints':[{'id':c['id'],'step':c['step'],'modelSha256':c['manifest']['checkpoint']['files']['model.safetensors']['sha256'],
                           'checkpointManifestSha256':c['manifest']['descriptor']['sha256']} for c in snapshot['checkpoints']],
            'evaluationSource':{'datasetVersionId':snapshot['externalSource']['datasetVersionId'],'manifestSha256':snapshot['externalSource']['manifestSha256']} if snapshot.get('externalSource') else None,
            'settings':run['settings'],'runtime':runtime,'report':report,'artifacts':artifacts}
        write_json(stage/'manifest.json',manifest);artifacts['manifest']=describe(stage/'manifest.json')
        artifacts['bundle']=make_zip(stage/'bundle.zip',[(p,p.name) for p in stage.iterdir() if p.is_file()])
        if sum(p.stat().st_size for p in stage.iterdir() if p.is_file())>MAX_OUTPUT_BYTES:raise DatasetError('Inference output exceeded 128 MiB.')
        with conn.transaction():
            current=conn.execute('SELECT * FROM inference_runs WHERE id=%s FOR UPDATE',(run['id'],)).fetchone()
            if current['cancel_requested']:raise InferenceCancelled()
            if stopping.is_set():raise DatasetError('Inference interrupted before publication.')
            stage.rename(final)
            conn.execute("UPDATE inference_runs SET status='completed',manifest=%s,metrics=%s,finished_at=now(),heartbeat_at=now() WHERE id=%s",(Jsonb(manifest),Jsonb(metrics),run['id']))
    except InferenceCancelled:
        conn.execute("UPDATE inference_runs SET status='cancelled',finished_at=now() WHERE id=%s AND status=ANY(%s)",(run['id'],list(RUNNING)))
    except Exception as exc:
        detail=str(exc) if isinstance(exc,DatasetError) else 'Inference failed while validating or publishing artifacts. Check storage/runtime availability.'
        try:conn.execute("UPDATE inference_runs SET status='failed',error=%s,finished_at=now() WHERE id=%s AND status=ANY(%s)",(detail,run['id'],list(RUNNING)))
        except Exception:pass
    finally:
        if process and process.poll() is None:stop_child(process)
        shutil.rmtree(stage,ignore_errors=True)
