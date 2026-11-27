import hashlib
import json

from fastapi import HTTPException

from ..datasets.storage import DatasetError, read_jsonl, storage_path
from ..models.source import current_permission, inspect_source
from ..tokenizers.pipeline import load_tokenizer
from ..tokenizers.router import source_snapshot
from ..tokenizers.sequences import build_blocks
from ..tokenizers.sft import document_sequence
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


def evaluation_snapshot(conn, root, project_id, checkpoint_ids, scope):
    if scope not in {'external', 'final-test'}:
        return checkpoint_snapshot(conn, root, project_id, checkpoint_ids)

    # Lock the referenced runs in one stable order to avoid competing comparisons
    # taking the same pair in opposite orders.
    rows = conn.execute("""SELECT r.id FROM smoke_runs r
        WHERE r.project_id=%s AND EXISTS (
            SELECT 1 FROM smoke_checkpoints c WHERE c.run_id=r.id AND c.id=ANY(%s::uuid[])
        ) ORDER BY r.id FOR UPDATE""", (project_id, checkpoint_ids)).fetchall()
    if len(rows) <= 1:
        return checkpoint_snapshot(conn, root, project_id, checkpoint_ids)

    candidates = [checkpoint_snapshot(conn, root, project_id, [checkpoint]) for checkpoint in checkpoint_ids]
    anchor = candidates[0]
    keys = ('architecture', 'vocabSize', 'contextLength', 'layers', 'hiddenSize', 'heads', 'estimatedParameters')
    tokenizer = anchor['trainingSource']['tokenizer']['manifest']['artifacts']['tokenizer']['sha256']
    for candidate in candidates:
        if any(candidate['configuration'][key] != anchor['configuration'][key] for key in keys):
            raise DatasetError('Cross-run evaluation requires identical checkpoint architecture and context.')
        if candidate['trainingSource']['tokenizer']['manifest']['artifacts']['tokenizer']['sha256'] != tokenizer:
            raise DatasetError('Cross-run evaluation requires the same frozen tokenizer.')
    return {**anchor, 'comparisonSources': [candidate['trainingSource'] for candidate in candidates],
            'checkpoints': [{**candidate['checkpoints'][0], 'trainingRunId': candidate['trainingRunId']}
                            for candidate in candidates]}


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
    target_ids={i for d in target_documents for i in d['recordIds']}
    a=[r for r in records(training) if r['id'] in train_ids]
    b=[r for r in records(target) if r['id'] in target_ids]
    if {text_hash(r['text']) for r in a}&{text_hash(r['text']) for r in b}:
        raise DatasetError('External evaluation duplicates cleaned training-record content.')
    # Manually supplied group labels are dataset-scoped. PDF hash groups are global.
    groups=lambda rows:{r['group_id'] for r in rows if str(r.get('group_id','')).startswith('pdf:')}
    if groups(a)&groups(b):raise DatasetError('External evaluation shares a PDF training group.')


def encode_documents(documents,tokenizer,length, assistant_only=False):
    result=[]
    for doc in documents:
        encoded=tokenizer.encode(doc['text'],add_special_tokens=False)
        if tokenizer.decode(encoded.ids,skip_special_tokens=False)!=doc['text']:
            raise DatasetError('Frozen tokenizer did not preserve evaluation text.')
        if assistant_only:
            block = document_sequence(tokenizer, doc, length)
            ids = block['input_ids'][:sum(block['attention_mask'])]
            blocks = [block]
        else:
            ids = [2] + encoded.ids + [3]
            blocks = build_blocks(ids, length)
        if (len(ids)+length-1)//length+len(result)>MAX_BLOCKS:
            raise DatasetError('Evaluation exceeds 256 blocks. Select a smaller reviewed corpus; no text was dropped.')
        cursor=0
        for ordinal,block in enumerate(blocks,1):
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
    sft = config.get('objective') == 'sft'
    result['subsetRecords']=inspected['trainingRecords'] if pilot else inspected['subset']
    earlier_sources = list(original.get('ancestorDatasets', ()))
    if fit_source := original.get('tokenizerFitSource'):
        earlier_sources.append(fit_source)

    def verify_earlier_sources(target, documents):
        for source in earlier_sources:
            # Exact resume and same-version warm starts use the original split.
            if source['manifestSha256'] == original['dataset']['manifestSha256']:
                continue
            earlier_train = [doc for doc in load_documents(root, source) if doc['split'] == 'train']
            reject_overlap(root, source, target, earlier_train, documents)

    scope = settings['metricScope']
    if scope in {'external', 'final-test'}:
        target=snapshot['externalSource']
        documents=load_documents(root,target)
        if scope == 'final-test':
            documents = [doc for doc in documents if doc['split'] == 'test']
            if not documents:
                raise DatasetError('Select a reviewed Q&A dataset containing reserved final-test documents.')
        reject_overlap(root,original['dataset'],target,train_docs,documents)
        verify_earlier_sources(target, documents)
        if comparison_sources := snapshot.get('comparisonSources'):
            seen = {original['dataset']['manifestSha256'], *(item['manifestSha256'] for item in earlier_sources)}
            for candidate in comparison_sources:
                sources = [candidate['dataset'], *candidate.get('ancestorDatasets', ())]
                if fitted := candidate.get('tokenizerFitSource'):
                    sources.append(fitted)
                for source in sources:
                    if source['manifestSha256'] in seen:
                        continue
                    seen.add(source['manifestSha256'])
                    train = [doc for doc in load_documents(root, source) if doc['split'] == 'train']
                    reject_overlap(root, source, target, train, documents)
            result['subsetRecords'] = []
            result['warnings'].append('Trained-subset scores are omitted for cross-run comparisons.')
        records=encode_documents(documents,tokenizer,config['contextLength'], scope == 'final-test')
        result['heldOutAvailable']=True
        result['warnings'].append('External evaluation uses frozen tokenizer encoding; exact overlap checks cannot rule out near-duplicates. Review independence manually.')
    else:
        split = 'train' if scope == 'training' else scope
        records=[]
        for record in read_jsonl(verified_artifact(root,sequence,split)):
            records.append(record)
            if len(records)>MAX_BLOCKS:raise DatasetError('Evaluation exceeds 256 blocks. No records were silently sampled.')
        if len(records)!=sequence['manifest']['counts'][split]['sequences']:
            raise DatasetError('Evaluation block count differs from the source manifest.')
        if split in {'validation', 'test'}:
            # Verify the immutable split against frozen-tokenizer reconstruction.
            held_out_docs = [doc for doc in training_docs if doc['split'] == split]
            if held_out_docs:
                verify_earlier_sources(original['dataset'], held_out_docs)
            expected=encode_documents(held_out_docs,tokenizer,config['contextLength'], sft)
            if records != expected:
                raise DatasetError('Held-out blocks differ from reviewed document content.')
            if split == 'test' and not records:
                raise DatasetError('This checkpoint has no reserved test blocks.')
            result['heldOutAvailable']=bool(records)
    for record in records:
        try:validate_block(record,config['vocabSize'],config['contextLength'], scope == 'final-test' or (sft and scope != 'external'))
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
