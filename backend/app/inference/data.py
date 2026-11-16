"""Numerical contracts usable in the training interpreter without API imports."""
import math

from ..training.data import validate_record


def validate_block(record, vocab, length):
    return validate_record({**record,'split':'train'},vocab,length)


def summarize_loss(weighted_loss, targets, blocks, documents):
    if targets <= 0:
        return {'available':False,'reason':'Not available — add independent documents.','loss':None,'perplexity':None,
                'targetTokens':0,'blocks':0,'documents':0}
    loss=weighted_loss/targets
    if not math.isfinite(loss):raise ValueError('Evaluation produced a nonfinite loss.')
    overflow=loss>math.log(__import__('sys').float_info.max)
    return {'available':True,'loss':loss,'perplexity':None if overflow else math.exp(loss),
            'perplexityOverflow':overflow,'targetTokens':targets,'blocks':blocks,'documents':documents}
