# Pre-training Studio

A local workspace for building a small language model, from requirements to pre-training and fine-tuning.

React + TypeScript frontend, Python/FastAPI backend, and **PostgreSQL project storage**. Project Setup, Environment, Datasets, reviewed corrections, CPU tokenizer training and bounded training-sequence exports are implemented. Actual model training remains a later milestone.

## UI screenshots

### Overview

Project dashboard with scope readiness and the training roadmap.

![Pre-training Studio overview with PostgreSQL project storage](artifacts/overview-postgres.png)

### Environment

Real backend-host checks for Python, PyTorch/CUDA, NVIDIA drivers, RAM and disk. Results reflect the machine and packages available when the screenshot was captured.

<details>
<summary>View the desktop Environment screen</summary>

![Desktop Environment screen with hardware checks and package status](artifacts/environment-desktop.png)

</details>

### Mobile layouts

| Project Setup                                                                                                         | Environment                                                                                                   |
| --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| <img src="artifacts/setup-postgres-mobile.png" alt="Mobile Project Setup form with PostgreSQL storage" width="280" /> | <img src="artifacts/environment-mobile.png" alt="Mobile Environment screen with system checks" width="280" /> |

### Datasets

Import and inspect raw text, review cleaning settings, then download versioned train/validation/test splits.

![Datasets library with imported corpus and version status](artifacts/datasets-library-desktop.png)

<details>
<summary>View dataset import, preview and processing screens</summary>

![TXT and JSONL dataset import form](artifacts/datasets-import-desktop.png)

![Raw dataset preview with pagination](artifacts/datasets-preview-desktop.png)

![Cleaning, grouping and split settings review](artifacts/datasets-processing-desktop.png)

![Completed dataset version with split counts and downloads](artifacts/datasets-splits-desktop.png)

</details>

| Mobile dataset overview                                                                                                     | Mobile prepared splits                                                                                           |
| --------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| <img src="artifacts/datasets-overview-mobile.png" alt="Dataset source metadata and original files on mobile" width="280" /> | <img src="artifacts/datasets-splits-mobile.png" alt="Versioned dataset split downloads on mobile" width="280" /> |

## Run everything

Prerequisites: Python 3.11+ with `venv`/`ensurepip`, Node.js 22.12+ (22.x) or 24.x, npm, and Docker with Compose. Verified on Linux with Python 3.14 and Node 24.

From the repository root:

```bash
python3 scripts/dev.py
```

The launcher creates an ignored `.env` with a random database password, creates `.venv`, installs pinned Python and npm dependencies when needed, starts PostgreSQL, applies versioned SQL migrations, and starts Python and React. First startup downloads the PostgreSQL image and dependencies.

- Studio: http://127.0.0.1:5173
- API docs: http://127.0.0.1:8000/docs
- PostgreSQL: `127.0.0.1:55432`

Ctrl+C stops React and Python. PostgreSQL stays in Docker, with data in the named `postgres_data` volume. `docker compose stop db` stops the database without deleting it. Start again with the same command. Configure ports in `.env` if they are occupied.

The app is a local personal workspace: application servers and database bind to loopback. It has no user accounts or public hosting configuration.

## Existing PostgreSQL

Copy `.env.example` to `.env`, then set `DATABASE_URL` to your PostgreSQL connection URL. Percent-encode special characters in usernames/passwords. The launcher skips Docker startup when `DATABASE_URL` is present. The database must already exist; the app creates its own tables and migration history. Runtime credentials need table/index creation and read/write permissions.

Keep `.env` private. The browser never receives database credentials. PostgreSQL is the only supported project database; there is no SQLite or browser-storage fallback.

## Start processes separately

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
# Configure .env first, or use scripts/dev.py for automatic configuration.
docker compose up -d --wait db
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` requests to Python. `.env` ports are honored by the one-command launcher; set `API_PORT` for the frontend proxy when running separately.

For one Python server serving both the API and UI:

```bash
npm run build --prefix frontend
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 after restarting the backend with a build present. Hash-based UI routes work through the same server.

## Project behavior

- Create, select, edit, and restore multiple projects from PostgreSQL. The latest updated project opens initially.
- Valid partial drafts can be saved. Server-side schemas validate numbers, enums and scope readiness independently of the browser.
- The server sets timestamps and revisions. Concurrent edits return a conflict instead of silently overwriting another tab's saved changes. Reload before retrying a conflict; unsaved edits remain open until discarded.
- Saves wait for server confirmation. Connection/database errors are visible and keep edits in the form. Unsaved edits are in memory until saved; they are not an offline backup.
- Legacy Step 1 browser drafts can be explicitly imported as a new project and saved to PostgreSQL. The original browser draft stays untouched. Open the same browser origin used in Step 1 to see that draft.
- Project Setup source fields hold planning metadata. Datasets stores uploaded raw files and prepared versions on local disk, with PostgreSQL metadata. Training is not started by data processing.

## Environment checks

Open **Environment → Run environment checks**. The backend checks:

- Its Python interpreter and installed training package versions.
- PyTorch import and CUDA/device access, in a subprocess with a timeout.
- NVIDIA driver and reported GPU memory, independently of PyTorch access.
- Total/available RAM and free disk at `STUDIO_DATA_DIR` (repository root by default).

Results describe the **backend host**, not the browser device or a remote cloud training machine. The backend checks inspect the API interpreter; the separate **Training runtime** panel tests the smoke executor in `.venv-training`. Missing optional PyTorch/Transformers packages in the API `.venv` do not prevent smoke training when the isolated runtime passes. Normal app setup does not install training libraries; use the explicit setup below.

You can explicitly copy PyTorch-visible GPU details, RAM and free disk to a local project draft, then review/save it. This is disabled for cloud projects and when GPU visibility is unverified. Heterogeneous GPU memory uses the smallest detected VRAM value. Checks do not run a forward/backward pass, estimate model capacity, or guarantee training readiness.

## Datasets: prepare a small sample

1. Save a project, open **Datasets**, and choose **Import dataset**.
2. Enter its name, language, source, license/permission note and permission status. Upload UTF-8 TXT/JSONL or text-based PDF files.
3. Inspect **Overview** and **Preview**. Raw files remain intact; previews show up to 20 records per page and truncate long text at 4,000 characters. Downloads retain full text.
4. Confirm source usage permission in Overview and save metadata. Confirmation is required before processing. Active jobs lock metadata edits; past versions retain their original metadata snapshot.
5. In **Processing**, choose cleanup, deduplication, grouping, split percentages and seed. Review the summary, then start processing. Status updates every two seconds; cancellation and retry are available.
6. In **Splits**, select a successful version and download JSONL splits, all processed records or the manifest. Reloading restores dataset/version records from PostgreSQL.
7. To remove an accidental duplicate, open that dataset and choose **Delete upload**, then confirm. This permanently removes only that imported dataset, its processing history and saved versions; your original file and separately imported copies remain. Cancel or finish active processing first.

Limits per import: **20 files, 20 MiB total, 10,000 documents**. A TXT file is one document; each non-empty JSONL line is one record. Each TXT document/JSONL line is limited to 1 MiB. Unsupported formats/encoding and invalid records are rejected with file/line errors. Use a small sample first; this version does not download remote datasets.

**PDF import:** Selectable text is extracted page by page (maximum 1,000 pages, 1 MiB extracted text per page and 20 MiB extracted text per PDF). Original PDFs are preserved. Each text page becomes a record with its original page number; all pages of the same PDF are grouped together to prevent train/validation/test leakage, including repeated uploads of identical PDF bytes. A single PDF defaults to 100/0/0 splits in the UI. Textless pages are skipped and listed in Overview. Fully scanned/image-only, password-protected and corrupt PDFs are rejected with actionable messages. OCR is not included; run OCR externally before importing scanned files. Review Preview for extraction quality, especially complex layouts and tables.

TXT files may contain multi-line text and an optional UTF-8 BOM. JSONL requires a string `text`; optional `source`, `language` and `group_id` must also be strings:

```jsonl
{"text":"বাংলা শেখার প্রথম উদাহরণ।","source":"Books","language":"bn","group_id":"book-1"}
{"text":"একই বইয়ের আরেকটি অংশ।","source":"Books","language":"bn","group_id":"book-1"}
{"text":"দ্বিতীয় বইয়ের উদাহরণ।","source":"Books","language":"bn","group_id":"book-2"}
{"text":"তৃতীয় বইয়ের উদাহরণ।","source":"Books","language":"bn","group_id":"book-3"}
```

Missing record source/language inherits the import form values. Empty text records are counted at import and removed by default during cleaning. Unicode NFC, line-ending normalization, outer trimming, empty removal and exact deduplication default on. HTML/script/style removal and internal whitespace collapse default off. Bangla joiners and meaningful characters are preserved.

The default split is **90/5/5**, seed **42**. Explicit `group_id` values and identical cleaned content stay in the same split, including when deduplication is off. Source grouping additionally keeps each source together. Deduplicated records keep the first document and merge provenance. Actual ratios may differ because whole groups stay intact. Each non-zero split needs at least one independent group; when only one group exists, choose 100/0/0 or add more independent groups. Dataset processing itself does not tokenize; use the Tokenizer screen after publishing a reviewed version.

Each successful run creates an immutable version with counts, source references, settings/seed and SHA-256 checksums. Failed/cancelled runs do not replace previous outputs. A PostgreSQL-backed worker starts with FastAPI and processes one job globally at a time. Jobs have heartbeat leases; interrupted running jobs are marked failed after a 60-second expired lease, and can be retried. Queued jobs survive restarts.

Dataset storage defaults to `<repository>/data/datasets/`. Set `STUDIO_DATA_DIR` to choose the parent storage root; it must be accessible to the Python process. PostgreSQL stores references, not file contents: preserve this directory together with database backups. Raw files use generated IDs rather than client filenames. The app does not expose arbitrary local paths or ingest a server path provided by the browser.

## Review and correct a saved dataset

Open a dataset, then **Review & Correct**. Choose its saved parent version. Each record opens with its full text and, for PDFs, the original page image. Click the image to inspect it at full size. Correct broken Bangla words, line wrapping, table rows and clause references in the editor; the **Before** section preserves the parent text for comparison.

Word suggestions are page-local and require explicit acceptance; they do not repair arbitrary Bengali glyph mappings. The optional spacing cleanup removes U+200B/BOM and normalizes NFC/line whitespace while preserving Bangla ZWJ/ZWNJ and paragraph breaks. Check suggestions against the PDF. Tables can be rewritten as labeled `Requirement`, `Clause`, `Meaning` lines without changing their facts.

Use **Save draft** for unfinished work, or **Mark reviewed & next** after checking the page. Moving between records saves pending edits; changing parent versions or leaving the workspace requires saving or undoing edits first. Saved drafts survive refreshes and server restarts. Concurrent tabs use draft revisions: conflicts preserve editor text and require reloading the saved draft rather than overwriting it silently. Editing text resets its review flag.

After all records are reviewed and saved, choose **Review publication → Create new corrected version**. A background job snapshots the draft and creates the next version; originals and previous versions stay intact. Editing is locked while processing is active. Cancelled/failed correction jobs can be retried from Review & Correct. Parent checksums are verified; duplicate corrected text crossing splits blocks publication.

Corrected versions keep the same record IDs, provenance and split membership, including 100/0/0 for a single PDF. In **Splits**, download the corrected JSONL, manifest, before/after correction report, page-ordered documents (`documents.jsonl`, with source boundaries and split labels), or continuous **training-only** text. No tokenizer or model is trained here. The UI is a review tool: a user's actual corpus is not automatically marked reviewed or published.

See [review workflow verification](artifacts/DATASET_REVIEW_VERIFICATION.md).

## Tokenizer training and sequence exports

1. Open **Tokenizer** and select a reviewed dataset version. The newest eligible reviewed version is selected initially; newer unreviewed processing versions are disabled. Source permission must be confirmed and the training split nonempty.
2. Choose a vocabulary target (default **8,000**, range 260–32,000), then **Train tokenizer**. Byte-level BPE learns only from the training documents. A PDF is one ordered document, not one document per page. Small corpora may yield a vocabulary below the target; use the displayed **actual vocabulary size** for later model configuration.
3. Inspect the completed run, measured fit duration and checksums. Download `tokenizer.json`, configuration, special-token mapping or manifest. The pinned `tokenizers==0.22.2` dependency is installed by the launcher; PyTorch/Transformers are not required for this workflow.
4. In **Encode / Decode**, enter up to 16 KiB UTF-8 and choose **Encode text**. Inspect IDs, byte-level pieces and Unicode character offsets, with 256 rows per page. Full decoded text must exactly match input, including Bangla joiners, whitespace, emoji and literal `[EOS]`/`[PAD]` spellings. Individual byte pieces can look unfamiliar.
5. Choose sequence length **128/256/512/1024** (default 512), then **Generate sequences**. Uses the same saved tokenizer and fixed dataset version. The builder adds BOS/EOS once per source document, keeps sources/splits separate, and writes non-overlapping right-padded blocks. A singleton tail borrows the preceding block's final token without duplication; every sequence retains at least one next-token target.
6. Preview IDs, masks, labels and document token ranges. Real-token labels equal input IDs; padding labels are `-100`. The future causal model/loss must shift targets exactly once. Decoding one byte-level block can show a partial character at its boundary; whole-document token streams preserve exact text.
7. Download split JSONL, `documents.tokens.jsonl`, the manifest or **complete bundle** ZIP. Empty validation/test splits are retained as empty files with an explicit notice. The bundle includes the exact tokenizer/configuration, all splits and token streams. Its manifest lists constituent file hashes, not hashes of itself or its containing ZIP.

Runs persist in PostgreSQL; artifacts live under `STUDIO_DATA_DIR/tokenizers/` and `STUDIO_DATA_DIR/sequences/`. One preparation worker serializes dataset, tokenizer and sequence work globally. Native fitting/encoding runs in a cancellable child process without database credentials. Queued work survives restart; expired running work fails with retry guidance. Retry creates a new run using the original source/settings, not the latest dataset version. Failed runs leave previously published outputs intact.

Sample limits: 20 MiB reviewed text, 10,000 source records, 2,000,000 content tokens for sequence generation, 256 MiB output and at least 512 MiB free storage. Exceeding limits fails explicitly; text is never silently sampled or truncated. Source version artifacts and downloaded outputs are checked against saved checksums. Delete dependent sequence runs before deleting their tokenizer, and remove tokenizer runs before deleting their source dataset.

This workflow prepares data; it does not initialize or train a language model. The later model configuration must support the chosen sequence length and actual vocabulary size. Future Transformers integration must preserve the exported literal-special-token policy (`split_special_tokens=true`) and unshifted-label contract.

See [Step 4 verification and screenshots](artifacts/STEP_4_VERIFICATION.md).

## Model configuration and smoke training

The **Model Config** and **Pre-training** pages support a bounded, real training diagnostic. They use a randomly initialized tiny GPT-2-style causal model and saved sequences, with no pretrained-model download. This establishes pipeline behavior on a small training subset; it does not establish language quality or rule accuracy.

Set up the training environment explicitly, once:

```bash
python3 scripts/setup_training.py --profile cpu
# NVIDIA alternative, after checking driver/wheel compatibility:
python3 scripts/setup_training.py --profile cu128
```

The script creates `.venv-training`, checks binary-wheel availability, installs pinned dependencies and runs `pip check`. It prefers an available Python 3.13/3.12 or uses the invoking interpreter; `--python /path/to/python` selects one explicitly. Python 3.14 with Torch 2.11.0 CPU was verified here. A predownloaded wheel cache can be used with `--wheelhouse /path/to/wheels --offline`. Normal startup never installs this stack. `STUDIO_TRAINING_PYTHON` optionally selects a server-controlled interpreter; clients cannot supply executable paths.

1. Open **Model Config** and select a completed sequence run from an eligible reviewed version. Vocabulary, context and special IDs come from its saved tokenizer/sequences. They are read-only; generate shorter sequences first if a smaller context is needed.
2. Review model/training settings and **Save new revision**. Default: 2 layers, hidden size 128, 4 heads, FP32, AdamW at 0.0003, 200 optimizer steps, batch 1, seed 42, no warmup/dropout. Unsaved edits block navigation until saved/discarded. Config revisions are immutable and exportable; parameter/storage estimates are checked before submission.
3. Open **Pre-training**, **Check training runtime**, then **Run smoke test**. CPU/CUDA readiness uses a real forward/backward probe in the training interpreter. Auto selects working CUDA or CPU; detected CUDA execution failures require repair or explicit CPU selection.
4. Watch actual optimizer steps, loss, target-token throughput, step time, CPU RSS and CUDA peak memory when available. Only the first one or two train blocks are cycled. Before/after loss is measured on the same subset in eval mode; 5% reduction is the diagnostic pass target. Insufficient reduction gives `needs-attention`, preserving results.
5. Download the complete bundle/report, inspect the bounded generated sample and download verified checkpoints. Checkpoints are saved every 50 steps and at completion. **Resume verification** starts a new linked run from an intermediate checkpoint, preserving optimizer/RNG/cursor state. Runs ending at step 50 have no intermediate checkpoint to resume.

The model shifts causal targets once internally; saved labels remain unshifted and padding labels stay `-100`. At least two real tokens per block are required. Empty validation/test splits remain valid for this train-only diagnostic; no held-out metrics are fabricated. Generation may be unreadable after tiny-subset training.

Training shares the existing single-worker preparation lock. Cancellation terminates the child process; interrupted leases fail with retry available. Partial checkpoints are hidden, verified completed checkpoints can survive cancellation/failure, and source artifacts are never edited. Retry starts from scratch; resume requires a completed parent, compatible config/source, exact runtime versions and device. Referenced source runs/configs/parent checkpoints are protected from deletion.

Bounds: 50–500 steps, up to 15 minutes, at most 10 million model parameters, 1 GiB outputs, 2 GiB available RAM and 5 GiB free artifact disk. Conservative checkpoint/bundle estimates may reject large combinations before launch. Real memory fit is checked by execution. CUDA installation was not completed during verification because wheel downloads timed out; CPU training/reload/resume passed. See [smoke-test verification](artifacts/STEP_5_VERIFICATION.md).

## Whole-dataset pilot training

1. In **Model Config**, choose **Whole-dataset pilot**, a reviewed sequence export, tiny architecture and epochs (default **3**). CPU/FP32 is fixed for this phase. Save a new immutable revision.
2. In **Pre-training**, select **Whole-dataset pilot** under Run mode. The execution preview validates every training block and shows document/block counts, supervised targets per epoch, derived updates, checkpoint steps and estimated storage. Preview and config saving do not start training.
3. **Check training runtime**, then **Start pilot**. Each epoch visits every train block once in a reproducible seeded order. For seven blocks, three epochs mean **21 updates**. Fresh pilots initialize random weights; they do not continue smoke weights.
4. Watch completed epochs, current epoch offset, unique blocks visited and cumulative target exposures. More epochs increase repeated exposures, not corpus size. Initial/final losses are token-weighted all-train diagnostics with no weight updates during scoring. Completion requires coverage, finite gradients, changed weights and verified reload; there is no loss-reduction quality verdict.
5. Download the bundle, coverage report and up to four epoch-boundary checkpoints. **Resume pilot** creates a linked child using the same source/config/runtime and remaining original epoch budget. Published intermediate checkpoints from completed, failed or cancelled pilots are eligible. Retry starts fresh; a final checkpoint cannot extend epochs.
6. Open **Evaluation** or **Playground** to use completed pilot checkpoints. Evaluation labels their original full-train score correctly; old smoke runs retain their subset score. Empty validation remains unavailable. Independent reviewed documents can be evaluated with the existing frozen-tokenizer workflow.

Bounds: 1–20 epochs, all 1–256 training blocks, at most 2,000 updates, 900 seconds, 10 million parameters and 1 GiB total run artifacts. Oversized plans fail without sampling or silently shortening epochs. Checkpoints retain weights, optimizer, RNG, actual epoch order/cursor and source hashes. Source corrections require a new reviewed version/tokenizer/sequences/config. Existing artifacts stay intact.

This is a small-corpus pilot, not a guarantee of language or factual quality. CUDA pilot training, warm starts from smoke checkpoints, epoch-budget extension, automatic best-checkpoint ranking and fine-tuning remain separate work. See [pilot plan](STEP_7_WHOLE_DATASET_PILOT_PLAN.md) and [verification](artifacts/STEP_7_VERIFICATION.md).

## Checkpoint Playground and Evaluation

**Playground** runs plain text completion on a saved CPU-trained checkpoint. Choose a completed training run/checkpoint, enter a prompt and select 8/16/32/64/128 new tokens. The live preview shows prompt tokens plus BOS and remaining context. Prompts are limited to 4 KiB UTF-8; context overflow is rejected without truncation. Greedy decoding uses the exact frozen tokenizer, stops on EOS and suppresses generated PAD/UNK/BOS. Final checkpoint selection is a convenient default, not a quality ranking.

Results are saved automatically with checkpoint/tokenizer hashes, raw generated IDs, output timing, JSON/JSONL reports and ZIP download. A NUL byte in model output is escaped for display; raw token IDs preserve it. Outputs can be repetitive or unreadable after tiny-subset training. This feature does not chat-fine-tune the model or modify its weights.

**Evaluation** compares up to four checkpoints from one run using the same immutable prompt-set version and greedy decoding. Save up to 20 prompts with optional reviewer context. **Edit as new version** preserves older versions; human readability/repetition/source-agreement notes are saved separately with optimistic revisions. Unsaved prompts/review notes block navigation until saved or discarded. Report exports never turn these notes into an automatic accuracy score.

Choose an explicit metric source:

- **All original train blocks:** scores every selected-source train block, plus a separate original-trained-data score: the smoke subset for smoke runs, all training blocks for pilots. The remaining blocks from the same PDF are not an independent held-out set.
- **Original validation split:** scores a nonempty held-out split. If empty, numerical metrics remain **Not available**, while prompt comparisons can still run.
- **Independent reviewed external corpus:** select a reviewed version with confirmed source permission. It is encoded using the checkpoint tokenizer with no refitting, even if its original dataset export labels its records `train`. Known dataset/file/document/group/content overlap is blocked. Exact checks do not rule out near-duplicates; review independence manually.

Reported loss is weighted by actual causal target-token counts, excluding padding and each block's unpredicted first token. **Block-based NLL/PPL v1** uses existing document-isolated non-overlapping blocks; its perplexity is not accuracy or sliding-window corpus PPL. Compare only the same tokenizer, target data and scoring protocol. Reserved test-set tuning and automatic best-checkpoint ranking are outside this workflow.

Inference uses the existing single-worker queue and isolated `.venv-training` subprocess. Initial support is CPU-trained checkpoints on their matching pinned CPU runtime. Maximum: four checkpoints, 20 prompts, 256 evaluation blocks, 15 minutes and 128 MiB result artifacts. Missing/corrupt artifacts, incompatible runtime, over-limit requests and known overlaps fail explicitly. Cancellation/retry/restart recovery are durable; referenced checkpoints, prompt versions and external datasets are protected from deletion. Existing runtime setup and app start commands remain unchanged.

See [Step 6 verification and screenshots](artifacts/STEP_6_VERIFICATION.md).

## Verify

```bash
npm test --prefix frontend
npm run build --prefix frontend
.venv/bin/python -m pytest -q --tb=short
.venv-training/bin/python -m pytest -q backend/training_tests --tb=short
```

Backend integration tests use **real PostgreSQL**, creating and dropping a uniquely named test database. The configured PostgreSQL role must have `CREATEDB` permission for these tests (the local Docker role does). Alternatively set `TEST_DATABASE_URL` to a dedicated database whose name contains `test`; tests retain their uniquely identified records there and never clear the application database. Environment-probe unit tests simulate missing packages, timeouts and GPU outcomes.

Real training API tests require explicit `.venv-training` setup; missing runtime/GPU tests are reported as skipped rather than numerical passes. Standalone numerical tests run in the training environment without the API/database stack. Verify these explicitly before claiming a working executor.

SQL migrations are in `backend/migrations/`. Each migration is recorded transactionally, with an advisory lock preventing concurrent migration runs. Future schema changes should add a new numbered SQL migration.

## API

- `GET /api/health` — checks PostgreSQL connectivity.
- `GET /api/projects` — saved projects, latest first.
- `POST /api/projects` — create a project with revision 0.
- `GET /api/projects/{id}` — restore one project.
- `PATCH /api/projects/{id}` — submit the full edited project with its current revision; returns the next revision.
- `GET /api/environment` — run read-only host checks (may take up to about 30 seconds).

Dataset endpoints (prefix `/api/projects/{project_id}/datasets`):

- `GET /` and `POST /` — list datasets / multipart import (`metadata` JSON field plus repeated `files`). Use the prefix without a trailing slash.
- `GET /{dataset_id}` and `PATCH /{dataset_id}` — detail / update dataset metadata and source permission.
- `DELETE /{dataset_id}` — delete the selected imported dataset, its jobs, versions and stored files; returns 409 while processing is queued or running.
- `GET /{dataset_id}/preview` — `page`, `page_size` (max 20), optional `version_id` and `split` (`processed`, `train`, `validation`, `test`).
- `POST /{dataset_id}/process` — queue processing settings; returns 202 with a job ID.
- `GET /{dataset_id}/jobs/{job_id}` and `POST /{dataset_id}/jobs/{job_id}/cancel` — status / cancellation.
- `GET /{dataset_id}/versions/{version_id}/download?artifact=manifest` — choose `manifest`, `processed`, `train`, `validation` or `test`.
- `GET /{dataset_id}/versions/{version_id}/corrections?page=1` — full parent record, saved draft, review counts and source-image link.
- `PUT /{dataset_id}/versions/{version_id}/corrections` — save `recordId`, `text`, `reviewed` and optimistic `revision`; stale drafts return 409.
- `POST /{dataset_id}/versions/{version_id}/corrections/publish` — snapshot the supplied draft `revision`; all records must be reviewed. Returns a durable job.
- `GET /{dataset_id}/files/{file_id}/pages/{page}/image` — render a bounded PNG of an imported PDF page.

Corrected-version downloads additionally accept `continuous` (training-only TXT), `documents` (source-separated JSONL) and `corrections` (before/after JSON report).

Tokenizer endpoints (`/api/projects/{project_id}/tokenizers`):

- `GET /sources`: eligible/rejected dataset versions and reasons; `GET /` / `POST /`: list / queue fitting with `{datasetVersionId, vocabSize}`.
- `GET /{run_id}`: durable status, source, settings and artifacts; `POST /{run_id}/encode`: `{text, tokenPage}` for bounded inspection.
- `POST /{run_id}/cancel`, `POST /{run_id}/retry`, `DELETE /{run_id}`: lifecycle controls; deletion is dependency-protected.
- `GET /{run_id}/download?artifact=tokenizer|config|special_tokens|manifest`.

Sequence endpoints (`/api/projects/{project_id}/sequence-runs`) share list/detail/cancel/retry/delete behavior:

- `POST /`: `{tokenizerRunId, sequenceLength}`; `GET /{run_id}/preview?split=train&page=1`: up to five sequences per response.
- `GET /{run_id}/download?artifact=train|validation|test|tokens|manifest|bundle`.

Model/training endpoints (prefix `/api/projects/{project_id}`):

- `GET/POST /model-configs`: list / save `{sequenceRunId, name, settings}`; `GET /model-configs/{id}`, `GET /model-configs/{id}/export`, `DELETE /model-configs/{id}`.
- `GET /training-runtime?refresh=true`: scoped import/CPU/CUDA execution checks, up to 60 seconds.
- `POST /model-configs` also accepts `{trainingKind: "pilot", sequenceRunId, name, settings: {epochs, device: "cpu", ...}}`; omit smoke-only `maxSteps`.
- `POST /pilot-preview` with `{modelConfigId}` validates and returns the full epoch/checkpoint plan without enqueueing.
- `GET/POST /pilot-runs`, `GET /pilot-runs/{id}`: mode-scoped history/start/status. Cancel/retry/resume/delete/metrics/checkpoint-download routes mirror smoke routes.
- `GET /pilot-runs/{id}/download?artifact=bundle|report|coverage|metrics|manifest` includes verified coverage and model/resume artifacts.
- `GET/POST /smoke-runs`: list / queue `{modelConfigId}`; `GET /smoke-runs/{id}` includes durable metrics, verdict and registered checkpoints.
- `GET /smoke-runs/{id}/metrics?afterStep=50`: bounded optimizer-step events; no fabricated progress.
- `POST /smoke-runs/{id}/cancel`, `/retry`, `/resume` (body `{checkpointId}`), `DELETE /smoke-runs/{id}`.
- `GET /smoke-runs/{id}/download?artifact=bundle|report|sample|metrics|config|tokenizer|tokenizer_config|special_tokens|manifest`.
- `GET /smoke-runs/{id}/checkpoints/{checkpoint_id}/download`: checksum-verified checkpoint ZIP, including saved model and restricted-load tensor/optimizer state.

Inference endpoints (same project prefix):

- `GET /inference-sources`: completed runs/checkpoints and eligibility; `POST /inference-preview`: `{checkpointId, prompt}` token budget.
- `GET/POST /prompt-sets`: all saved versions / create a set or append a version using optional set `id`; body includes `name`, `language`, `prompts: [{text, notes}]`.
- `GET /prompt-sets/{set_id}/versions/{version}` and `/export`; `DELETE /prompt-sets/{set_id}` is dependency-protected.
- `POST /generation-runs`: `{checkpointId, prompt, maxNewTokens}`.
- `POST /evaluation-runs`: `{checkpointIds, promptSetVersionId, maxNewTokens, metricScope, externalDatasetVersionId?}`; scope is `training`, `validation` or `external`.
- Both run types have list/detail/cancel/retry/delete and `/download?artifact=bundle|report|outputs|manifest|events`.
- `GET/PUT /evaluation-runs/{id}/annotations`: revisioned human observations keyed by checkpoint and prompt index; `/annotations/export` downloads the current review snapshot separately.

## Plans and verification

- [Full training roadmap](MODEL_TRAINING_PLAN.md)
- [Remaining work and lightweight-first roadmap](REMAINING_WORK_PLAN.md)
- [Step 1 UI plan](STEP_1_UI_PLAN.md)
- [Step 2 implementation notes](STEP_2_BACKEND_PLAN.md)
- [Step 2 verification](artifacts/STEP_2_VERIFICATION.md)
- [Step 3 datasets implementation](STEP_3_DATASETS_PLAN.md)
- [Step 3 verification](artifacts/STEP_3_VERIFICATION.md)
- [Model smoke-test plan](STEP_5_MODEL_SMOKE_TEST_PLAN.md)
- [Model smoke-test verification](artifacts/STEP_5_VERIFICATION.md)
- [Evaluation/Playground plan](STEP_6_EVALUATION_PLAYGROUND_PLAN.md)
- [Evaluation/Playground verification](artifacts/STEP_6_VERIFICATION.md)
- [Verification artifacts](artifacts/)

- [Whole-dataset pilot plan](STEP_7_WHOLE_DATASET_PILOT_PLAN.md)
- [Whole-dataset pilot verification](artifacts/STEP_7_VERIFICATION.md)
