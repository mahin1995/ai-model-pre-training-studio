# Pre-training Studio — Progress ebong Remaining Work

Updated: 2026-11-16 (Asia/Dhaka)

## 1. Agreed working order

Age app-er UI, configuration, PostgreSQL metadata ebong choto sample diye testable backend features complete korbo. GPU-dependent installation, full dataset processing ebong actual model training shesher execution phase-e rakhbo.

Dataset import, preview, basic cleaning, exact deduplication ebong document-level split-er jonno PyTorch lagbe na. Tokenizer-er small-sample test-o PyTorch chara kora jay. Boro dataset processing/tokenizer training CPU, RAM ebong disk-er upor heavy hote pare; tai prothome bounded sample use korbo.

**Latest delivered: M7 bounded Evaluation and Playground.** Saved CPU checkpoints now support plain completion, immutable prompt sets, checkpoint comparison, training diagnostics, original/external held-out scoring and human annotations. See `STEP_6_EVALUATION_PLAYGROUND_PLAN.md` and `artifacts/STEP_6_VERIFICATION.md`. Next phase is a separate bounded whole-dataset training pilot with explicit coverage/epoch configuration; independent validation documents and CUDA verification are needed before broader quality/scaling claims.

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
| Model Config | Source-derived vocabulary/context, bounded architecture/training settings, immutable revisions and export | Complete — smoke configuration |
| Smoke training | Isolated CPU runtime, real loss/gradients, single-worker jobs, checkpoints, reload/resume and downloads | Verified — CPU fixtures; CUDA pending |
| Evaluation | Fixed prompt versions, up to four checkpoints, all-train/smoke-subset diagnostics, original/external held-out scoring, revisioned human notes and reports | Complete — bounded CPU workflow |
| Playground | Frozen-tokenizer CPU checkpoint completion, token-budget preview, history and exports | Complete — plain text completion |
| Environment screen | Python, packages, PyTorch/CUDA probe, NVIDIA driver, RAM/disk results | Complete |
| Local launcher | `.venv` setup, dependencies, PostgreSQL + Python + React launch | Complete |
| Production serving path | Built React frontend ebong API same Python server theke serve | Verified locally |

Environment scope alada: backend `.venv` remains without PyTorch; isolated `.venv-training` has verified Torch 2.11.0 CPU and Transformers 4.57.6. RTX 3060 / 12 GiB driver visible, but CUDA installation timed out and GPU execution is unverified. The live corpus's existing tokenizer/sequence passed read-only smoke-source validation; no live model run was created automatically. Full-corpus model training remains future execution work.

Latest verification (2026-11-16): **84 backend + 34 frontend + 13 numerical tests pass**, one existing CUDA test explicitly skipped; production build and both dependency checks pass. Real browser checks cover generation, context budget, four-checkpoint comparison over every fixture training block, external evaluation, empty validation, manual-note persistence and mobile layout. Details: `artifacts/STEP_6_VERIFICATION.md`. Earlier verification remains in its respective artifact notes.

## 3. Kototuku baki?

- Initial app foundation ebong project/environment management complete.
- M3, M4, bounded M5 and bounded M7 complete. M6, M8 and M9 have partial execution coverage; M10 and M11 remain future work. Counts do not represent effort percentages.
- Model Config, Pre-training smoke controls, Evaluation and Playground are functional. Fine-tuning remains planned.
- **The live corpus has completed CPU smoke runs, and live all-train-block checkpoint evaluation is observed.** Full-corpus training has not started: smoke training still uses at most two blocks. Source quality, independent validation, capacity and acceptance criteria need review before larger execution.
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

**Done when:** Job infrastructure independently test kora jay ebong training UI saved configurations use kore. Actual training executor baki thakle screen-e seta explicitly dekhay; fake loss/progress dekhay na.

**Delivered:** Bounded real CPU executor/checkpoints. **Deferred:** CUDA execution verification, full training controls and actual SFT processing.

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

- [ ] Agreed compute/data/time budget-e full pre-training run.
- [ ] Real loss, validation, throughput, logs ebong sample generation UI-te connect.
- [ ] Resumable checkpoints ebong disk retention policy verify.
- [ ] Validation results diye base checkpoint select.
- [ ] Fixed prompts, repetition ebong language-quality evaluation; report save.

**Done when:** Base model checkpoint ebong evaluation report ready. Base model instruction-following quality automatically assumed hobe na.

### M11 — Fine-tuning + final evaluation/inference

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
| M10 Pre-training/base evaluation | Not started |
| M11 Fine-tuning/final inference | Not started |

## 8. Completion log

2026-11-16: Evaluation and Playground implemented and verified. 84 backend / 34 frontend / 13 numerical tests pass; existing CUDA test skipped. Browser checks cover four checkpoints, all 19 fixture train blocks, independent external scoring, empty-validation unavailability, notes/draft guards, refresh and mobile layout. Migration 007 applied. Read-only live inspection observed a completed comparison of checkpoints 50/100/150/200 over all seven original train blocks, labeled as diagnostics. Existing datasets/checkpoints remain intact; no new model training was triggered. See `artifacts/STEP_6_VERIFICATION.md`.

2026-11-15: Model Config and bounded CPU smoke workflow verified. 77 backend / 30 frontend / 10 numerical tests pass; one CUDA test skipped after dependency-download timeouts. Browser checks passed config saving/navigation protection, real training, lower same-subset loss, checkpoint download/reload/resume and mobile layout. Migrations 005/006 applied; live source artifacts passed read-only validation. No live model run was created automatically. Details: `artifacts/STEP_5_VERIFICATION.md`.

2026-11-14: M4A/M4B complete. Reviewed-version selection, train-only byte-level BPE, exact encoding previews, cancellable native jobs, fixed-length sequence exports and ZIP downloads verified with 69 backend / 26 frontend tests and a real desktop/mobile browser workflow. The live 27-page reviewed source passed read-only validation. No full-corpus tokenizer run or model training was started.

2026-11-14: Review & Correct workflow verified using an isolated PostgreSQL database and generated PDF fixture: save/reload, page review, Version 2 publication, unchanged parent artifacts, derived export checksums and responsive browser flow. The live uploaded PDF is preserved; no actual corpus was automatically marked reviewed. Tokenizer/model training remain unimplemented.

2026-11-09: M3 Datasets complete. TXT/JSONL import, bounded preview, source permission editing/gate, cleaning, exact deduplication, leakage-resistant splits, PostgreSQL jobs/cancellation/recovery, immutable version downloads ebong checked browser flow verified. Large-corpus execution remains deferred. See `artifacts/STEP_3_VERIFICATION.md`.
