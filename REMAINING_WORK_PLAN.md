# Pre-training Studio — Progress ebong Remaining Work

Updated: 2026-11-01 (Asia/Dhaka)

## 1. Agreed working order

Age app-er UI, configuration, PostgreSQL metadata ebong choto sample diye testable backend features complete korbo. GPU-dependent installation, full dataset processing ebong actual model training shesher execution phase-e rakhbo.

Dataset import, preview, basic cleaning, exact deduplication ebong document-level split-er jonno PyTorch lagbe na. Tokenizer-er small-sample test-o PyTorch chara kora jay. Boro dataset processing/tokenizer training CPU, RAM ebong disk-er upor heavy hote pare; tai prothome bounded sample use korbo.

**Next implementation: Datasets screen + backend.** Ei document planning/progress artifact; notun dataset/training feature ekhono implement kora hoyni.

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
| Environment screen | Python, packages, PyTorch/CUDA probe, NVIDIA driver, RAM/disk results | Complete |
| Local launcher | `.venv` setup, dependencies, PostgreSQL + Python + React launch | Complete |
| Production serving path | Built React frontend ebong API same Python server theke serve | Verified locally |

Environment screen complete mane training environment ready na. Last verified setup-e GPU driver RTX 3060 / 12 GB VRAM report korechilo; backend `.venv`-e PyTorch ebong core training libraries install kora hoyni. Actual dataset, tokenizer, model checkpoint ba training run ekhono nei.

Previous verification: 13 frontend tests + 9 backend tests pass; production build, real PostgreSQL stop/start persistence ebong checked browser flows pass. Details: [Step 2 verification](artifacts/STEP_2_VERIFICATION.md).

## 3. Kototuku baki?

- Initial app foundation ebong project/environment management complete.
- Nicher revised roadmap-e **9-ti milestone baki**: 5-ti feature-building milestone, tarpor 4-ti heavier execution milestone.
- Datasets, Tokenizer, Model Config, Pre-training, Evaluation, Fine-tuning ebong Playground-er functional workflows baki. Existing sidebar entries sudhu planned placeholders.
- **Actual model training ekhono shuru hoyni.** Training project-er scope, data sources, permission ebong acceptance criteria user-keo fill/confirm korte hobe; UI complete howa diye ei decisions automatically complete hoy na.
- Time/effort-er percentage ekhon reliable na: dataset size, final model size ebong pilot throughput jana nei. Milestone count-ke elapsed-time ba total-effort percentage hisebe dhorbo na.

## 4. Phase A — Age lightweight feature development

### M3 — Datasets screen + backend (next)

- [ ] Project-er shathe linked dataset records ebong PostgreSQL migration.
- [ ] Local TXT/JSONL import; supported encoding/format ebong size limits clear kora.
- [ ] Uploaded/raw files configured local data directory-te rakha; PostgreSQL-e metadata, source provenance, file references ebong processing status rakha.
- [ ] Raw data preserve kora; cleaning diye original file overwrite na kora.
- [ ] Bounded preview, record counts ebong sample quality inspection.
- [ ] Empty record, unwanted markup, whitespace ebong Unicode cleaning-er configurable rules.
- [ ] Small sample-e exact deduplication ebong before/after summary.
- [ ] Document/source group dhore deterministic train/validation/test split; tokenization/chunking-er age split.
- [ ] Source/license/permission metadata link kora; sensitive data manually review korar workflow.
- [ ] Processing status, errors ebong output manifest dekhano; long task request-er moddhe block na kora.
- [ ] Import, cleaning, reproducible split ebong UI/backend integration verify kora.

**Done when:** Choto real sample import → preview → clean/deduplicate → split kora jay; raw files intact thake ebong reload-er por metadata/output references fire pawa jay.

**Deferred:** Full corpus processing, large-scale near-deduplication, automatic web collection ebong expensive scanning.

### M4 — Tokenizer screen + small-sample pipeline

- [ ] Tokenizer method, vocabulary size, special tokens ebong output location configuration.
- [ ] Saved dataset training split select kora; validation/test data diye tokenizer train na kora.
- [ ] Small sample-e tokenizer train, progress/status ebong artifact save.
- [ ] Bangla/English/mixed text encode/decode preview.
- [ ] Token count, basic efficiency report ebong saved tokenizer metadata.

**Done when:** Bounded training sample theke tokenizer create, save/reload ebong encode/decode verify kora jay. Compatible standalone tokenizer dependency lagte pare; PyTorch lagbe na.

**Deferred:** Full training corpus-er final tokenizer run ebong whole-corpus tokenization.

### M5 — Model Config screen + configuration persistence

- [ ] Layers, hidden size, attention heads, vocabulary ebong context length fields.
- [ ] Optimizer, learning rate, warmup, batch size, gradient accumulation ebong precision fields.
- [ ] Architecture consistency checks, jemon hidden size attention-head count diye divisible kina.
- [ ] Dataset/tokenizer version references, random seed ebong checkpoint/log settings.
- [ ] PostgreSQL-e versioned config save/load ebong export.
- [ ] Estimated parameter/memory values thakle assumptions-shoho estimate label deya.

**Done when:** Configuration validate/save/reload kora jay. Hardware capacity ba final model size ekhane verified bole claim kora hobe na.

**Deferred:** Real model initialization ebong GPU memory measurement.

### M6 — Training controls + job infrastructure

- [ ] Pre-training ebong fine-tuning-er alada configuration screens.
- [ ] Job records, status transitions, logs, progress ebong output/checkpoint references-er API contract.
- [ ] Background execution, cancellation ebong failure recovery-er infrastructure.
- [ ] Small non-training task diye real job lifecycle test.
- [ ] Training controls-er capability/readiness gate; executor na thakle clear unavailable state.
- [ ] Fine-tuning dataset schema, role/chat template, assistant-only loss-mask configuration ebong preview rules.
- [ ] Checkpoint list/resume controls-er UI contract; real checkpoint na thakle empty state.

**Done when:** Job infrastructure independently test kora jay ebong training UI saved configurations use kore. Actual training executor baki thakle screen-e seta explicitly dekhay; fake loss/progress dekhay na.

**Deferred:** PyTorch training executor, GPU smoke test, real checkpoint creation/resume ebong actual SFT processing run.

### M7 — Evaluation + Playground UI/API preparation

- [ ] Fixed evaluation prompt sets create/save/load.
- [ ] Evaluation report schema, comparison UI ebong empty/loading/error states.
- [ ] Playground prompt/chat layout ebong generation-settings form.
- [ ] Inference request/streaming-response contract ebong model selection.
- [ ] Verified model/executor na thakle generation/run controls unavailable state.

**Done when:** Prompt/configuration/report workflows ready ebong inference integration-er boundaries clear. Real model output/metrics chara real evaluation complete bola hobe na.

**Deferred:** Real inference, measured metrics, generation streaming ebong model quality comparison.

## 5. Phase B — Sheshe heavier execution

### M8 — Real training environment + full data/tokenizer preparation

- [ ] Python/PyTorch/CUDA compatibility verify kore backend/training environment-er dependency versions select/pin.
- [ ] Compatible PyTorch ebong core training libraries install; GPU detection verify.
- [ ] Data source permissions, project scope, budget ebong success criteria finalize.
- [ ] Full corpus import/cleaning/deduplication ebong leakage-resistant document-level splits.
- [ ] Near-deduplication proyojon hole full-run resource budget-er moddhe add kora.
- [ ] Training split diye final tokenizer train; validation/test chara tokenizer fit kora.
- [ ] Final splits tokenization/packing ebong dataset/tokenizer manifest version kora.

**Done when:** Compatible environment ebong reproducible final dataset/tokenizer artifacts ready.

### M9 — Model initialization + real smoke test

- [ ] Hardware/data budget onujayi final small model configuration select.
- [ ] Random-weight model initialize ebong parameter count verify.
- [ ] Real training executor integrate; causal labels, padding masks ebong finite gradients verify.
- [ ] Tiny subset-e short run kore loss decrease check.
- [ ] Measured VRAM, tokens/second ebong step time record.
- [ ] Real checkpoint save/reload/resume ebong generation check.
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
M3 Datasets (small samples)
    ↓
M4 Tokenizer (small-sample test)
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
| M3 Datasets | Not started — next |
| M4 Tokenizer | Not started |
| M5 Model Config | Not started |
| M6 Training/job infrastructure | Not started |
| M7 Evaluation/Playground preparation | Not started |
| M8 Full environment/data preparation | Not started |
| M9 Model smoke test | Not started |
| M10 Pre-training/base evaluation | Not started |
| M11 Fine-tuning/final inference | Not started |
