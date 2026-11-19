# Step 7 — Whole-dataset Pilot Verification

Verified: **17 November 2026, Asia/Dhaka**. CPU/FP32 only.

## Delivered behavior

- Immutable pilot configs select reviewed dataset/tokenizer/sequences and derive updates from epochs × all train blocks. Existing smoke configs, requests, checkpoints and results remain supported.
- Migration `008_whole_dataset_pilot.sql` adds mode discriminators to existing config/run tables. Shared checkpoint and inference foreign keys remain intact.
- Every completed epoch visits every block exactly once in a deterministic seeded permutation. Reports distinguish unique blocks, completed epochs, offset, block exposures and supervised target exposures. Padding and unpredicted block-first tokens do not contribute targets.
- Initial/final diagnostic loss is token weighted over all training blocks. Pilot completion checks coverage, finite gradients, changed weights and fresh-process reload without claiming a language-quality pass.
- Versioned pilot checkpoints retain weights, optimizer, RNG, actual order, cursor, coverage counters and source/config/runtime identity. Retry starts fresh; linked resume restores the remaining original budget, including from intact published checkpoints of failed/cancelled parents.
- Preview, queue/status/history, cancellation, restart recovery, metrics, protected downloads/deletion, epoch UI, Evaluation and Playground integration are functional.

## Automated checks

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q --tb=short` | **89 passed, 1 skipped** |
| `.venv-training/bin/python -m pytest backend/training_tests -q --tb=short` | **15 passed** |
| `npm test --prefix frontend` | **36 passed** |
| `npm run build --prefix frontend` | TypeScript + production build passed |
| `pip check`, API and training interpreters | No broken requirements |
| Python compile and Git whitespace checks | Passed |

Total: **140 passing tests**. The existing CUDA execution test is skipped because that runtime is unavailable; GPU execution is not marked verified.

New `test_pilot_api.py` exercises real CPU training on more than two blocks, derived plans/limits, mode/project isolation, exact epoch coverage, checkpoint/bundle integrity, reload/resume, failed-parent recovery, corruption/runtime mismatch, queued/native cancellation, native timeout, restart recovery and source/dependency protection. Pilot checkpoints also run through real generation, all-train scoring, empty-validation scoring and independent external-corpus scoring with the frozen tokenizer. The expanded external-evaluation integration case passed separately after the full-suite run. After adding the final publication deadline/cancellation check, pilot and smoke training integrations were rechecked: six passed, the same CUDA case skipped.

New standalone numerical tests verify deterministic permutations, padded-tail supervised counts and partial coverage, and compare uninterrupted versus interrupted/resumed model **and optimizer** tensors exactly on CPU. Existing causal-shift/padding/nonfinite-gradient, smoke-resume and inference numerical tests also pass.

## Browser workflow

Real headless Chrome tested the production build served by one FastAPI server on an isolated port, temporary PostgreSQL database and temporary artifacts. All temporary jobs train generated fixtures; the harness removes its database/data/server afterward.

- Model Config → pilot mode → reviewed sequences → three epochs → save immutable config; unsaved navigation guard checked.
- Preview showed **19 train blocks**, **one document**, **2,387 supervised targets per epoch**, **57 updates**, checkpoints **19/38/57** and conservative storage estimate. Preview created no run.
- Runtime probe → Start pilot → all **19/19** blocks visited, **3/3** epochs, **7,161** cumulative target exposures, finite training and matching fresh-process reload.
- Training bundle download succeeded. Browser refresh restored history/report.
- Resume from epoch-one checkpoint completed the remaining 38 updates with the same final loss as uninterrupted training.
- Completed pilot checkpoints generated Playground continuations and ran multi-checkpoint Evaluation with all 19 original training blocks. The table uses **Original full-train loss** for pilots.
- Forward/reverse keyboard navigation through the pilot epoch field was checked on the live form without saving. Desktop and 390-pixel mobile views inspected; no horizontal page overflow or uncaught JavaScript errors.

Fixture losses illustrate execution, not production model quality. Live user data was not submitted for pilot training.

Screenshots:

- [Pilot configuration](pilot-config-desktop.png)
- [Pilot progress and result](pilot-training-desktop.png)
- [Pilot checkpoint evaluation](pilot-evaluation-desktop.png)
- [Mobile training view](pilot-training-mobile.png)

## Live integration and boundaries

The local server was restarted after checking that no preparation/training/inference jobs were active. Migration 008 applied and the built UI/API are served at `http://127.0.0.1:8000`. Existing dataset/version/tokenizer/sequence/config/training/checkpoint/inference metadata digests were unchanged across restart when excluding the new default mode columns. No live pilot run was created.

Limits: CPU/FP32, 1–256 blocks, 1–20 epochs, at most 2,000 updates, four epoch-boundary checkpoints, 15 minutes and 1 GiB per run. Larger data/model budgets, GPU pilots, mixed precision, warm starts and extending an existing epoch budget remain separate work. Small-corpus training loss is diagnostic; empty held-out splits stay unavailable and independent evaluation remains explicit.
