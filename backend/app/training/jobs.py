import json
import math
import os
import shutil
import subprocess
import time
from uuid import uuid4

from psycopg.types.json import Jsonb

from ..datasets.storage import DatasetError, storage_path, write_jsonl
from ..models.source import current_permission, inspect_source
from ..tokenizers.jobs import stop_child
from ..tokenizers.storage import verified_artifact, write_json
from .data import describe
from .runtime import BACKEND, child_environment, select_runtime, training_python
from .storage import MAX_BYTES, check_resources, checked_file, make_zip, verify_checkpoint

ACTIVE = ('queued', 'validating', 'initializing', 'training', 'verifying')
RUNNING = ACTIVE[1:]


class SmokeCancelled(Exception):
    pass


def claim_smoke(conn, worker_id):
    with conn.transaction():
        run = conn.execute("SELECT * FROM smoke_runs WHERE status='queued' ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
        if run:
            conn.execute("UPDATE smoke_runs SET status='validating',worker_id=%s,started_at=now(),heartbeat_at=now() WHERE id=%s", (worker_id, run['id']))
        return run


def recover_smoke(conn, root):
    rows = conn.execute("""UPDATE smoke_runs SET status='failed',verdict='failed',finished_at=now(),
        error='Training was interrupted. Retry from scratch or inspect saved checkpoints.'
        WHERE status=ANY(%s) AND (heartbeat_at IS NULL OR heartbeat_at<now()-interval '60 seconds') RETURNING storage_key""", (list(RUNNING),)).fetchall()
    for row in rows:
        base = storage_path(root, row['storage_key']).parent
        shutil.rmtree(base/'.tmp-results', ignore_errors=True)
        for directory in (base/'checkpoints').glob('.tmp-*'):
            shutil.rmtree(directory, ignore_errors=True)


def publish_checkpoints(conn, root, run, checkpoints):
    for path in sorted(checkpoints.glob('step-*/checkpoint.json')):
        info = json.loads(path.read_text())
        step = info['step']
        if type(step) is not int or step <= 0 or step > run['configuration']['maxSteps']:
            raise DatasetError('Checkpoint step is outside the run budget.')
        if conn.execute('SELECT 1 FROM smoke_checkpoints WHERE run_id=%s AND step=%s', (run['id'],step)).fetchone():
            continue
        key = path.parent.relative_to(root).as_posix()
        for entry in info['files'].values():
            checked_file(root, key, entry)
        bundle = make_zip(path.parent/'checkpoint.zip', [(f, f.name) for f in path.parent.iterdir() if f.is_file() and f.name not in ('checkpoint.zip', 'checkpoint.tmp')])
        manifest = {'checkpoint': info, 'descriptor': describe(path), 'bundle': bundle}
        conn.execute('INSERT INTO smoke_checkpoints(id,run_id,step,storage_key,manifest) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(run_id,step) DO NOTHING',
                     (uuid4(),run['id'],step,key,Jsonb(manifest)))


def execute_smoke(conn, root, run, stopping):
    pilot = run.get('training_kind') == 'pilot'
    final = storage_path(root, run['storage_key'])
    base, stage = final.parent, final.parent/'.tmp-results'
    checkpoints = base/'checkpoints'
    process = None
    offset = 0
    metrics = dict(run.get('metrics') or {})
    deadline = time.monotonic() + run['configuration']['timeLimitSeconds']

    def heartbeat(status=None):
        if stopping.is_set():
            raise DatasetError('Training stopped during server shutdown. Retry this run.')
        row = conn.execute('SELECT cancel_requested FROM smoke_runs WHERE id=%s', (run['id'],)).fetchone()
        if not row or row['cancel_requested']:
            raise SmokeCancelled()
        if time.monotonic() > deadline:
            raise DatasetError('Training time limit exceeded. Reduce epochs, sequence length or model size.')
        conn.execute('UPDATE smoke_runs SET heartbeat_at=now(),metrics=%s'+(',status=%s' if status else '')+' WHERE id=%s',
                     (Jsonb(metrics), status, run['id']) if status else (Jsonb(metrics),run['id']))

    def consume_events():
        nonlocal offset
        path = stage/'metrics.jsonl'
        if not path.exists():
            return None
        if path.stat().st_size > 4 * 1024**2:
            raise DatasetError('Training metrics exceeded the bounded log limit.')
        with path.open('rb') as stream:
            stream.seek(offset)
            pending = stream.read()
        end = pending.rfind(b'\n')+1
        offset += end
        last_stage = None
        for line in pending[:end].splitlines():
            event = json.loads(line)
            if any(isinstance(v,float) and not math.isfinite(v) for v in event.values()):
                raise DatasetError('Training emitted nonfinite metrics.')
            metrics.update(event)
            if event.get('stage') in RUNNING:
                last_stage = event['stage']
        return last_stage

    def wait_for_child(command, status):
        nonlocal process
        heartbeat(status)
        process = subprocess.Popen([str(training_python()), '-m', command, str(stage)] + ([str(checkpoints)] if command.endswith('.process') else []),
            cwd=BACKEND, env=child_environment(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=os.name=='posix')
        while process.poll() is None:
            heartbeat(consume_events())
            publish_checkpoints(conn, root, run, checkpoints)
            if sum(p.stat().st_size for p in base.rglob('*') if p.is_file()) > MAX_BYTES:
                raise DatasetError('Training artifacts exceeded the 1 GiB run limit.')
            stopping.wait(0.25)
        heartbeat(consume_events())
        publish_checkpoints(conn, root, run, checkpoints)
        if process.returncode:
            detail = 'Training subprocess failed. Inspect the isolated runtime, memory and disk availability.'
            if (stage/'error.json').exists():
                detail = json.loads((stage/'error.json').read_text())['detail']
            raise DatasetError(detail)

    try:
        check_resources(root)
        current_permission(conn, run['source_snapshot'])
        heartbeat('validating')
        source = inspect_source(root, run['source_snapshot'], run['configuration'])
        runtime = select_runtime(run['configuration'], force=True, heartbeat=heartbeat)
        if runtime['versions'] != run['runtime_snapshot']['versions'] or runtime['device'] != run['runtime_snapshot']['device']:
            raise DatasetError('Training runtime changed after submission. Retry to snapshot the current compatible runtime.')
        stage.mkdir(parents=True, exist_ok=False)
        checkpoints.mkdir(parents=True, exist_ok=True)
        write_json(stage/'configuration.json', run['configuration'])
        write_jsonl(stage/('train.jsonl' if pilot else 'subset.jsonl'), source['trainingRecords'] if pilot else source['subset'])
        saved = run['source_snapshot']['tokenizer']
        for key, filename in (('tokenizer','tokenizer.json'),('config','tokenizer_config.json'),('special_tokens','special_tokens_map.json')):
            shutil.copyfile(verified_artifact(root, saved, key), stage/filename)
        resume_path = None
        if run['resume_checkpoint_id']:
            checkpoint = conn.execute('SELECT * FROM smoke_checkpoints WHERE id=%s', (run['resume_checkpoint_id'],)).fetchone()
            if not checkpoint:
                raise DatasetError('Resume checkpoint is unavailable.')
            resume_path = str(verify_checkpoint(root, checkpoint))
        write_json(stage/'request.json', {'device':runtime['device'], 'sourceIdentity':run['source_snapshot']['sourceIdentity'], 'resumePath':resume_path})
        wait_for_child('app.training.process', 'initializing')
        wait_for_child('app.training.verify_process', 'verifying')
        result = json.loads((stage/'training-result.json').read_text())
        verification = json.loads((stage/'verification.json').read_text())
        if not verification['reloadMatches'] or not verification['generationValid'] or result['completedSteps'] != run['configuration']['maxSteps']:
            raise DatasetError('Smoke-test verification did not complete successfully.')
        result.pop('finalCheckpoint', None)
        if pilot and (result['coverage']['completedEpochs'] != run['configuration']['epochs'] or result['coverage']['epochOffset'] != 0
                      or result['coverage']['uniqueBlocksVisited'] != source['trainingSequences']):
            raise DatasetError('Pilot did not cover every requested block/epoch.')
        verdict = None if pilot else ('passed' if result['lossDecreaseRatio'] >= 0.05 else 'needs-attention')
        report = {**result, **verification, 'verdict': verdict, 'sourceIdentity':run['source_snapshot']['sourceIdentity'],
                  'warnings':['All-train diagnostic only; no held-out evaluation was performed.' if pilot else 'Train-subset diagnostic only; no held-out evaluation was performed.']}
        write_json(stage/'report.json', report)
        write_json(stage/'sample.json', verification['sample'])
        if pilot:
            write_json(stage/'coverage.json', result['coverage'])
            (stage/'USAGE.txt').write_text('Whole-dataset CPU pilot. Use this bundle tokenizer with its model.\nLoad model weights from the final checkpoints/step-* directory using GPT2LMHeadModel.from_pretrained.\nTraining loss is a diagnostic; independent evaluation is separate.\nResume requires the original immutable configuration/source and runtime.\n', encoding='utf-8')
        for private in ('request.json','subset.jsonl','train.jsonl','reload-reference.pt','training-result.json','verification.json'):
            (stage/private).unlink(missing_ok=True)
        artifacts = {key: describe(stage/filename) for key,filename in (('report','report.json'),('sample','sample.json'),
            ('metrics','metrics.jsonl'),('config','configuration.json'),('tokenizer','tokenizer.json'),
            ('tokenizer_config','tokenizer_config.json'),('special_tokens','special_tokens_map.json'))}
        if pilot:
            artifacts['coverage'] = describe(stage/'coverage.json')
        manifest = {'schemaVersion':2 if pilot else 1,'kind':'whole-dataset-pilot' if pilot else 'model-smoke-test','runId':str(run['id']), 'configuration':run['configuration'],
            'source':{k:v for k,v in run['source_snapshot'].items() if k not in ('dataset','sequence','tokenizer')},
            'runtime':runtime,'verdict':verdict,'report':report,'artifacts':artifacts}
        write_json(stage/'manifest.json', manifest)
        artifacts['manifest'] = describe(stage/'manifest.json')
        files = [(p,p.name) for p in stage.iterdir() if p.is_file()]
        files += [(p,'checkpoints/'+p.relative_to(checkpoints).as_posix()) for p in checkpoints.rglob('*') if p.is_file() and p.name != 'checkpoint.zip']
        artifacts['bundle'] = make_zip(stage/'bundle.zip', files)
        if sum(p.stat().st_size for p in base.rglob('*') if p.is_file()) > MAX_BYTES:
            raise DatasetError('Training artifacts exceeded the 1 GiB run limit.')
        heartbeat('verifying')
        with conn.transaction():
            current = conn.execute('SELECT * FROM smoke_runs WHERE id=%s FOR UPDATE', (run['id'],)).fetchone()
            if current['cancel_requested']:
                raise SmokeCancelled()
            if stopping.is_set():
                raise DatasetError('Training interrupted before publication. Retry this run.')
            stage.rename(final)
            conn.execute("UPDATE smoke_runs SET status='completed',verdict=%s,manifest=%s,metrics=%s,heartbeat_at=now(),finished_at=now() WHERE id=%s",
                         (verdict,Jsonb(manifest),Jsonb(metrics),run['id']))
    except SmokeCancelled:
        conn.execute("UPDATE smoke_runs SET status='cancelled',finished_at=now() WHERE id=%s AND status=ANY(%s)", (run['id'],list(RUNNING)))
    except Exception as exc:
        detail = str(exc) if isinstance(exc,DatasetError) else 'Training failed while validating or publishing artifacts. Check storage/runtime availability and retry.'
        try:
            conn.execute("UPDATE smoke_runs SET status='failed',verdict='failed',error=%s,finished_at=now() WHERE id=%s AND status=ANY(%s)", (detail,run['id'],list(RUNNING)))
        except Exception:
            pass  # Lost DB lease is recovered on the next worker session.
    finally:
        if process and process.poll() is None:
            stop_child(process)
        for temporary in checkpoints.glob('.tmp-*'):
            shutil.rmtree(temporary, ignore_errors=True)
        if (stage/'metrics.jsonl').is_file():
            try:
                shutil.copyfile(stage/'metrics.jsonl', base/'metrics.jsonl')
            except OSError:
                pass
        shutil.rmtree(stage, ignore_errors=True)
