"""Run explicitly with .venv-training/bin/python -m pytest backend/training_tests."""
import copy
import json

import pytest
import torch

from app.training.core import batch, execute, load_checkpoint, new_model, step_model
from app.training.data import validate_record, write_json


def settings():
    h,vocab,context,layers=16,260,8,1
    return {'vocabSize':vocab,'contextLength':context,'hiddenSize':h,'layers':layers,'heads':2,
            'estimatedParameters':vocab*h+context*h+layers*(12*h*h+13*h)+2*h,
            'seed':42,'learningRate':0.003,'device':'cpu','maxSteps':8,'checkpointEvery':4,'timeLimitSeconds':60}


def records():
    return [{'input_ids':[2,8,9,10,3,0,0,0],'attention_mask':[1,1,1,1,1,0,0,0],
             'labels':[2,8,9,10,3,-100,-100,-100],'split':'train'},
            {'input_ids':[2,11,12,13,14,15,3,0],'attention_mask':[1,1,1,1,1,1,1,0],
             'labels':[2,11,12,13,14,15,3,-100],'split':'train'}]


@pytest.fixture(autouse=True)
def deterministic_cpu():
    torch.set_num_threads(2);torch.manual_seed(42)


def test_causal_loss_shifts_exactly_once_and_ignores_padding():
    cfg=settings();model=new_model(cfg).eval();record=records()[0]
    inputs=batch(record,'cpu');output=model(**inputs,use_cache=False)
    expected=torch.nn.functional.cross_entropy(output.logits[:,:-1].reshape(-1,cfg['vocabSize']),inputs['labels'][:,1:].reshape(-1),ignore_index=-100)
    torch.testing.assert_close(output.loss,expected)
    # Right-padding input values cannot influence earlier causal predictions.
    altered={k:v.clone() for k,v in inputs.items()};altered['input_ids'][0,5:]=200
    torch.testing.assert_close(model(**altered,use_cache=False).loss,output.loss)
    logits=output.logits.detach().requires_grad_(True)
    torch.nn.functional.cross_entropy(logits[:,:-1].reshape(-1,cfg['vocabSize']),inputs['labels'][:,1:].reshape(-1),ignore_index=-100).backward()
    assert torch.count_nonzero(logits.grad[:,4:])==0


@pytest.mark.parametrize('kind',['shifted','left-padding','range','bool','too-short','validation'])
def test_invalid_sequence_contract_rejected(kind):
    record=copy.deepcopy(records()[0])
    if kind=='shifted':record['labels']=record['labels'][1:]+[-100]
    if kind=='left-padding':record['attention_mask']=[0,0,0,1,1,1,1,1]
    if kind=='range':record['input_ids'][1]=260
    if kind=='bool':record['labels'][1]=True
    if kind=='too-short':record['attention_mask']=[1,0,0,0,0,0,0,0]
    if kind=='validation':record['split']='validation'
    with pytest.raises(ValueError):validate_record(record,260,8)


def test_nonfinite_gradient_stops_optimizer_update():
    cfg=settings();model=new_model(cfg);optimizer=torch.optim.AdamW(model.parameters(),lr=0.003)
    initial=next(model.parameters()).detach().clone()
    handle=next(model.parameters()).register_hook(lambda gradient:torch.full_like(gradient,float('nan')))
    with pytest.raises(ValueError,match='gradients'):step_model(model,optimizer,records()[0],'cpu')
    assert torch.equal(initial,next(model.parameters()).detach());handle.remove()


def test_checkpoint_reload_and_resumed_update_match_uninterrupted(tmp_path):
    cfg=settings();events=[]
    def run(name,resume=None):
        directory=tmp_path/name;directory.mkdir();checkpoints=directory/'checkpoints';checkpoints.mkdir()
        write_json(directory/'configuration.json',cfg)
        write_json(directory/'request.json',{'device':'cpu','sourceIdentity':'fixture-source','resumePath':str(resume) if resume else None})
        (directory/'subset.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records()))
        result=execute(directory,checkpoints,events.append)
        return checkpoints,result
    full,result=run('full')
    assert result['finiteGradients'] and result['weightsChanged'] and result['finalLoss']<result['initialLoss']
    model,optimizer,state=load_checkpoint(full/'step-000008',cfg,'fixture-source','cpu')
    assert state['step']==8 and optimizer.state_dict()['state']
    assert state['configuration']==cfg and state['schedule']['name']=='constant'
    assert state['subsetSize']==2 and state['subsetCursor']==0
    resumed,resume_result=run('resumed',full/'step-000004')
    other,_,state=load_checkpoint(resumed/'step-000008',cfg,'fixture-source','cpu')
    assert resume_result['startingStep']==4 and resume_result['initialLoss']==result['initialLoss']
    assert resume_result['finalLoss']==pytest.approx(result['finalLoss'],abs=1e-7)
    for key,value in model.state_dict().items():torch.testing.assert_close(value,other.state_dict()[key],rtol=0,atol=0)
    # Integrity verification happens before loading any tensor state.
    (resumed/'step-000008'/'training-state.pt').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='integrity'):load_checkpoint(resumed/'step-000008',cfg,'fixture-source','cpu')


def test_out_of_memory_is_reported_without_native_trace(tmp_path,monkeypatch):
    from app.training.process import main
    def oom(*args,**kwargs):raise RuntimeError('CUDA out of memory: native internal traceback')
    monkeypatch.setattr('app.training.core.execute',oom)
    assert main(tmp_path,tmp_path/'checkpoints')==1
    detail=json.loads((tmp_path/'error.json').read_text())['detail']
    assert 'out of memory' in detail and 'native internal' not in detail
