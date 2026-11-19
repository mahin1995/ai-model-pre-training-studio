import hashlib
import json

from fastapi import HTTPException

from ..datasets.storage import DatasetError, read_jsonl, storage_path
from ..models.source import current_permission, inspect_source
from ..tokenizers.pipeline import load_tokenizer
from ..tokenizers.router import source_snapshot
from ..tokenizers.sequences import build_blocks
from ..tokenizers.source import load_documents
from ..tokenizers.storage import verified_artifact
from ..training.router import find_smoke
from ..training.storage import verify_checkpoint
from .data import validate_block
from .schemas import MAX_BLOCKS


def checkpoint_snapshot(conn, root, project_id, checkpoint_ids):
    rows=[]; parent=None
    for checkpoint_id in checkpoint_ids:
        row=conn.execute('''SELECT c.* FROM smoke_checkpoints c JOIN smoke_runs r ON r.id=c.run_id
            WHERE c.id=%s AND r.project_id=%s''',(checkpoint_id,project_id)).fetchone()
        if not row:raise HTTPException(404,'Checkpoint not found in this project.')
        if parent is None:parent=find_smoke(conn,project_id,row['run_id'],lock=True)
        if row['run_id']!=parent['id']:raise HTTPException(409,'Compare checkpoints from the same training run.')
        if parent['status']!='completed':raise HTTPException(409,'Choose checkpoints from a completed training run.')
        if row['manifest']['checkpoint']['device']!='cpu':
            raise HTTPException(409,'This version supports CPU-trained checkpoints on the CPU runtime.')
        info=row['manifest']['checkpoint']
        expected=hashlib.sha256(json.dumps(parent['configuration'],sort_keys=True).encode()).hexdigest()
        if info['configHash']!=expected or info['sourceIdentity']!=parent['source_snapshot']['sourceIdentity']:
            raise HTTPException(409,'Checkpoint configuration/source lineage does not match its training run.')
        verify_checkpoint(root,row)
        rows.append({'id':str(row['id']),'step':row['step'],'storage_key':row['storage_key'],'manifest':row['manifest']})
    current_permission(conn,parent['source_snapshot'])
    return {'trainingRunId':str(parent['id']),'configuration':parent['configuration'],
            'trainingKind':parent['training_kind'], 'trainingSource':parent['source_snapshot'],'trainingReport':parent['manifest']['report'],
            'checkpoints':sorted(rows,key=lambda r:r['step'])}


def frozen_tokenizer(root,snapshot):
    saved=snapshot['trainingSource']['tokenizer']
    verified_artifact(root,saved,'manifest')
    path=verified_artifact(root,saved,'tokenizer')
    tokenizer=load_tokenizer(path)
    if tokenizer.get_vocab_size()!=snapshot['configuration']['vocabSize']:
        raise DatasetError('Checkpoint vocabulary differs from its saved tokenizer.')
    return tokenizer,path


def check_prompts(tokenizer,config,prompts,new_tokens):
    counts=[]
    for prompt in prompts:
        ids=tokenizer.encode(prompt['text'],add_special_tokens=False).ids
        if len(ids)+1+new_tokens>config['contextLength']:
            raise DatasetError('Prompt plus BOS and requested new tokens exceeds the checkpoint context. Shorten the prompt or output limit.')
        counts.append(len(ids))
    return counts


def text_hash(text):return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()


def reject_overlap(root,training,target,train_documents,target_documents):
    if training['datasetId']==target['datasetId']:
        raise DatasetError('External evaluation overlaps the original dataset lineage. Choose independent documents.')
    def file_hashes(s):return {f['sha256'] for f in s['manifest'].get('rawFiles',[]) if f.get('sha256')}
    if file_hashes(training)&file_hashes(target):
        raise DatasetError('External evaluation contains a file used by the original source.')
    if {d['documentId'] for d in train_documents}&{d['documentId'] for d in target_documents}:
        raise DatasetError('External evaluation shares training document IDs.')
    if {text_hash(d['text']) for d in train_documents}&{text_hash(d['text']) for d in target_documents}:
        raise DatasetError('External evaluation duplicates cleaned training-document content.')
    def records(s):return list(read_jsonl(storage_path(root,s['storageKey'])/'processed.jsonl'))
    train_ids={i for d in train_documents for i in d['recordIds']}
    a=[r for r in records(training) if r['id'] in train_ids];b=records(target)
    if {text_hash(r['text']) for r in a}&{text_hash(r['text']) for r in b}:
        raise DatasetError('External evaluation duplicates cleaned training-record content.')
    # Manually supplied group labels are dataset-scoped. PDF hash groups are global.
    groups=lambda rows:{r['group_id'] for r in rows if str(r.get('group_id','')).startswith('pdf:')}
    if groups(a)&groups(b):raise DatasetError('External evaluation shares a PDF training group.')


def encode_documents(documents,tokenizer,length):
    result=[]
    for doc in documents:
        encoded=tokenizer.encode(doc['text'],add_special_tokens=False)
        if tokenizer.decode(encoded.ids,skip_special_tokens=False)!=doc['text']:
            raise DatasetError('Frozen tokenizer did not preserve evaluation text.')
        ids=[2]+encoded.ids+[3]
        if (len(ids)+length-1)//length+len(result)>MAX_BLOCKS:
            raise DatasetError('Evaluation exceeds 256 blocks. Select a smaller reviewed corpus; no text was dropped.')
        cursor=0
        for ordinal,block in enumerate(build_blocks(ids,length),1):
            n=sum(block['attention_mask'])
            result.append({**block,**{k:doc[k] for k in ('documentId','recordIds','pages','filename','split')},
                           'tokenRange':[cursor,cursor+n],'ordinal':ordinal})
            cursor+=n
    return result


def prepare_inputs(root,snapshot,settings):
    tokenizer,path=frozen_tokenizer(root,snapshot)
    config=snapshot['configuration']
    counts=check_prompts(tokenizer,config,settings['prompts'],settings['maxNewTokens'])
    result={'tokenizerPath':path,'promptTokenCounts':counts,'records':[], 'subsetRecords':[],
            'metricScope':settings.get('metricScope'),'warnings':[], 'heldOutAvailable':False}
    if settings['kind']=='generation':return result
    original=snapshot['trainingSource']
    inspected=inspect_source(root,original,config)
    sequence=original['sequence']
    training_docs=load_documents(root,original['dataset'])
    train_docs=[d for d in training_docs if d['split']=='train']
    pilot = config.get('trainingKind') == 'pilot'
    result['subsetRecords']=inspected['trainingRecords'] if pilot else inspected['subset']
    if settings['metricScope']=='external':
        target=snapshot['externalSource']
        documents=load_documents(root,target)
        reject_overlap(root,original['dataset'],target,train_docs,documents)
        records=encode_documents(documents,tokenizer,config['contextLength'])
        result['heldOutAvailable']=True
        result['warnings'].append('External evaluation uses frozen tokenizer encoding; exact overlap checks cannot rule out near-duplicates. Review independence manually.')
    else:
        split='train' if settings['metricScope']=='training' else 'validation'
        records=[]
        for record in read_jsonl(verified_artifact(root,sequence,split)):
            records.append(record)
            if len(records)>MAX_BLOCKS:raise DatasetError('Evaluation exceeds 256 blocks. No records were silently sampled.')
        if len(records)!=sequence['manifest']['counts'][split]['sequences']:
            raise DatasetError('Evaluation block count differs from the source manifest.')
        if split=='validation':
            # Verify the immutable split against frozen-tokenizer reconstruction.
            expected=encode_documents([d for d in training_docs if d['split']==split],tokenizer,config['contextLength'])
            if records!=expected:raise DatasetError('Validation blocks differ from reviewed document content.')
            result['heldOutAvailable']=bool(records)
    for record in records:
        try:validate_block(record,config['vocabSize'],config['contextLength'])
        except ValueError as exc:raise DatasetError(str(exc)) from None
    result['records']=records
    if settings['metricScope']=='training':
        result['warnings'].append('Training diagnostic only. The pilot trained on all source train blocks.' if pilot else 'Training diagnostic only. All source train blocks include the smoke subset; other blocks from the same source are not independent held-out data.')
    elif not records:
        result['warnings'].append('Not available — add independent documents. No held-out loss/perplexity was computed.')
    result['warnings'].append('Block-based NLL/PPL v1: document-isolated non-overlapping blocks; not sliding-window corpus perplexity. Perplexity is not accuracy.')
    return result


def external_snapshot(conn,root,project_id,version_id):
    return source_snapshot(conn,root,project_id,version_id)
