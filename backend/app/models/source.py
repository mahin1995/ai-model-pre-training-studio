import hashlib
import json

from fastapi import HTTPException

from ..datasets.router import find_dataset
from ..datasets.storage import DatasetError, checksum, read_jsonl
from ..tokenizers.pipeline import load_tokenizer
from ..tokenizers.router import find_run
from ..tokenizers.sft import TEMPLATE_VERSION, document_sequence
from ..tokenizers.source import eligibility, load_documents
from ..tokenizers.storage import verified_artifact
from ..training.data import validate_record
from ..training.pilot import FULL_BLOCK_LIMIT, record_identity, run_limits


def take_snapshot(conn, root, project_id, sequence_id):
    sequence = find_run(conn, project_id, sequence_id, 'sequence')
    dataset = find_dataset(conn, project_id, sequence['dataset_id'], lock=True)
    sequence = find_run(conn, project_id, sequence_id, 'sequence', lock=True)
    tokenizer = find_run(conn, project_id, sequence['tokenizer_run_id'], 'tokenizer', lock=True)
    if sequence['status'] != 'completed' or tokenizer['status'] != 'completed':
        raise HTTPException(409, 'Select completed sequence and tokenizer runs.')
    reason = eligibility(sequence['source_snapshot']['manifest'], dataset['metadata']['permission'])
    if reason:
        raise HTTPException(409, reason)
    if not sequence['manifest']['counts']['train']['sequences']:
        raise HTTPException(409, 'The selected sequence run has no training sequences.')
    def artifact_row(row):
        return {key: row[key] for key in ('status', 'storage_key', 'manifest')}
    dataset_snapshot = {k: v for k, v in sequence['source_snapshot'].items() if k != 'tokenizer'}
    identity = hashlib.sha256(json.dumps({'sequenceId': str(sequence_id), 'manifest': sequence['manifest'],
                                        'tokenizerManifest': tokenizer['manifest']}, sort_keys=True).encode()).hexdigest()
    fit_source = tokenizer['source_snapshot']
    fit_metadata = find_dataset(conn, project_id, tokenizer['dataset_id'])['metadata']
    if fit_metadata['permission'] != 'confirmed':
        raise HTTPException(409, 'Confirm the tokenizer source usage permission before using these sequences.')
    fit_provenance = {}
    if fit_source['datasetVersionId'] != dataset_snapshot['datasetVersionId']:
        fit_provenance['tokenizerFitSource'] = fit_source
    return {**fit_provenance, 'dataset': dataset_snapshot, 'sequence': artifact_row(sequence), 'tokenizer': artifact_row(tokenizer),
            'datasetId': str(sequence['dataset_id']), 'datasetVersionId': str(sequence['dataset_version_id']),
            'tokenizerRunId': str(sequence['tokenizer_run_id']), 'sequenceRunId': str(sequence_id),
            'datasetName': dataset['metadata']['name'], 'datasetVersion': dataset_snapshot['datasetVersion'],
            'sourceIdentity': identity}


def inspect_source(root, snapshot, config=None):
    """Verify immutable sources, complete train coverage, and select fixed subset."""
    sequence, saved_tokenizer = snapshot['sequence'], snapshot['tokenizer']
    documents = load_documents(root, snapshot['dataset'])
    for row in (sequence, saved_tokenizer):
        verified_artifact(root, row, 'manifest')
    tokenizer_path = verified_artifact(root, saved_tokenizer, 'tokenizer')
    if sequence['manifest']['tokenizerSha256'] != checksum(tokenizer_path):
        raise DatasetError('Sequence tokenizer differs from the saved tokenizer.')
    for key in ('tokenizer', 'config', 'special_tokens', 'train', 'validation', 'test', 'tokens'):
        verified_artifact(root, sequence, key)
    tokenizer = load_tokenizer(tokenizer_path)
    vocab, length = tokenizer.get_vocab_size(), sequence['manifest']['sequenceLength']
    if vocab != saved_tokenizer['manifest']['actualVocabSize']:
        raise DatasetError('Saved vocabulary size is inconsistent.')
    if config and (config['vocabSize'] != vocab or config['contextLength'] != length):
        raise DatasetError('Model configuration does not match tokenizer/sequence artifacts.')
    sft = sequence['manifest'].get('objective') == 'sft'
    if sft and sequence['manifest'].get('templateVersion') != TEMPLATE_VERSION:
        raise DatasetError('Unsupported SFT chat template.')
    sft_blocks = {d['documentId']: document_sequence(tokenizer, d, length)
                  for d in documents if sft and d['split'] == 'train'}
    expected = {d['documentId']: {'document': d, 'ids': (sft_blocks[d['documentId']]['input_ids'][:sum(sft_blocks[d['documentId']]['attention_mask'])]
                         if sft else [2]+tokenizer.encode(d['text'], add_special_tokens=False).ids+[3]), 'cursor': 0}
                for d in documents if d['split'] == 'train'}
    selected, records, count = [], [], 0
    for record in read_jsonl(verified_artifact(root, sequence, 'train')):
        try:
            validate_record(record, vocab, length, sft)
        except ValueError as exc:
            raise DatasetError(str(exc)) from None
        source = expected.get(record.get('documentId'))
        if not source:
            raise DatasetError('Training sequence has an unknown document.')
        if sft and any(record[key] != value for key, value in sft_blocks[record['documentId']].items()):
            raise DatasetError('SFT sequence differs from its reviewed example or answer mask.')
        n = sum(record['attention_mask'])
        start = source['cursor']
        doc = source['document']
        if (record['input_ids'][:n] != source['ids'][start:start+n] or record.get('tokenRange') != [start,start+n]
                or any(record.get(key) != doc[key] for key in ('pages', 'recordIds', 'filename'))):
            raise DatasetError('Training sequences differ from reviewed document order/provenance.')
        source['cursor'] += n
        if len(selected) < 2:
            selected.append(record)
        if len(records) < FULL_BLOCK_LIMIT:
            records.append(record)
        count += 1
    if not selected or count != sequence['manifest']['counts']['train']['sequences'] or any(d['cursor'] != len(d['ids']) for d in expected.values()):
        raise DatasetError('Training sequence coverage/count is inconsistent.')
    if config and config.get('trainingKind') == 'pilot':
        limit, _ = run_limits(config.get('profile'))
        if count > limit or count != config['trainingBlocks'] or record_identity(records) != config['recordsSha256']:
            raise DatasetError('Pilot full training coverage differs from the saved configuration.')
    if config and len(tokenizer.encode(config['prompt'], add_special_tokens=False).ids)+1+32 > length:
        raise DatasetError('Generation prompt is too long for this context. Use a shorter prompt.')
    return {'vocabSize': vocab, 'contextLength': length, 'subset': selected, 'trainingSequences': count,
            'objective': 'sft' if sft else 'causal', 'tokenizerPath': tokenizer_path, 'trainingRecords': records}


def current_permission(conn, snapshot):
    dataset_ids = [snapshot['datasetId'], *(source['datasetId'] for source in snapshot.get('ancestorDatasets', ()))]
    if fit_source := snapshot.get('tokenizerFitSource'):
        dataset_ids.append(fit_source['datasetId'])
    rows = conn.execute('SELECT metadata FROM datasets WHERE id=ANY(%s::uuid[])', (dataset_ids,)).fetchall()
    if len(rows) != len(set(dataset_ids)) or any(row['metadata']['permission'] != 'confirmed' for row in rows):
        raise DatasetError('Confirm current dataset usage permission before training.')
