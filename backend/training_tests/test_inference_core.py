import math

import pytest
import torch
from tokenizers import Tokenizer,decoders,models,pre_tokenizers,trainers

from app.inference.core import generate,load_model,score
from app.inference.data import summarize_loss
from app.training.core import batch,new_model


def configuration(vocab=260,length=8):
    h=16;layers=1
    return {'vocabSize':vocab,'contextLength':length,'hiddenSize':h,'layers':layers,'heads':2,
            'estimatedParameters':vocab*h+length*h+layers*(12*h*h+13*h)+2*h}


def test_evaluation_loss_is_target_weighted_and_padding_ignored():
    torch.manual_seed(42);cfg=configuration();model=new_model(cfg).eval()
    a={'input_ids':[2,8,9,3,0,0,0,0],'attention_mask':[1,1,1,1,0,0,0,0],'labels':[2,8,9,3,-100,-100,-100,-100],'split':'validation','documentId':'a'}
    b={'input_ids':[2,11,12,13,14,15,3,0],'attention_mask':[1,1,1,1,1,1,1,0],'labels':[2,11,12,13,14,15,3,-100],'split':'validation','documentId':'b'}
    expected=[]
    with torch.no_grad():
        for record in (a,b):
            data=batch(record,'cpu');logits=model(**data,use_cache=False).logits
            expected.append(torch.nn.functional.cross_entropy(logits[:,:-1].reshape(-1,260),data['labels'][:,1:].reshape(-1),ignore_index=-100).item())
    result=score(model,[a,b],cfg)
    assert result['targetTokens']==9 and result['documents']==2 and result['blocks']==2
    assert result['loss']==pytest.approx((expected[0]*3+expected[1]*6)/9,abs=1e-7)
    assert result['perplexity']==pytest.approx(math.exp(result['loss']))
    assert score(model,[],cfg)['loss'] is None


def test_perplexity_overflow_and_nonfinite_are_explicit():
    assert summarize_loss(1000,1,1,1)['perplexityOverflow']
    assert summarize_loss(1000,1,1,1)['perplexity'] is None
    with pytest.raises(ValueError,match='nonfinite'):summarize_loss(float('nan'),1,1,1)


def test_inference_loads_only_safetensors_and_generates_deterministically(tmp_path,monkeypatch):
    torch.set_num_threads(2);torch.manual_seed(42)
    tokenizer=Tokenizer(models.BPE(unk_token='[UNK]'));tokenizer.pre_tokenizer=pre_tokenizers.ByteLevel(add_prefix_space=False);tokenizer.decoder=decoders.ByteLevel()
    tokenizer.train_from_iterator(['Hello বাংলা [EOS] world'],trainers.BpeTrainer(vocab_size=280,special_tokens=['[PAD]','[UNK]','[BOS]','[EOS]'],initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),show_progress=False))
    tokenizer.encode_special_tokens=True
    cfg=configuration(tokenizer.get_vocab_size(),128);new_model(cfg).save_pretrained(tmp_path,safe_serialization=True)
    def forbidden(*args,**kwargs):raise AssertionError('Inference must not torch.load training state')
    monkeypatch.setattr(torch,'load',forbidden)
    model=load_model(tmp_path,cfg);assert not model.training and not any(p.requires_grad for p in model.parameters())
    before={k:v.clone() for k,v in model.state_dict().items()}
    a=generate(model,tokenizer,'বাংলা [EOS]',8);b=generate(model,tokenizer,'বাংলা [EOS]',8)
    assert a['newTokenIds']==b['newTokenIds'] and a['generatedTokenCount']<=8
    assert all(i>=4 for i in tokenizer.encode('বাংলা [EOS]',add_special_tokens=False).ids)
    for key,value in before.items():assert torch.equal(value,model.state_dict()[key])
    with pytest.raises(ValueError,match='context'):generate(model,tokenizer,'Hello '*200,128)
