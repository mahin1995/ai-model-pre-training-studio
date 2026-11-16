"""Executed only by the isolated training interpreter; no API/DB imports."""
import importlib.metadata
import json
import platform


def main():
    import torch
    from transformers import GPT2Config, GPT2LMHeadModel
    versions = {name: importlib.metadata.version(name) for name in ('torch', 'transformers', 'tokenizers', 'safetensors')}
    versions['python'] = platform.python_version()
    if versions['tokenizers'] != '0.22.2':
        raise RuntimeError('Tokenizer version mismatch')
    torch.set_num_threads(2)

    def run(device):
        model = GPT2LMHeadModel(GPT2Config(vocab_size=260, n_positions=8, n_embd=16, n_layer=1,
                                          n_head=2, resid_pdrop=0, embd_pdrop=0, attn_pdrop=0)).to(device)
        ids = torch.tensor([[2, 5, 7, 3]], device=device)
        loss = model(input_ids=ids, labels=ids, use_cache=False).loss
        loss.backward()
        if not torch.isfinite(loss) or any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
            raise RuntimeError('Nonfinite probe')
    run('cpu')
    result = {'ready': True, 'cpu': True, 'cuda': False, 'cudaError': None, 'versions': versions,
              'message': 'CPU forward/backward passed.', 'deviceName': 'CPU'}
    if torch.cuda.is_available():
        try:
            run('cuda')
            torch.cuda.synchronize()
            result.update(cuda=True, deviceName=torch.cuda.get_device_name(0), message='CPU and CUDA forward/backward passed.')
        except Exception:
            result['cudaError'] = 'CUDA execution failed; CPU remains available when selected explicitly.'
    print(json.dumps(result))


if __name__ == '__main__':
    main()
