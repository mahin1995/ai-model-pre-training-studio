import json, zipfile, tempfile, hashlib
from pathlib import Path
import torch
from tokenizers import Tokenizer
from transformers import GPT2LMHeadModel
from collections import Counter
base=Path('data/assessments/step-8-2026-11-20')
seq=Path('data/sequences/6c465258-3451-4421-a797-730b5d982760/95556465-6286-411f-a4a4-c45a52a6e213/train.jsonl')
torch.set_num_threads(2)
tok=Tokenizer.from_file(str(base/'baseline/tokenizer.json'));tok.encode_special_tokens=True;tok.no_padding();tok.no_truncation()
prompts=json.loads((base/'prompt-set.json').read_text())['prompts']
records=[json.loads(l) for l in seq.read_text().splitlines()]
ids=[i for r in records for i,m in zip(r['input_ids'],r['attention_mask']) if m]
counts=Counter(ids); runs=Counter(); run=0
for i in ids:
 if i==202:run+=1
 elif run:runs[run]+=1;run=0
if run:runs[run]+=1
out={'newline_count':counts[202],'real_tokens':len(ids),'newline_runs':dict(runs),'block_count':len(records),'checkpoint_results':[]}
with tempfile.TemporaryDirectory() as tmp:
 with zipfile.ZipFile(base/'baseline/bundle.zip') as z:
  for name in z.namelist():
   if name.startswith('checkpoints/') and ('model.safetensors' in name or name.endswith('/config.json') or name.endswith('/generation_config.json')):z.extract(name,tmp)
 for step in [7,14,21]:
  model=GPT2LMHeadModel.from_pretrained(Path(tmp)/f'checkpoints/step-{step:06d}',local_files_only=True,use_safetensors=True,attn_implementation='eager').eval()
  samples=[]
  with torch.inference_mode():
   for p in prompts:
    encoded=tok.encode(p['text'],add_special_tokens=False).ids; inp=torch.tensor([[2]+encoded]);mask=torch.ones_like(inp)
    gen=model.generate(input_ids=inp,attention_mask=mask,max_new_tokens=32,do_sample=False,use_cache=True,pad_token_id=0,bos_token_id=2,eos_token_id=3,suppress_tokens=[0,1,2]); generated=gen[0,inp.shape[1]:].tolist()
    manual=inp; top=[]
    for n in range(32):
     logits=model(input_ids=manual,attention_mask=torch.ones_like(manual),use_cache=False).logits[0,-1].clone();logits[[0,1,2]]=-float('inf');probs=logits.softmax(-1); vals, inds=probs.topk(3);top.append([{'id':int(i),'p':float(v)} for v,i in zip(vals,inds)]); manual=torch.cat([manual,inds[0].reshape(1,1)],dim=1)
    samples.append({'prompt':p['text'],'prompt_ids':inp[0].tolist(),'output_ids':generated,'direct_tokens':[int(x[0]['id']) for x in top],'top3_first4':top[:4],'same_all':generated==[x[0]['id'] for x in top]})
   r=records[-1]; input_ids=torch.tensor([r['input_ids']]); labels=torch.tensor([r['labels']]);mask=torch.tensor([r['attention_mask']]);res=model(input_ids=input_ids,attention_mask=mask,labels=labels,use_cache=False);manual_loss=torch.nn.functional.cross_entropy(res.logits[:,:-1,:].reshape(-1,model.config.vocab_size),labels[:,1:].reshape(-1),ignore_index=-100)
   out['checkpoint_results'].append({'step':step,'samples':samples,'loss':float(res.loss),'manual_loss':float(manual_loss),'loss_abs_delta':float(abs(res.loss-manual_loss))})
Path('/tmp/studio-step9-diagnosis.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({'real_tokens':len(ids),'newline':counts[202],'runs':dict(runs),'steps':[{'step':x['step'],'newline_only':sum(s['output_ids']==[202]*32 for s in x['samples']),'direct_matches':sum(s['same_all'] for s in x['samples']),'loss_delta':x['loss_abs_delta']} for x in out['checkpoint_results']]},ensure_ascii=False,indent=2))
