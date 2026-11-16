# Model-training Smoke Test Plan

Status: **Implemented; CPU training, checkpoint reload/resume and browser workflow verified on isolated fixtures (15 November 2026).** CUDA setup/profile is supported, but CUDA execution remains unverified after dependency-download timeouts. The live corpus has not been trained by this implementation task.

Evidence and operational limits: [Step 5 verification](artifacts/STEP_5_VERIFICATION.md).

## 1. Goal and current state

Saved tokenizer ও sequence bundle ব্যবহার করে একটি ছোট, random-weight causal language model initialize, train, save, reload ও resume করব। উদ্দেশ্য training pipeline কাজ করে কি না যাচাই করা; language quality বা pilot-rule accuracy প্রমাণ করা নয়।

Repository inspection, 15 November 2026:

- Datasets এবং Tokenizer workflow functional। Model Config এবং Pre-training sidebar entries এখনো placeholders; এগুলো implement করতে হবে।
- Reviewed Version 3-এর tokenizer completed: actual vocabulary **1,173**, content tokens **6,659**। Completed sequence run: **7 × 1,024 positions**, **507 padding positions**। এগুলো বর্তমান observed values, configuration-এ hardcode করব না।
- Corpus-এর কিছু বাংলা বানান, যেমন `হললো` ও `ককোননো`, review করা প্রয়োজন। সংশোধন করলে নতুন reviewed version → tokenizer → sequences তৈরি করতে হবে। পুরোনো artifacts overwrite করব না। এই সমস্যা numerical smoke test আটকায় না, কিন্তু corrected source ব্যবহার করাই preferred।
- Backend Python **3.14.4**; `torch`, `transformers`, `safetensors` installed নেই। NVIDIA driver RTX 3060 / **12 GiB** report করছে; usable CUDA training এখনো verified নয়। Project Setup-এর manually entered capacity দিয়ে training readiness নির্ধারণ করব না।

এই কাজ roadmap-এর M5 config, M6 job infrastructure, bounded M8 runtime setup এবং M9 smoke executor-এর প্রয়োজনীয় অংশ একসঙ্গে যুক্ত করবে। Full-corpus preparation, full pre-training, evaluation suite ও fine-tuning বাকি থাকবে।

## 2. User workflow

**Model Config → Select completed sequences → Save configuration → Pre-training / Smoke test → Inspect results → Download checkpoint**

### Model Config

- Completed, same-project sequence run নির্বাচন করলে তার fixed dataset version, tokenizer, actual vocabulary, sequence length এবং special IDs দেখাবে। Default newest eligible completed sequence run; user অন্য eligible run বেছে নিতে পারবে।
- Source-derived fields read-only। অন্য tokenizer/sequence বাছলে নতুন configuration revision save করতে হবে।
- Model ও training settings একই form-এ থাকবে; save-এর সময় backend validation হবে। Unsaved edits নিয়ে navigation/project switch করলে existing draft-protection pattern অনুসরণ করবে।
- Saved immutable revision, settings export, estimated parameter count ও source lineage দেখা যাবে। Estimate এবং model instantiate করার পরে measured count আলাদা label হবে।

### Pre-training: Smoke test

- Saved config, selected subset, device, max steps ও time limit দেখিয়ে **Run smoke test**। Missing runtime হলে actionable setup state; config save তখনও সম্ভব।
- Run history, real optimizer step / requested steps, elapsed time, measured loss, supervised tokens/sec এবং device memory দেখাবে। Preparation stages-এ indeterminate status থাকবে।
- Cancel, retry-from-scratch এবং separate **Resume verification** action থাকবে। Retry/resume নতুন run বানাবে; original result বদলাবে না।
- Result-এ technical checks, diagnostic loss comparison, generated sample ও registered downloads থাকবে। Validation/test খালি থাকলে train-only diagnostic লেখা থাকবে।

## 3. First model and defaults

Use Hugging Face **GPT2Config + GPT2LMHeadModel(config)** with random weights। Pretrained weights/tokenizer download করব না। Established implementation ব্যবহার করলে প্রথম milestone-এ custom attention/loss implementation যাচাই করার বাড়তি কাজ কমবে।

| Setting | Smoke-test default / rule |
| --- | --- |
| Architecture | Small GPT-2-style decoder-only causal LM |
| Vocabulary | Saved tokenizer-এর actual size; currently 1,173 |
| Layers / hidden size / heads | 2 / 128 / 4 |
| Feed-forward size | 4 × hidden size |
| Context length | Selected sequence length; currently 1,024 |
| Special IDs | Read and verify PAD 0, UNK 1, BOS 2, EOS 3 |
| Dropout | 0 for repeatable diagnostic |
| Precision | FP32 |
| Device | Auto selects CUDA only after successful training-runtime probe; explicit CPU available |
| Optimizer | AdamW, learning rate 0.0003, weight decay 0 |
| Scheduler / warmup | Constant learning rate / 0 steps |
| Micro-batch / accumulation | 1 / 1 |
| Gradient clipping | Global norm 1.0; inspect finiteness before clipping |
| Optimizer steps | 200; configurable 50–500 |
| Training subset | First min(2, available train sequences), stable file order, cycle repeatedly |
| Seed | 42; record seeds, device and library versions |
| Checkpoints | Every 50 optimizer steps and final; retain all within run limits |
| Generation | One saved prompt, greedy, at most 32 new tokens, stop on EOS |

Current vocabulary/context দিয়ে preset approximately **0.68 million parameters**; real count initialization-এর পরে record হবে। Config edits প্রথম version-এ bounded: layers 2/4, hidden size 64/128/256, heads 2/4/8, hidden size divisible by heads, maximum 10 million parameters। Arbitrary custom architectures ও mixed precision পরে।

Context নির্বাচিত sequences-এর length-এর সমান হবে। Smaller context চাইলে ছোট-length sequence run আগে generate করতে হবে; trainer silently truncate/repack করবে না।

## 4. Runtime setup and readiness

- Heavy training dependencies API startup বা normal launcher-এ auto-install হবে না। Explicit setup script দিয়ে project-local **`.venv-training`** তৈরি করব। Existing backend `.venv` ও pinned tokenizer dependencies অক্ষত থাকবে।
- Available supported Python interpreter ও binary wheels যাচাই করে stable PyTorch/Transformers/safetensors versions select এবং separate runtime requirements-এ pin করব। Prefer Python 3.12/3.13 when available; Python 3.14-ও কেবল complete compatible wheel set verified হলে ব্যবহার হবে। Unsupported runtime হলে clear setup action; source compilation নয়।
- CPU এবং CUDA install profiles আলাদা; official PyTorch wheel source ব্যবহার হবে। Runtime-এ `tokenizers==0.22.2` ও exported tokenizer contract রাখতে হবে; Transformers dependency resolver conflict হলে compatible version select করব, API environment upgrade নয়।
- Training subprocess-এর interpreter server-controlled configuration, যেমন `STUDIO_TRAINING_PYTHON`; browser request কোনো executable path দিতে পারবে না।
- Environment UI-তে **Backend runtime** এবং **Training runtime** scope আলাদা দেখাবে। Existing backend-only PyTorch warning-কে training runtime failure হিসেবে দেখাবে না। Minimal executor-এ `datasets`, `accelerate`, `peft` required নয়।
- Probe verifies imports, versions, CPU or CUDA allocation এবং tiny forward/backward। CUDA fail হলে selected GPU run fail/readiness-blocked; silently CPU-তে training চালাবে না। User explicit CPU run বেছে নিতে পারবে।
- Start preflight: at least 2 GiB available RAM, 5 GiB free artifact disk; maximum 15 minutes per run এবং 1 GiB published artifacts। Parameter count × optimizer/model-state size × checkpoint count দিয়ে conservative storage estimate করব; cap ছাড়ালে run শুরু হওয়ার আগেই settings change চাইবে। এগুলো bounded diagnostic limits, model-fit guarantee নয়। Probe deadline 60 seconds; timeout/failure readable হবে।

## 5. Data and loss contract

1. Require completed sequence/tokenizer runs, same project, reviewed source, current source permission এবং nonempty training split। Immutable config references both run IDs and original dataset-version ID।
2. Verify source manifests, tokenizer vocabulary/special IDs এবং artifact sizes/checksums at submission and execution। Existing document/split isolation ও limits retain করব।
3. Validate all selected records: equal fixed-length arrays, in-range IDs, binary right-padding mask, PAD positions, labels equal real IDs / `-100` on padding, at least two real tokens।
4. Pass saved `input_ids`, `attention_mask`, `labels` directly to model। **Dataset labels unshifted থাকবে; GPT2LMHeadModel shifts once internally।** Training loop আবার shift করবে না। Padding loss-এ ignored থাকবে।
5. Train শুধু selected train subset-এ। Validation/test থাকলেও model updates বা diagnostic subset-এ ব্যবহার করব না; full held-out evaluation এই phase-এর বাইরে।
6. Before/after fixed-subset loss `model.eval()` এবং no-grad mode-এ compute হবে, actual next-token targets দিয়ে weighted average হবে। Diagnostic চলাকালে subset/order/settings বদলাবে না।
7. প্রতিটি step-এ finite loss ও gradients check; optimizer updates সত্যি weights বদলেছে কি না verify। Nonfinite values, OOM, invalid data বা budget expiry হলে actionable failure; fake metrics নয়।

Separate blocks reset context; block boundary-র cross-block next-token relationship এই exported format-এ শেখানো হয় না। Smoke test existing sequence contract বজায় রাখবে।

## 6. Job lifecycle, persistence and artifacts

- New migrations **005_model_configs.sql** এবং **006_smoke_runs.sql**; prior migrations unchanged। Config revisions immutable; smoke_runs and checkpoints record lineage, status, metrics, hashes, runtime snapshot and timestamps। Foreign keys/deletion checks protect referenced datasets, tokenizer/sequence runs, configs and checkpoints।
- Extend existing single-worker advisory-lock scheduling: dataset, tokenizer, sequence এবং smoke jobs একসঙ্গে execute হবে না। Do not create an independent GPU worker that bypasses the lock।
- States: queued → validating → initializing → training → verifying → completed; failed/cancelled terminal states। Verdict আলাদা: passed / needs-attention / failed।
- Credential-free, offline training subprocess; API/database parent owns metadata, cancellation and heartbeat। Torch imports only in training runtime; API remains usable without it। Metrics read via bounded JSONL events, not database access from child।
- Parent polls cancellation/timeout even while a native training operation runs; terminate process group, then bounded kill fallback। Server restart expires interrupted leases as failed; no automatic model resume।
- Each checkpoint atomically published and registered only after checksum verification। Parent can preserve verified checkpoints from cancelled/failed runs; partial writes/staging never downloadable। Final report/bundle publication is atomic; protect cancellation/commit races like existing preparation jobs।
- Downloads use registered artifact IDs with project isolation and hash checks; no arbitrary file paths or uploaded Python/pickle checkpoints। Existing source artifacts remain untouched।

Downloads: model config, tokenizer files, model weights, optimizer/training state, metrics JSONL, diagnostic report, generated sample and lineage/runtime manifest; complete ZIP where within cap। Store model via safetensors; store primitive/tensor-only optimizer/RNG state using restricted `torch.load(..., weights_only=True)` and CPU map location। Keep tied weights handling compatible with `save_pretrained(..., safe_serialization=True)`।

Proposed API contract, under `/api/projects/{project_id}`:

- `GET/POST /model-configs`, `GET /model-configs/{id}`, `GET /model-configs/{id}/export` for immutable revisions।
- `GET /training-runtime` for server-configured interpreter/readiness; no request-supplied executable।
- `GET/POST /smoke-runs`, `GET /smoke-runs/{id}`, `GET /smoke-runs/{id}/metrics?afterStep=...` for bounded incremental polling।
- `POST /smoke-runs/{id}/cancel`, `/retry`, `/resume` and `GET /smoke-runs/{id}/download?artifact=...` for lifecycle/registered artifacts।
- `DELETE` config/run only when terminal and unreferenced; checkpoints needed by resumed child runs cannot be removed।

## 7. Checkpoint reload and resume verification

- Save model, optimizer, global step, schedule definition, CPU/CUDA RNG states, seed, subset cursor and source/config hashes। Checkpoint contract includes exact runtime versions।
- Reload final checkpoint into a fresh model/process। Same fixed input in eval mode must yield matching logits/loss within documented device-specific tolerance। Confirm in-range generated IDs and bounded termination; readable language is not a pass requirement।
- Manual **Resume verification** accepts a registered intermediate checkpoint from a completed compatible smoke run, creates a child run, and continues from its saved optimizer step to the original configured total。 No source/config edits during resume; runtime/device mismatch blocks exact resume and requests a new smoke run।
- CPU regression test compares uninterrupted training with checkpoint+resume using same batches/seeds, optimizer state and next-step behavior। On CUDA use explicit tolerances; never promise reproducibility across releases/hardware।
- Generation uses saved tokenizer's literal-special-token policy, inserts BOS once, and rejects prompts that leave fewer than 32 context positions; no silent prompt truncation। Arbitrary generated byte sequences can decode poorly; preserve token IDs in the report and do not interpret this as extraction corruption।

## 8. Success criteria

| Check | Required evidence |
| --- | --- |
| Model/data compatibility | Actual vocabulary, context and special IDs match immutable sources |
| Real training | Finite loss/gradients, changed weights, requested optimizer steps completed |
| Tiny-subset learnability | Same fixed-subset final eval loss at least 5% below initial loss |
| Checkpoint | Save, independent reload, matching outputs and resumed optimizer update |
| Observability | Actual step time, target tokens/sec, CPU RSS and CUDA peak allocated/reserved memory when applicable |
| Safety of existing data | Source hashes unchanged; no tokenizer fitting or text mutation during training |

The 5% decrease is a diagnostic acceptance target, not a guarantee. Completed computation with insufficient decrease shows **needs-attention**, not a false pass; preserve metrics to investigate settings/data। Individual training-step loss need not decrease monotonically। Empty held-out splits mean no validation loss, validation perplexity or generalization claim।

## 9. Implementation order and verification

1. **Config API/UI:** schemas, immutable revisions, source selection, validation, export and draft protection; feature usable without Torch।
2. **Runtime:** explicit setup/requirements, interpreter validation, readiness probe and scoped Environment UI।
3. **CPU executor:** tiny model, strict sequence loader, fixed-subset loss, training metrics and bounded subprocess।
4. **Jobs/UI:** persisted runs, polling, cancellation, recovery, downloads and dependency protection।
5. **Checkpoint/generation:** atomic intermediate/final saves, fresh-process reload, resume verification and bounded sample।
6. **Verification:** isolated CPU integration/browser tests, then real CUDA probe/small smoke run when available; record measured results and only then update milestone status।

Expected code locations: `backend/app/models/`, `backend/app/training/`, new migrations/tests; frontend `ModelConfig.tsx`, `PreTraining.tsx`, scoped services/types, existing Environment and App integration। Keep training numerical code runnable under `.venv-training` independently of API dependencies।

Tests cover cross-project references, incompatible versions/context, corrupt artifacts, wrong labels/double-shift prevention, pad-loss masking, nonfinite gradients, missing runtime, CUDA errors, OOM, time/disk limits, queued/running cancellation, restart recovery, protected deletion, checkpoint integrity/reload/resume and unchanged inputs। Numerical tests run explicitly in pinned training runtime; missing runtime must not silently count as a passed training test। Backend API tests use temporary PostgreSQL only।

Browser acceptance: select actual-vocabulary source → save/reload config → run → real metrics → checkpoint download → refresh history → resume verification; empty/error/cancel states and responsive keyboard-accessible controls। Run existing pytest, Vitest, production build and separate training-runtime tests; capture verification report with runtime versions and actual counts। No model-quality assertion for the small one-PDF corpus।

## 10. References and deferred work

- [Hugging Face GPT-2 model/configuration and causal labels](https://huggingface.co/docs/transformers/model_doc/gpt2)
- [Transformers runtime installation](https://huggingface.co/docs/transformers/installation)
- [Official PyTorch platform-specific installation](https://pytorch.org/get-started/locally/)
- [PyTorch restricted checkpoint loading](https://docs.pytorch.org/docs/stable/generated/torch.load.html)
- [PyTorch reproducibility limits](https://docs.pytorch.org/docs/stable/notes/randomness.html)

Deferred: large/full-corpus runs, pretrained-model fine-tuning, SFT/LoRA, mixed precision, multi-GPU/distributed execution, chat interfaces, full evaluation, inference serving and cloud deployment। Successful smoke test is the gate before planning larger training resources and quality evaluation।
