# Step 7 — Whole-dataset Pre-training Pilot

Status: **Implemented and verified on CPU, 17 November 2026.** Real pilot fixtures, exact resume, browser flow and Evaluation/Playground integration pass. The user's live pilot has not been started.

Evidence: [Step 7 verification](artifacts/STEP_7_VERIFICATION.md).

Date: 17 November 2026, Asia/Dhaka.

## 1. Goal and starting point

Smoke test → Evaluation/Playground-er por next step holo selected training export-er **sob block diye bounded pilot training**. Ekhane epoch, real data coverage, reproducible resume ebong usable checkpoint verify korbo.

Last verified live source-e 27 PDF pages, 1,173 vocabulary, 1,024 context ebong seven training blocks chilo. Existing smoke executor maximum first two blocks repeatedly train kore. Evaluation sob seven block score korte pare, kintu scoring weights update kore na. Tai smoke-er steps barano diye whole-dataset training hobe na.

These are historical observations, not hardcoded configuration. Implementation selected immutable source theke counts, vocabulary ebong context derive korbe. Pilot shuru hobe **new random weights** diye; current smoke checkpoint theke silently continue korbe na.

Eta small-corpus learning experiment. Ek PDF theke general-purpose language ability ba reliable rule-answering expect korbo na. Fine-tuning ebong larger-corpus training following phases.

## 2. Data readiness and frozen inputs

Start-er age user ekta reviewed dataset → completed tokenizer → completed sequence export select korbe. Existing eligible chain diye tooling/pilot practice kora jabe; abar upload mandatory na.

- Source preview-te Bangla spelling, table reading order ebong paragraph boundaries review kora uchit. Previously observed `হললো` / `ককোননো`-er moto extraction issues correction tooling diye check korte hobe.
- Correction publish korle new reviewed dataset version → new train-only tokenizer → new sequences → new pilot config lagbe. Old artifacts/checkpoints preserve korbo.
- Usage permission, source manifest, tokenizer checksum, complete document/token coverage ebong sequence arrays verify korbo enqueue ebong execution-er age.
- Vocabulary/context selected artifacts theke read-only; PAD/UNK/BOS/EOS IDs remain 0/1/2/3. Padding, labels and document boundaries preserve korbo.
- Current single PDF train-only thakbe. Page split kore fake validation banabo na. Independent reviewed documents later frozen tokenizer diye Evaluation-e use kora jabe.

Source bodlale existing saved config rewrite hobe na; new immutable config revision create hobe.

## 3. User workflow and configuration

**Model Config → Whole-dataset pilot preset → Save → Pre-training → Preview plan → Start pilot → Coverage/checkpoints → Evaluate/Playground.**

Existing smoke mode accessible thakbe. Pilot selection-er jonno clear separate mode, description ebong history badge thakbe.

| Setting | Initial policy |
| --- | --- |
| Initialization | Random weights only; seed default 42 |
| Architecture | Existing tiny GPT-2 options and 10M-parameter cap |
| Device / precision | CPU / FP32 for this phase |
| Epochs | Default 3; integer 1–20 |
| Data | All selected train blocks, maximum 256 |
| Updates | `train block count × epochs`; maximum 2,000 |
| Batch / accumulation | 1 / 1 |
| Optimizer | AdamW, default LR 0.0003, weight decay 0 |
| Schedule / clipping | Constant LR, no warmup, gradient clipping 1.0 |
| Order | Deterministic seeded permutation per epoch |
| Checkpoints | Up to four completed-epoch boundaries, including final |
| Runtime / artifacts | At most 900 seconds and 1 GiB total per run |

Defaults are an initial engineering baseline, not tuned hyperparameters. Seven blocks × three epochs = **21 optimizer steps**; seven blocks × ten epochs = **70 steps**. One epoch means each training block is processed once. Requested total steps are derived, not an independent field that can silently cut an epoch short.

Preview shows frozen version IDs, block/document counts, unique supervised targets per epoch, requested epochs/steps, checkpoint steps and estimated storage. Reject over-limit settings clearly; do not silently sample blocks, cap epochs or discard text. Time estimate appears only after measured pilot throughput exists and is labeled approximate.

CPU keeps this compatible with currently verified inference. CUDA/mixed precision, larger batches, gradient accumulation and warmup schedules are deferred rather than partially enabled here.

## 4. Training loop, coverage and metrics

1. Generalize source inspection to expose verified full training records as well as the existing smoke subset. Preserve legacy callers and contracts.
2. Freeze stable block identities/order and their checksum in the run snapshot. Store document IDs, ordinal and token range; never mix validation/test into the loader.
3. Generate each epoch's permutation from the saved seed and epoch using a dedicated RNG. Record the algorithm version, actual permutation, next offset and supported runtime for exact resume.
4. Process every block exactly once per completed epoch. Keep tails and padding masks; no `drop_last`, replacement sampling or two-block selection in pilot mode.
5. Preserve unshifted labels with padding `-100`; GPT-2 performs the causal shift internally. Count actual supervised targets from `labels[1:] != -100`, not padded context length. See [GPT-2 loss contract](https://huggingface.co/docs/transformers/v4.57.1/en/model_doc/gpt2).
6. Track real step loss, finite gradient norm, step time, supervised targets/second and CPU RSS. Show completed epochs, current offset, unique blocks visited and cumulative target exposures separately.
7. Compute token-weighted initial/final all-train diagnostics with weights frozen; optional epoch-end diagnostics use the same protocol. Keep these separate from online training loss and exclude evaluation targets from training throughput/coverage.

Coverage includes all real exported tokens, but the first position of each independent block has no causal target. Report that boundary policy explicitly. Repeated epochs increase exposures, not unique corpus size. Reuse the existing block-based NLL/PPL protocol; [perplexity depends on tokenization and context policy](https://huggingface.co/docs/transformers/perplexity).

Completion requires all requested updates, exact epoch coverage, finite results and verified final checkpoint. Lower training loss is informative, not a required 5% quality pass. Do not reuse the smoke verdict for general model quality. Interrupted runs report partial coverage and their actual terminal state.

## 5. Checkpoints, recovery and resource limits

- Choose at most four evenly spaced completed-epoch boundaries before starting: `ceil(k × epochs / min(epochs, 4))`, for `k = 1..min(epochs, 4)`. Convert each to an optimizer step; always include final. No automatic checkpoint deletion in this phase.
- Estimate weights, optimizer state, checkpoint ZIPs, final bundle copies and staging overhead before enqueue. Require existing 2 GiB available RAM / 5 GiB free disk gates and enforce the per-run artifact/time caps during execution. Reject configurations whose conservative storage estimate exceeds budget.
- Checkpoints contain model weights, optimizer, fixed schedule, configuration/source hashes, RNG states, global step, completed epoch, actual order, next offset and coverage counters. [PyTorch's resume guidance](https://docs.pytorch.org/tutorials/beginner/saving_loading_models.html) explains why optimizer state accompanies model state.
- Version checkpoint metadata. Preserve support for existing smoke checkpoints; a legacy subset cursor cannot be interpreted as a pilot cursor.
- Fresh-process reload verifies matching logits/loss and bounded generation. Numerical tests compare interrupted/resumed and uninterrupted CPU training, including an epoch boundary.
- Resume creates a linked child from a registered verified intermediate **pilot** checkpoint under identical configuration, data, runtime and remaining original budget. Failed/cancelled parents may supply an intact published checkpoint. Restore counters without double-counting parent updates.
- A final checkpoint already at the configured total has no remaining work. Extending epochs, changing LR/source or initializing from smoke weights is a future explicit warm-start feature.
- Cancellation/restart preserves already published checkpoints, removes temporary files and marks the job interrupted/failed as appropriate. No automatic training rerun. Retry means a new from-scratch run; resume is a distinct action.

## 6. Persistence, API and worker integration

Use the next migration, expected **008_whole_dataset_pilot.sql**; do not rewrite applied migrations.

- Add a training-kind discriminator to existing `model_configs` and `smoke_runs`, defaulting existing rows to `smoke`. Keep existing run/checkpoint foreign keys so inference/deletion references remain valid; the historical table name is internal.
- Add a discriminated pilot-settings schema with epochs and derived maxSteps/checkpoint schedule. Keep old smoke config requests/responses valid. Mode-specific endpoints reject mismatched configs.
- Store configuration, full-source snapshot, initialization policy and coverage protocol immutably. Keep metrics/checkpoints in the shared storage infrastructure with mode-aware serialization.
- Reuse the single advisory-lock worker and credential-free `.venv-training` subprocess. Preparation, inference, smoke and pilot must not run concurrently. API runtime remains Torch-free.
- Reuse cancellation, heartbeat, lease recovery, checksum-only registered downloads, project isolation and dependency-protected deletion. Generalize shared helpers only where needed.

Proposed pilot routes under `/api/projects/{project_id}`:

- `POST /pilot-preview`: validate saved config and return complete execution/storage plan without training.
- `POST /pilot-runs`: enqueue an immutable pilot config.
- `GET /pilot-runs` and `GET /pilot-runs/{id}`: status, progress, metrics and checkpoints.
- `POST /pilot-runs/{id}/cancel`, `/retry`, `/resume`: explicit lifecycle actions.
- Download routes for bundle/report/metrics/manifest and registered checkpoints; guarded run deletion.

Saving a config or requesting a preview must never enqueue training. An accepted Start pilot request is sufficient authorization to execute that run; no extra confirmation dialog is required.

## 7. UI, Evaluation and exports

Model Config adds the pilot preset, epoch input and derived plan. Pre-training adds separate smoke/pilot controls, honest loading/error states, epoch/block coverage, metrics, checkpoint downloads, refresh recovery and retry/resume actions. Preserve keyboard/mobile usability and unsaved-edit protection.

Completed pilot checkpoints must be selectable in the **existing** Evaluation and Playground workflows. Update source eligibility/report parsing and replace smoke-specific text conditionally. In particular, `subsetRecords = first two blocks` must not be described as the pilot's trained subset: pilot training uses the full export. Existing smoke reports keep their original two-block semantics.

Compare checkpoints from one run with identical tokenizer/prompts/data/protocol. Initial version does not add automatic cross-run ranking. Final checkpoint is a convenience default, not a claim that it is best.

After completion, show links to Evaluation and Playground; do not launch new jobs automatically. All-train loss stays a training diagnostic. Empty validation shows **Not available**. Independent external evaluation reuses frozen-tokenizer/overlap checks; no tokenizer refitting or test-set tuning.

Bundle includes tokenizer/special-token configuration, model config/weights, registered checkpoints and resume state, source/checksum manifests, coverage report, JSONL metrics, diagnostics, runtime and short usage notes. Original PDF/data/checkpoints remain unchanged; downloads use registered artifact names.

## 8. Implementation order and acceptance

1. **Contracts + migration:** mode-specific configs, derived preview, immutable snapshots, old-row compatibility and limits.
2. **Executor:** all-block loading, deterministic epochs, accurate coverage/target metrics, bounded artifacts and versioned checkpoint/resume.
3. **Jobs/API:** shared queue, cancel/restart/retry/resume and protected artifacts/dependencies.
4. **UI + inference compatibility:** pilot config/run/history, correct metric labels, Evaluation/Playground eligibility and exports.
5. **Verification/docs:** temporary PostgreSQL/data fixtures, real CPU runs, browser checks and completion evidence.

Acceptance checks:

- Use a fixture with **more than two blocks** and a padded tail. Every block appears exactly once per epoch; three epochs produce `3 × N` updates and exact target counts. No validation/test exposure.
- Verify seeded order, source/tokenizer checksums, single causal shift, target-weighted diagnostics and legacy smoke behavior.
- Verify uninterrupted versus linked-resume weights/optimizer/order/counters under the same CPU runtime, fresh-process reload and generation.
- Verify corruption, foreign-project IDs, config/source/runtime mismatch, resource rejection, native cancellation, worker restart and dependency deletion.
- Run completed pilot checkpoints through Playground and all-train/external Evaluation; preserve empty-validation behavior and old smoke report semantics.
- Browser workflow: save → preview → start → epoch/coverage → checkpoint/bundle download → Evaluation/Playground; refresh, keyboard and mobile checks.
- Run backend pytest with `--tb=short`, isolated training-runtime numerical tests, frontend Vitest, production build and dependency checks. Record results before marking implementation complete.

Tests may train isolated fixtures. Implementation must not automatically train the user's live corpus. A live pilot begins only through the user's explicit Start action or a separate instruction to run it.

## 9. Decision after the pilot

Check full coverage, stability, reload/resume, generated samples and measured time/storage. Correct extraction issues or add independent documents where needed. Only then plan larger data/model budgets, optional verified CUDA execution, validation-based checkpoint selection and eventually instruction fine-tuning.

Related: [Step 6](STEP_6_EVALUATION_PLAYGROUND_PLAN.md), [smoke plan](STEP_5_MODEL_SMOKE_TEST_PLAN.md), [remaining roadmap](REMAINING_WORK_PLAN.md).
