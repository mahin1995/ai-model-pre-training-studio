# Evaluation and Playground Verification

Verified 16 November 2026 (Asia/Dhaka).

## Delivered

- CPU checkpoint Playground with frozen-tokenizer token budget, bounded greedy completion, raw IDs, saved history and checksum-registered exports.
- Immutable prompt-set versions and comparison of up to four checkpoints from one completed training run.
- All-original-training-block diagnostics, separately reported original smoke-subset loss, nonempty validation scoring and explicit unavailable metrics for empty validation.
- Independent reviewed external-corpus encoding without tokenizer fitting, source/file/document/PDF-group/exact-content overlap checks and provenance-rich reports.
- Revisioned human review notes, separate annotation exports and unsaved-edit navigation guards.
- Migration 007, protected dependencies, shared worker scheduling, native-process cancellation, recovery, compatible-runtime checks and atomic publication.

## Automated verification

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q --tb=short` | **84 passed, 1 skipped** (existing CUDA test) |
| `.venv-training/bin/python -m pytest -q backend/training_tests --tb=short` | **13 passed** |
| `npm test --prefix frontend` | **34 passed** |
| `npm run build --prefix frontend` | TypeScript and production build passed |
| `pip check` in API and training environments | No broken requirements |
| Whitespace / Python compilation | Passed |

API integration uses temporary PostgreSQL/data and real CPU checkpoints. Tests cover deterministic completion, literal-special-token prompt round-trip, full training-block coverage, original smoke-subset metrics, empty and nonempty original validation, external frozen encoding, cross-project and lineage/content rejection, immutable prompt versions, annotation conflicts, ZIP integrity, protected deletion, runtime/checksum failure, queued/native cancellation and interrupted leases. A follow-up run of all seven inference API tests also passed after adding exact cleaned-content overlap coverage.

Numerical tests independently compare the weighted shifted/masked loss with manual cross-entropy, verify padding exclusions and perplexity overflow handling, assert inference never loads optimizer tensor state, confirm unchanged weights/deterministic IDs, reject context overflow, and test recoverable display escaping of generated NUL bytes. Existing smoke numerical tests remain green. An existing Starlette/httpx deprecation warning remains.

## Real browser flow

Headless local Chrome tested the built UI using a reviewed PDF fixture and a separate reviewed external corpus, with a real 200-step CPU model and four checkpoints. Its training export contained **19 blocks**; comparison scored every block and reported the original two-block smoke subset separately.

Passed: generation/token-budget display, context-overflow disabling, ZIP download, prompt-set saving, prompt and review-note navigation guards, four-checkpoint comparison, manual-note save/reload, refresh persistence, external evaluation on three independent documents, unavailable empty-validation metrics, 390px responsive layout without document overflow, and zero JavaScript page errors. Temporary browser server/database/storage were removed afterward.

- [Playground desktop](playground-desktop.png)
- [Evaluation desktop](evaluation-desktop.png)
- [Independent-corpus evaluation](evaluation-independent-desktop.png)
- [Empty-validation mobile state](evaluation-mobile.png)

## Live workspace

Migration **007_evaluation_playground.sql** applied; built UI and API serve on port 8000. Read-only validation confirmed the user's existing checkpoints **50/100/150/200**, **seven original train blocks**, two smoke-subset blocks and no original held-out data. Later read-only observation found a completed live training-diagnostic evaluation covering all seven blocks for each checkpoint, correctly labeled with no held-out metric claim. No model training or source correction was triggered automatically by this implementation.

Existing datasets, tokenizer artifacts, model weights and checkpoints remain intact. New inference records protect their referenced training runs/checkpoints and any external dataset versions from deletion.

## Boundaries

CPU-trained checkpoints and their matching pinned runtime are supported. CUDA remains unverified. Evaluation is **block-based NLL/PPL v1**, not sliding-window corpus perplexity or factual accuracy. Exact overlap checks cannot rule out near-duplicates. Poor/repetitive generation is retained as a model result, not converted into a tool failure or automatic quality pass. Full-dataset training, chat fine-tuning, streaming generation and reserved final-test workflows remain later phases.
