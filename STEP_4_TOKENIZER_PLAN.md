# Step 4 — Tokenizer Training and Training-Sequence Generation

Status: M4A and M4B implemented and verified on isolated sample data. Model training has not started.

Verification: [Tokenizer and sequence checks](artifacts/STEP_4_VERIFICATION.md). The decisions below are the implemented contract; actual full-corpus tokenizer/model runs remain separate work.

Prepared: 2026-11-14 (Asia/Dhaka).

## Goal and scope

Replace the Tokenizer placeholder with a local, project-scoped workflow:

**Reviewed dataset version → Train tokenizer → Inspect encoding → Generate sequences → Download artifacts.**

Deliver two independently testable parts: **M4A, tokenizer training and inspection**, then **M4B, sequence generation using a saved tokenizer**. This extends the roadmap's small-sample M4 milestone to include sequence export. Final full-corpus preparation, model configuration, PyTorch installation and model training remain later milestones.

Keep React/TypeScript, FastAPI, PostgreSQL and the single-server production path. CPU only; no cloud services, Hub upload, external dataset download or GPU dependency.

## Skill and evidence

Used the installed `find-skills` workflow to locate Orchestra Research's [huggingface-tokenizers skill](https://github.com/Orchestra-Research/AI-Research-SKILLs/blob/main/02-tokenization/huggingface-tokenizers/SKILL.md), then read its training/pipeline references directly. No new skill or BMad runtime was installed. Repository requirements take precedence: training data only, minimal text changes and preserved provenance. The skill's illustrative validation-set fitting and throughput estimates are not adopted.

Implementation references:

- [Hugging Face's byte-level BPE example at v0.22.2](https://github.com/huggingface/tokenizers/blob/v0.22.2/bindings/python/examples/train_bytelevel_bpe.py).
- [Versioned Python tokenizer API](https://github.com/huggingface/tokenizers/blob/v0.22.2/bindings/python/py_src/tokenizers/__init__.pyi).
- [Causal language modeling and block preparation](https://huggingface.co/docs/transformers/en/tasks/language_modeling).
- Existing dataset corrections, immutable publication, checksum and background-worker conventions in this repository.

## Input eligibility and immutable lineage

- The first implementation accepts one dataset version per tokenizer run. It must belong to the selected project, have confirmed source permission, contain nonempty training data and have a published correction manifest with `reviewedRecords == counts.output`.
- Default to the newest **eligible reviewed version**, not simply the largest version number. During inspection, this corpus had reviewed Versions 2 and 3, while Version 4 was ordinary processing output; Version 3 is currently the default candidate. Query this dynamically; never hardcode these numbers or UUIDs.
- Drafts, raw imports and unreviewed versions are visible with an explanation but cannot start this workflow. A newer unreviewed version does not invalidate an older reviewed version.
- Validate the selected version's manifest and checksums for `processed.jsonl`, `documents.jsonl` and all split files before preparing inputs. Validate source document/record IDs, page order and split membership against the manifest; fail on inconsistency.
- Read reviewed `documents.jsonl`. Each source PDF is one document in original page order. Preserve TXT/JSONL document boundaries. Train only on documents labeled `train`; encode other nonempty splits with the resulting tokenizer without fitting again.
- Snapshot the version UUID, settings, source hashes and library version at submission. Dataset changes and later versions cannot redirect a queued run.
- Tokenizer/sequence references prevent deleting their source dataset through UI/API and database foreign keys. Return an actionable 409; remove dependent runs first. Lock the dataset row during submission/deletion to avoid races.

## M4A — Train, save and inspect a tokenizer

### Decisions

| Setting | Default / constraint |
| --- | --- |
| Library | Pin `tokenizers==0.22.2`; verify installation/import on the existing Python 3.14 environment |
| Model | Byte-level BPE; `min_frequency=2`, no dropout |
| Vocabulary target | 8,000; integer range 260–32,000, including reserved tokens |
| Byte coverage | Full 256-byte alphabet using `ByteLevel.alphabet()` |
| Reserved IDs | `[PAD]=0`, `[UNK]=1`, `[BOS]=2`, `[EOS]=3`; all distinct |
| Text processing | `ByteLevel(add_prefix_space=False)` and ByteLevel decoder; no lowercasing, accent stripping or additional normalization |
| Boundary insertion | Sequence builder owns BOS/EOS; tokenizer has no automatic boundary postprocessor |
| Corpus spelling of reserved tokens | Encode literal `[PAD]`/`[EOS]` etc. as ordinary content, not inserted control IDs; verify the versioned API setting and test it |

The requested vocabulary is a ceiling/target. A small corpus may produce fewer tokens; display requested and actual sizes without treating this as a failure. Future model configuration must use the **actual vocabulary size**.

### UI and behavior

- Tokenizer library and New tokenizer form: eligible dataset/version, vocabulary target and immutable configuration summary.
- Training job status, elapsed time, actual errors, cancellation and retry. Show an indeterminate training stage while the native BPE trainer runs; do not invent a merge-progress percentage.
- Saved-run details: source version/review status, actual vocabulary, training document/byte counts, tokenizer checksum and measured training duration.
- Encode/decode playground: input text, token IDs, byte-level token pieces, offsets, decoded full text, token count and UTF-8 bytes/token. Individual byte-token pieces may not be readable Bangla; full decoded text is the round-trip check.
- Keep inspection requests bounded to 16 KiB of valid UTF-8 and 256 visible token rows with pagination. Return full counts; never silently truncate the submitted text.
- Save/reload `tokenizer.json`, `tokenizer_config.json` and `special_tokens_map.json`; configurations record exact boundary, literal-special-token and normalization policies for later training/inference integration.

### API contracts

Prefix: `/api/projects/{project_id}/tokenizers`.

- `GET /`: list runs; `POST /`: queue `{datasetVersionId, vocabSize}` and return 202 plus job/run ID.
- `GET /{run_id}`: source lineage, settings, status, measured counts and registered artifacts.
- `POST /{run_id}/cancel`: request cancellation; `POST /{run_id}/retry`: create a new run with the same immutable source/settings.
- `POST /{run_id}/encode`: `{text, tokenPage}`; return IDs/pieces/offsets for the requested page, total count, decoded text and round-trip result.
- `GET /{run_id}/download?artifact=tokenizer|config|special_tokens|manifest`.
- `DELETE /{run_id}`: only terminal runs with no dependent sequence runs; preserve the dataset. Active/dependent runs return 409.

## M4B — Generate training sequences

- Select a completed saved tokenizer. Its original dataset version is fixed; choosing a different corpus or combining versions is deferred.
- Sequence lengths: **128, 256, 512, 1024**; default **512**, including special tokens and padding.
- Encode each complete source document, then prepend one BOS and append one EOS per document, not per PDF page. Do not mix source documents or splits inside a sequence.
- Preserve the previously agreed **non-overlapping** blocks. Keep the final partial block and right-pad it. If a final block would contain just one token, move the preceding block's last real token into it, padding both blocks as necessary. This retains every token without overlap and prevents a one-token, all-ignored causal-loss sample.
- Export JSONL with `input_ids`, `attention_mask`, `labels`, and provenance metadata (`documentId`, original record/page references, split, ordinal). Arrays always have the chosen sequence length.
- Labels equal input IDs on real tokens and use `-100` on padding. They are **not pre-shifted**: the future causal-LM model/loss must perform the next-token shift exactly once. Every sequence has at least two real tokens.
- Generate `train.jsonl`, `validation.jsonl`, `test.jsonl`; empty splits produce empty files plus an explicit UI note, not synthetic records.
- Preview a sequence's IDs, decoded content, masks, labels and source range. Report unique content tokens, BOS/EOS tokens, padded tokens, sequence counts and padding ratio separately.
- Preserve page order in per-document token streams. Export `documents.tokens.jsonl` so concatenating each document's unpadded sequence IDs can be checked against its complete original token stream.

Sequence API prefix: `/api/projects/{project_id}/sequence-runs`.

- `POST /`: `{tokenizerRunId, sequenceLength}` → 202; `GET /` and `GET /{run_id}`: list/details.
- `GET /{run_id}/preview?split=train&page=1`: paginated sequence previews, maximum five sequences per request.
- `POST /{run_id}/cancel` and `POST /{run_id}/retry`: same durable-job behavior as tokenizer runs.
- `GET /{run_id}/download?artifact=train|validation|test|tokens|manifest|bundle`: fixed artifact allowlist; bundle contains the exact tokenizer, configuration, sequences, tokens and manifest.
- `DELETE /{run_id}`: remove only that terminal run and its artifacts.

## Storage, execution and limits

- Add migration `004_tokenizer_sequences.sql` with project-scoped `tokenizer_runs` and `sequence_runs`, immutable settings/source hashes, timestamps, status, cancellation, heartbeat and artifact references. Foreign keys use restricted deletion for dependencies; existing migrations are unchanged.
- Store artifacts under generated run UUIDs in `STUDIO_DATA_DIR/tokenizers/` and `STUDIO_DATA_DIR/sequences/`. PostgreSQL contains metadata; filesystem paths never come from browser input.
- Extend the existing preparation-worker scheduler under its global advisory lock: one dataset/tokenizer/sequence preparation task at a time across API processes. Reuse staging, atomic publication, heartbeat recovery and cancellation conventions.
- Execute native BPE fitting in a dedicated child process. The parent polls cancellation/heartbeats, terminates the child on cancellation/shutdown and escalates to kill after a bounded grace period. Never pass database credentials to the training child or report fabricated in-training progress.
- Queued jobs survive restart. Expired running jobs fail with retry guidance; retry starts a new run and never claims to resume half-trained BPE state.
- Sample limits: 20 MiB reviewed text, 10,000 records, 2,000,000 content tokens per sequence run before boundary insertion/padding, 256 MiB generated sequence artifacts. Require at least 512 MiB free storage before starting. Exceeding a limit fails clearly; no silent truncation or sampling.
- Limits and corruption checks apply server-side. Validate encoded-token/output limits while writing; clean unpublished staging on failure and keep all prior outputs intact.
- Record hashes, special IDs, actual vocabulary, library/pipeline versions, labels policy, source grouping, counts, requested sequence length and empty-split warnings in manifests. Verify reload and round-trip before publishing tokenizer artifacts.

## Implementation order and file responsibilities

1. **Contracts and migration:** add `backend/app/tokenizers/schemas.py`, migration 004 and matching `frontend/src/types/tokenizers.ts`. Tests cover eligibility, project isolation, settings and deletion dependencies.
2. **Tokenizer core:** add `backend/app/tokenizers/pipeline.py` and `train_process.py`; use `train_from_iterator` over verified training documents. Test train-only fitting, byte coverage, literal special spellings, exact round-trip and save/reload.
3. **Durable jobs/API:** add tokenizer router/storage/job helpers; integrate scheduling in the existing dataset worker and register routes in `backend/app/main.py`. Test cancellation during native fitting, immutable snapshots, restart/retry and publication failures.
4. **Tokenizer UI:** add `frontend/src/components/Tokenizer.tsx` and API adapter; wire the existing sidebar destination in `App.tsx`. Deliver a working training/details/playground workflow before adding sequence generation.
5. **Sequence core/API:** add `backend/app/tokenizers/sequences.py` and sequence routes; reuse the same verified document loader and saved tokenizer. Test tails, labels, split/document isolation and token reconstruction.
6. **Sequence UI and downloads:** add sequence configuration, status, previews and bundle downloads inside Tokenizer. Explain why the existing single-PDF corpus has empty validation/test outputs.
7. **Verification and documentation:** update README/remaining roadmap and add verification notes/screenshots. Mark M4A/M4B complete only after their actual tests and browser flows pass.

Keep feature tests in `backend/tests/test_tokenizers_api.py`, `backend/tests/test_tokenizer_pipeline.py`, `backend/tests/test_sequence_pipeline.py` and adjacent frontend `*.test.ts` files. Do not refactor unrelated project/environment screens.

## Acceptance checks

- Latest eligible reviewed version is selected even when a newer unreviewed version exists; missing/empty training data blocks submission.
- A validation-only unique marker is absent from the fitting input; validation/test are encoded using the saved training tokenizer. No JSON metadata becomes training text.
- Bangla, English, mixed text, emoji, decomposed Unicode, punctuation, joiners, whitespace and literal reserved spellings round-trip unchanged. Special IDs remain fixed after reload.
- A PDF's page-spanning example remains ordered within one document, with no artificial BOS/EOS at page breaks.
- Sequence lengths at `L-1`, `L`, `L+1` and multiple-block boundaries preserve all tokens. Singleton tails are repaired as specified; padding is masked and no sample has zero next-token targets.
- Reconstruct every source token stream from non-overlapping, unpadded sequences. Distinct documents/splits remain isolated; labels are unshifted and padding uses `-100`.
- Check cancellation, child cleanup, checksum mismatches, disk/output-limit failures, multiple tabs, restart persistence, cross-project access and dependency-protected deletion.
- Run pytest, Vitest and the production build; use isolated PostgreSQL for backend/browser tests. Browser flow: reviewed dataset → train → reload tokenizer → encode/decode → generate → inspect/download. Verify mobile layout and preserved source artifacts.

## Deliverable

A saved, reloadable tokenizer and an audited sequence bundle suitable for the later model smoke test. This proves the preparation pipeline on a small corpus; it does not establish model quality or start model training.
