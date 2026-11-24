# Pre-training Studio — Progress ebong Remaining Work

Updated: 2026-11-20 (Asia/Dhaka)

## 1. Agreed working order

Age app-er UI, configuration, PostgreSQL metadata ebong choto sample diye testable backend features complete korbo. GPU-dependent installation, full dataset processing ebong actual model training shesher execution phase-e rakhbo.

Dataset import, preview, basic cleaning, exact deduplication ebong document-level split-er jonno PyTorch lagbe na. Tokenizer-er small-sample test-o PyTorch chara kora jay. Boro dataset processing/tokenizer training CPU, RAM ebong disk-er upor heavy hote pare; tai prothome bounded sample use korbo.

**Latest delivered: bounded whole-dataset pilot training.** Step 7 adds all-block epochs, coverage, immutable pilot configs, exact resume and CPU checkpoint integration with Evaluation/Playground. See `STEP_7_WHOLE_DATASET_PILOT_PLAN.md` and `artifacts/STEP_7_VERIFICATION.md`. Read-only inspection on 19 November confirms a completed live seven-block, three-epoch pilot and a matched linked resume; scaling and fine-tuning remain later phases. Step 8 baseline execution is now recorded in `artifacts/STEP_8_EVALUATION_REVIEW.md`; external Markdown evaluation has now completed on two documents; human/domain review remains pending.

Previous phase: **M7 bounded Evaluation and Playground.** Saved CPU checkpoints now support plain completion, immutable prompt sets, checkpoint comparison, training diagnostics, original/external held-out scoring and human annotations. See `STEP_6_EVALUATION_PLAYGROUND_PLAN.md` and `artifacts/STEP_6_VERIFICATION.md`. Whole-dataset pilot tooling is now delivered; independent validation documents and CUDA verification are needed before broader quality/scaling claims.

2026-11-14 implementation: M4A and M4B now support reviewed-version CPU BPE fitting, exact encode/decode inspection, saved artifacts and non-overlapping padded sequence exports. Verified with isolated sample data. This does not start model training or imply a final full-corpus tokenizer is ready.

M3 follow-up: PDF import, duplicate-upload deletion and **Review & Correct** are implemented. Version-scoped drafts support source-page comparison, explicit Bangla suggestions, manual table/text correction, revision conflicts and reviewed version publication with audit/continuous-text exports. This makes correction tooling available; the user's actual corpus still needs page-by-page review before publishing its corrected version. See `artifacts/DATASET_REVIEW_VERIFICATION.md`.

## 2. Ekhon porjonto complete

| Area | Implemented behavior | Status |
| --- | --- | --- |
| Frontend foundation | React, TypeScript, Vite, responsive navigation/layout | Complete |
| Overview | Empty state, project summary, scope-readiness progress, roadmap | Complete |
| Project Setup | Basics, hardware, budget, sources, success criteria, review | Complete |
| Validation | Partial draft support, invalid-value checks, scope-ready gate | Complete |
| Python backend | FastAPI, project API, health endpoint | Complete |
| PostgreSQL storage | Project create/list/read/update, SQL migrations, persistent Docker volume | Complete |
| Save reliability | Server timestamps/revisions, concurrent-edit conflict detection | Complete |
| Project selection/import | Saved project switching, explicit legacy browser-draft import | Complete |
| Datasets | TXT/JSONL/PDF import, preview, cleaning/deduplication, grouped splits, upload deletion, reviewed corrections and immutable version downloads | Complete |
| Tokenizer + sequences | Reviewed-source CPU BPE training, encode/decode inspection, immutable artifacts, masks/labels, token-stream and bundle downloads | Complete — bounded samples |
| Model Config | Source-derived vocabulary/context, smoke/pilot settings, immutable revisions and export | Complete — bounded configurations |
| Smoke training | Isolated CPU runtime, real loss/gradients, single-worker jobs, checkpoints, reload/resume and downloads | Verified — CPU fixtures; CUDA pending |
| Whole-dataset pilot | All train blocks per epoch, real coverage/metrics, checkpoints, exact linked resume and exports | Verified — CPU fixtures and observed completed live pilot/resume |
| Evaluation | Fixed prompt versions, up to four checkpoints, all-train/smoke-subset diagnostics, original/external held-out scoring, revisioned human notes and reports | Complete — bounded CPU workflow |
| Playground | Frozen-tokenizer CPU checkpoint completion, token-budget preview, history and exports | Complete — plain text completion |
| Environment screen | Python, packages, PyTorch/CUDA probe, NVIDIA driver, RAM/disk results | Complete |
| Local launcher | `.venv` setup, dependencies, PostgreSQL + Python + React launch | Complete |
| Production serving path | Built React frontend ebong API same Python server theke serve | Verified locally |

Environment scope alada: backend `.venv` remains without PyTorch; isolated `.venv-training` has verified Torch 2.11.0 CPU and Transformers 4.57.6. RTX 3060 / 12 GiB driver visible, but CUDA installation timed out and GPU execution is unverified. The live corpus's existing tokenizer/sequence passed read-only smoke-source validation; no live model run was created automatically. Whole-dataset pilot tooling is CPU-verified with isolated fixtures and completed live runs. Larger-corpus training and independent assessment remain execution work.

Latest verification (2026-11-17): **89 backend + 36 frontend + 15 numerical tests pass**, one existing CUDA test explicitly skipped; production build and both dependency checks pass. Real browser checks cover generation, context budget, four-checkpoint comparison over every fixture training block, external evaluation, empty validation, manual-note persistence and mobile layout. Details: `artifacts/STEP_7_VERIFICATION.md`. Earlier verification remains in its respective artifact notes.

## 3. Kototuku baki?

- Initial app foundation ebong project/environment management complete.
- M3, M4, bounded M5 and bounded M7 complete. M6, M8 and M9 have partial execution coverage; M10 and M11 remain future work. Counts do not represent effort percentages.
- Model Config, Pre-training smoke/pilot controls, Evaluation and Playground are functional. Fine-tuning remains planned.
- **The live corpus has completed CPU smoke runs, and live all-train-block checkpoint evaluation is observed.** The live pilot also completed all seven blocks for three epochs (21 updates), with a matched resume and saved all-train checkpoint comparisons. No independent evaluation was attached to those pilot runs during 19 November inspection. Source quality, independent validation, capacity and acceptance criteria need review before larger execution.
- Time/effort-er percentage ekhon reliable na: dataset size, final model size ebong pilot throughput jana nei. Milestone count-ke elapsed-time ba total-effort percentage hisebe dhorbo na.

## 4. Phase A — Age lightweight feature development

### M3 — Datasets screen + backend (complete: 2026-11-09)

- [x] Project-er shathe linked dataset records ebong PostgreSQL migration.
- [x] Local TXT/JSONL import; supported encoding/format ebong size limits clear kora.
- [x] Uploaded/raw files configured local data directory-te rakha; PostgreSQL-e metadata, source provenance, file references ebong processing status rakha.
- [x] Raw data preserve kora; cleaning diye original file overwrite na kora.
- [x] Bounded preview, record counts ebong sample quality inspection.
- [x] Empty record, unwanted markup, whitespace ebong Unicode cleaning-er configurable rules.
- [x] Small sample-e exact deduplication ebong before/after summary.
- [x] Document/source group dhore deterministic train/validation/test split; tokenization/chunking-er age split.
- [x] Source/license/permission metadata link kora; sensitive data manually review korar workflow.
- [x] Processing status, errors ebong output manifest dekhano; long task request-er moddhe block na kora.
- [x] Import, cleaning, reproducible split ebong UI/backend integration verify kora.

**Done when:** Choto real sample import → preview → clean/deduplicate → split kora jay; raw files intact thake ebong reload-er por metadata/output references fire pawa jay.

**Deferred:** Full corpus processing, large-scale near-deduplication, automatic web collection ebong expensive scanning.

### M4 — Tokenizer screen + small-sample pipeline (complete: 2026-11-14)

- [x] Tokenizer method, vocabulary size, fixed special tokens and generated artifact locations.
- [x] Reviewed dataset training split selection; validation/test never used for fitting.
- [x] CPU sample fitting, durable status/cancel/retry and immutable artifact publication.
- [x] Bangla/English/mixed text encode/decode preview, paginated token IDs/pieces/offsets.
- [x] Actual vocabulary, token counts, measured efficiency/timing and saved metadata.
- [x] M4B: fixed-length source-isolated sequences, tail retention, masks, labels, previews and complete export bundles.
- [x] Project isolation, snapshot/checksum validation, restart recovery and dependency-protected deletion.

**Verified:** Bounded sample → tokenizer fit/save/reload → exact encoding → sequence generation → bundle download passes in real PostgreSQL/API/browser checks. Standalone `tokenizers==0.22.2` is pinned; no PyTorch dependency was introduced.

**Deferred:** Full training corpus-er final tokenizer run ebong whole-corpus tokenization.

### M5 — Model Config screen + configuration persistence (bounded scope complete: 2026-11-15)

- [x] Layers, hidden size, attention heads; source-derived read-only vocabulary/context.
- [x] Learning rate, steps and device fields; fixed AdamW/FP32/batch-1/no-warmup smoke preset recorded explicitly.
- [x] Architecture consistency, parameter/storage caps and generation-context validation.
- [x] Dataset/tokenizer/sequence references, random seed and fixed checkpoint/log policy.
- [x] PostgreSQL immutable revisions, save/load/export and unsaved-edit protection.
- [x] Labeled parameter/storage estimates; actual parameter count measured by executor.

**Done when:** Configuration validate/save/reload kora jay. Hardware capacity ba final model size ekhane verified bole claim kora hobe na.

**Verified:** CPU initialization is delivered through the smoke executor. **Deferred:** broader architectures/optimizers, mixed precision and measured GPU memory.

### M6 — Training controls + job infrastructure

- [ ] Pre-training ebong fine-tuning-er alada configuration screens.
- [x] Smoke job records, real metrics/logs/progress and output/checkpoint API.
- [x] Single-worker background execution, cancellation and lease recovery.
- [x] Queued lifecycle, real sleeping-child cancellation and timeout tests.
- [x] Training-runtime readiness gate with missing-runtime/device errors.
- [ ] Fine-tuning dataset schema, role/chat template, assistant-only loss-mask configuration ebong preview rules.
- [x] Actual checkpoint list/download/reload/resume controls and empty states.
- [x] Separate bounded pilot mode: all-block epochs, execution preview, coverage and resumable CPU training.

**Done when:** Job infrastructure independently test kora jay ebong training UI saved configurations use kore. Actual training executor baki thakle screen-e seta explicitly dekhay; fake loss/progress dekhay na.

**Delivered:** Bounded real CPU executor/checkpoints. **Deferred:** CUDA execution verification, larger training budgets and actual SFT processing.

### M7 — Evaluation + Playground (bounded CPU workflow complete: 2026-11-16)

- [x] Immutable prompt-set versions, create/save/load/export and draft protection.
- [x] Real checkpoint comparison/reporting, target-weighted metrics and explicit empty/loading/error states.
- [x] Plain-completion Playground and bounded greedy generation settings.
- [x] Queued CPU inference API, checkpoint selection, polling/cancel/retry/history and downloads.
- [x] Eligibility, source/runtime/hash/context gates and dependency-protected deletion.
- [x] Independent reviewed external-corpus encoding with frozen tokenizer and exact-overlap checks.
- [x] Separate revisioned human annotations; no automatic factual accuracy score.

**Verified:** Real CPU checkpoint loading/generation, seven inference API tests, numerical loss/immutability tests and a four-checkpoint desktop/mobile browser workflow. Current live corpus's seven blocks are training diagnostics; validation/test remain unavailable unless independent data is supplied.

**Deferred:** Streaming/chat, sampling strategies, CUDA inference, sliding-window PPL, reserved final-test workflow and broader quality claims. Plain inference and measured block metrics are delivered.

## 5. Phase B — Sheshe heavier execution

### M8 — Real training environment + full data/tokenizer preparation

- [x] Isolated Python/PyTorch CPU compatibility, pinned training libraries and explicit setup.
- [x] CPU training runtime installed; real forward/backward verified separately from API runtime.
- [ ] Compatible CUDA runtime install and actual GPU forward/backward/training verification.
- [ ] Data source permissions, project scope, budget ebong success criteria finalize.
- [ ] Full corpus import/cleaning/deduplication ebong leakage-resistant document-level splits.
- [ ] Near-deduplication proyojon hole full-run resource budget-er moddhe add kora.
- [ ] Training split diye final tokenizer train; validation/test chara tokenizer fit kora.
- [ ] Final splits tokenization/packing ebong dataset/tokenizer manifest version kora.

**Done when:** Compatible environment ebong reproducible final dataset/tokenizer artifacts ready.

### M9 — Model initialization + real smoke test

- [ ] Hardware/data budget onujayi final small model configuration select.
- [x] Random-weight fixture model initialization and measured parameter count.
- [x] Real CPU executor, causal labels, padding masks and finite gradients.
- [x] Fixed tiny training subset loss decreases; diagnostic verdict recorded.
- [x] CPU RSS, target tokens/second and step time recorded.
- [ ] Actual CUDA peak allocated/reserved VRAM measured (implementation present, runtime unverified).
- [x] Real checkpoint save, fresh-process reload, exact-state CPU resume and bounded generation.
- [ ] Measured pilot throughput diye full training time/cost estimate update.

**Done when:** Numerical stability, memory behavior ebong checkpoint resume pass. Fail hole fix kore tarpor full pre-training.

### M10 — Pre-training + base evaluation

- [x] Bounded whole-dataset CPU pilot tooling, epoch/coverage configuration, exact resume and Evaluation/Playground integration verified using isolated fixtures (Step 7).

- [ ] Agreed compute/data/time budget-e full pre-training run.
- [ ] Real loss, validation, throughput, logs ebong sample generation UI-te connect.
- [ ] Resumable checkpoints ebong disk retention policy verify.
- [ ] Validation results diye base checkpoint select.
- [ ] Fixed prompts, repetition ebong language-quality evaluation; report save.

**Done when:** Base model checkpoint ebong evaluation report ready. Base model instruction-following quality automatically assumed hobe na.

### M11 — Use-case-based mid-training and post-training

Implementation and acceptance criteria are in the [mid-training and fine-tuning plan](MID_TRAINING_FINE_TUNING_PLAN.md). Mid-training is an optional bridge from M10 to supervised fine-tuning. Each project can choose direct SFT from an eligible base checkpoint or compare it with mid-training followed by SFT. The first use case is source-backed Bangla aviation document Q&A.

#### M11 — Fine-tuning + final evaluation/inference

- [ ] Permission-compatible SFT data collect/clean/split; pre-training/evaluation overlap review.
- [ ] Same tokenizer, consistent chat template, assistant-response loss mask ebong truncation policy verify.
- [ ] Full fine-tuning ba LoRA-er small pilot; tarpor agreed budget-e final SFT run.
- [ ] Validation-based checkpoint selection; overfitting/general-language regression inspect.
- [ ] Reserved test set-e base vs fine-tuned model comparison.
- [ ] Real inference/streaming Playground-e connect; latency, memory ebong quality measure.
- [ ] Model/tokenizer/config package, known limitations ebong usable local serving instructions.
- [ ] Quantization/adapter merge ba external deployment dorkar hole scope onujayi add ebong re-evaluate.

**Done when:** Acceptance criteria assess kora hoyeche, reports saved, ebong usable local model/Playground ready. Criteria fail hole relevant data/training stage-e fire jabo.

## 6. Execution order ebong dependency rules

```text
Completed: App foundation + Project Setup + PostgreSQL + Environment inspection
    ↓
M3 Datasets (small samples — COMPLETE)
    ↓
M4 Tokenizer + sequence exports (small-sample test — COMPLETE)
    ↓
M5 Model configuration
    ↓
M6 Training/job infrastructure
    ↓
M7 Evaluation/Playground preparation
    ↓
M8 Compatible PyTorch environment + full dataset/tokenizer processing
    ↓
M9 Real model initialization + smoke test
    ↓
M10 Pre-training + base evaluation
    ↓
M11 SFT + final evaluation + inference
```

UI/API preparation age kora jabe; final runtime integration ebong end-to-end validation real models/artifacts pabar por korte hobe. Original [model training roadmap](MODEL_TRAINING_PLAN.md)-er data → split → tokenizer → smoke test → pre-training → evaluation → fine-tuning dependency order preserve korbo.

## 7. Progress update rule

Prottek milestone complete hole ei file-e corresponding checklist ebong completion log update korbo. UI ready, backend ready ebong actual execution verified—ei state-gulo alada kore record korbo. Work start kora ba placeholder screen thaka diye milestone complete mark korbo na.

| Milestone | Current status |
| --- | --- |
| Initial UI foundation (Step 1) | Complete |
| FastAPI/PostgreSQL/Environment (Step 2) | Complete |
| M3 Datasets | Complete — small-sample pipeline verified |
| M4 Tokenizer + sequences | Complete — bounded sample pipeline verified |
| M5 Model Config | Complete — bounded smoke preset |
| M6 Training/job infrastructure | Smoke workflow verified; fine-tuning/full-run controls pending |
| M7 Evaluation/Playground | Complete — bounded real CPU inference and metrics |
| M8 Full environment/data preparation | CPU runtime ready; CUDA/full-corpus preparation pending |
| M9 Model smoke test | CPU fixture verified; target corpus/final capacity and CUDA pending |
| M10 Pre-training/base evaluation | Bounded CPU pilot/live resume completed; independent assessment and larger training pending |
| M11 Fine-tuning/final inference | Not started |

## 8. Completion log

2026-11-20 follow-up: User-supplied `doc/` Markdown candidates inspected. Native `.md`/`.markdown` import added with one UTF-8 document per file; syntax/tables/code remain text. Two OM-A documents were technically reviewed and evaluated with the original pilot tokenizer on all 28 blocks / 27,075 targets. External loss at steps 7/14/21: 6.9118 / 6.8496 / 6.7999. The 483-block OM-D full conversion exceeds the 256-block cap; closely related OM-D training summary was excluded from this first holdout. 93 backend tests pass (one CUDA skip), 36 frontend tests/build and live browser checks pass. Original docs/model/tokenizer unchanged; human/domain review pending. See `artifacts/STEP_8_MARKDOWN_EVALUATION.json` and the updated Step 8 review.

2026-11-20: Step 8 baseline assessment executed using existing APIs. Original pilot checkpoints 7/14/21 compared over all seven training blocks and 12 frozen prompts; 36/36 compared completions contain 32 newline characters only. Provisional assistant annotations and a matching Playground example were saved, with human/domain approval explicitly pending. Downloads/checkpoint/source integrity passed; original training records and four existing training runs were unchanged. Visual PDF comparison confirms Bangla extraction discrepancies. Existing output views now identify whitespace-only continuations and expose escaped text; 36 frontend tests/build and live desktop/mobile browser checks pass. Only the original dataset is stored; independent evaluation remains pending rather than complete. See `artifacts/STEP_8_EVALUATION_REVIEW.md`.

2026-11-19: Read-only database inspection confirms live pilot `09f2260f-9ed6-4b3d-a2f7-1cade911511a` and its linked resume completed all seven blocks for three epochs, with 21 total updates, matching reload and final all-train loss 6.1099 from initial 7.0591. Attached checkpoint evaluations are training diagnostics. Step 8 independent-evaluation/data-expansion plan saved; execution remains pending. Local HTTP API was unavailable during inspection; no server, training or evaluation was started.

2026-11-17: Whole-dataset pilot implemented. Migration 008 preserves existing run/checkpoint references and adds smoke/pilot mode. 89 backend / 36 frontend / 15 numerical tests pass; one CUDA test skipped. Real CPU/browser fixtures cover all 19 blocks for three epochs (57 updates), exact model/optimizer resume, checkpoints/downloads, interruption handling and pilot Evaluation/Playground. Local server updated after checking no active jobs; existing metadata preserved and no live pilot queued. See `artifacts/STEP_7_VERIFICATION.md`.

2026-11-16: Evaluation and Playground implemented and verified. 84 backend / 34 frontend / 13 numerical tests pass; existing CUDA test skipped. Browser checks cover four checkpoints, all 19 fixture train blocks, independent external scoring, empty-validation unavailability, notes/draft guards, refresh and mobile layout. Migration 007 applied. Read-only live inspection observed a completed comparison of checkpoints 50/100/150/200 over all seven original train blocks, labeled as diagnostics. Existing datasets/checkpoints remain intact; no new model training was triggered. See `artifacts/STEP_6_VERIFICATION.md`.

2026-11-15: Model Config and bounded CPU smoke workflow verified. 77 backend / 30 frontend / 10 numerical tests pass; one CUDA test skipped after dependency-download timeouts. Browser checks passed config saving/navigation protection, real training, lower same-subset loss, checkpoint download/reload/resume and mobile layout. Migrations 005/006 applied; live source artifacts passed read-only validation. No live model run was created automatically. Details: `artifacts/STEP_5_VERIFICATION.md`.

2026-11-14: M4A/M4B complete. Reviewed-version selection, train-only byte-level BPE, exact encoding previews, cancellable native jobs, fixed-length sequence exports and ZIP downloads verified with 69 backend / 26 frontend tests and a real desktop/mobile browser workflow. The live 27-page reviewed source passed read-only validation. No full-corpus tokenizer run or model training was started.

2026-11-14: Review & Correct workflow verified using an isolated PostgreSQL database and generated PDF fixture: save/reload, page review, Version 2 publication, unchanged parent artifacts, derived export checksums and responsive browser flow. The live uploaded PDF is preserved; no actual corpus was automatically marked reviewed. Tokenizer/model training remain unimplemented.

2026-11-09: M3 Datasets complete. TXT/JSONL import, bounded preview, source permission editing/gate, cleaning, exact deduplication, leakage-resistant splits, PostgreSQL jobs/cancellation/recovery, immutable version downloads ebong checked browser flow verified. Large-corpus execution remains deferred. See `artifacts/STEP_3_VERIFICATION.md`.

2026-11-20 Step 9 follow-up: A controlled unchanged-data 10-epoch CPU pilot completed 70 updates; its step-21 model hash matches the original baseline. Frozen external loss was 6.799943 at step 21 and 6.754163 at step 70, but 11 of 12 step-70 outputs were whitespace-only. This is not a usable-generation or domain-quality result. PDF correction drafts, comprehensive source review and permission/domain review remain pending. See `artifacts/STEP_9_PILOT_RESULT.md`.
