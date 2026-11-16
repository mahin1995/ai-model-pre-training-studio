# Model Configuration and Smoke Training Verification

Verified 15 November 2026 (Asia/Dhaka).

## Delivered

- Immutable project-scoped model configurations, source-derived actual vocabulary/context/special IDs, bounded settings and exports; new migrations 005/006.
- Isolated training interpreter/setup, scoped Environment/runtime panel, real CPU/CUDA readiness probe, single-worker queued executor with cancellation/recovery.
- Random-weight GPT-2-style FP32 training on up to two fixed train blocks, real metrics, finite-gradient/weight-change checks and same-subset loss comparison.
- Atomic registered checkpoints with full training configuration/schedule/subset cursor, safetensors weights, restricted tensor/optimizer loading, fresh-process reload/generation, linked exact-state resume, checked downloads and dependency-protected deletion.
- Responsive Model Config and Pre-training pages, draft-navigation protection, history, loss chart, reports and bundles.

## Automated checks

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q --tb=short` | **77 passed, 1 skipped** (CUDA unavailable) |
| `.venv-training/bin/python -m pytest -q backend/training_tests --tb=short` | **10 passed** |
| `npm test --prefix frontend` | **30 passed** |
| `npm run build --prefix frontend` | TypeScript and Vite production build passed |
| `pip check` in both environments | No broken requirements |
| `git diff --check` | Passed |

Numerical tests verify one causal shift, ignored padding targets, invalid sequence rejection, finite-gradient protection, changed weights/lower loss, checkpoint integrity and bitwise-matching CPU parameters after uninterrupted versus resumed training. Executor/API tests cover actual training/reload/resume/downloads plus missing runtime, CUDA failure gating, resource errors, timeout, running-child cancellation, recovery, project isolation and source protection. An existing Starlette/httpx deprecation warning remains.

## Runtime and browser evidence

Verified runtime: Python **3.14.4**, Torch **2.11.0+cpu**, Transformers **4.57.6**, Tokenizers **0.22.2**, safetensors **0.8.0**. API requirements remain unchanged; training dependencies live in ignored `.venv-training` with their own pins. Official-wheel downloads encountered timeouts; SHA-256-verified wheels were cached and the explicit installer completed using `--wheelhouse ... --offline`.

Local Chrome exercised the built UI on an isolated temporary PostgreSQL database and reviewed generated PDF fixture: source selection, config save, unsaved-edit navigation guard, CPU runtime check, 100 real steps, loss chart, bundle download, checkpoint reload, resume from step 50 to 100, parent-deletion protection, refresh persistence and 390px mobile layout. No JavaScript page errors or horizontal overflow. Temporary server/database/storage were removed afterward.

The 125,248-parameter fixture model's same-subset loss went from **5.4802885 to 1.7518909** (about **68.0% lower**). Its resumed final loss matched uninterrupted training within the asserted CPU tolerance. These are diagnostic training-subset results, not validation/generalization or language-quality measurements.

- [Model Config desktop](model-config-desktop.png)
- [Training desktop](smoke-training-desktop.png)
- [Training mobile](smoke-training-mobile.png)

## Live workspace and limits

The local Python server serves the built UI/API on port 8000. Migrations 005/006 applied. Read-only source validation confirmed the user's existing artifacts: **1,173 vocabulary, 1,024 context, 7 available train blocks, 2 selected diagnostic blocks**. The live dataset/tokenizer/sequence remain intact; no live model configuration or training run was created automatically.

CUDA remains **unverified**: the RTX 3060 driver is visible, but CUDA dependency downloads timed out and the installed training profile is CPU. The GPU test was explicitly skipped, not counted as a pass. Install `--profile cu128` and rerun runtime/training checks before claiming GPU execution.

This implements the bounded smoke phase. Full-corpus training, held-out evaluation, fine-tuning, distributed/mixed-precision execution and cloud deployment remain outside this change. Model size/context/device changes require their own measured smoke run. Checkpoint hashes reside in the registered artifact index; a manifest/bundle does not contain its own hash.
