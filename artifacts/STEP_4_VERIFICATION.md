# Step 4 — Tokenizer and Sequence Verification

Verified: 2026-11-14 (Asia/Dhaka).

## Implemented

- Reviewed-version eligibility, newest eligible default, immutable source/settings snapshots and checksum/provenance/split validation.
- Byte-level BPE fitting on training documents only; fixed special IDs, full byte alphabet, no additional normalization and literal reserved-spelling preservation.
- Saved tokenizer/config/special-token files; exact encode/decode inspection with paginated IDs, pieces, offsets and measured counts.
- Source-isolated, non-overlapping sequence blocks with per-document BOS/EOS, singleton-tail repair, padding masks, unshifted labels and `-100` padding labels.
- Split/token-stream/manifest exports and complete ZIP bundles with the exact tokenizer; empty evaluation splits are explicit.
- PostgreSQL migration 004 and durable queues, shared global worker serialization, cancellable credential-free native child processes, expired-lease recovery and dependency-safe deletion.

## Automated validation

Results: **69 backend tests passed, 26 frontend tests passed**, production TypeScript/Vite build passed, and `pip check` reported no broken requirements. An existing Starlette/httpx deprecation warning remains.

```bash
.venv/bin/python -m pytest -q --tb=short
npm test --prefix frontend
npm run build --prefix frontend
.venv/bin/python -m pip check
```

New checks exercise train-only fitting, validation markers, Bangla/English/emoji/decomposed-Unicode/joiner/literal-special round-trips, fixed IDs and save/reload; exact token reconstruction across block boundaries; document/split isolation, masks, labels and resource limits; API validation, project isolation, checksum failures, cancellation terminating a native child, queued persistence, expired leases, immutable retries, bundle integrity and dependency-protected deletion. Prior dataset/version tests continue to pass.

## Browser validation

Headless local Chrome tested the built UI against a dedicated temporary PostgreSQL database and generated reviewed PDF. Verified selection of reviewed Version 2 despite newer unreviewed Version 3; real CPU fitting; exact Bangla/emoji/literal-special round-trip; token pagination; real sequence generation and ZIP download; empty validation preview; refresh persistence; blocked deletion with dependent sequences; 390px mobile layout without horizontal overflow; zero JavaScript page errors. The isolated server/database were removed afterward.

- [Tokenizer desktop](tokenizer-desktop.png)
- [Sequence exports and preview](training-sequences-desktop.png)
- [Tokenizer mobile](tokenizer-mobile.png)

The live corpus's reviewed Version 3 was read-only validated as one document containing 27 ordered pages. No source records were modified or model training started. Test tokenizers/sequences were generated only in isolated fixture storage.

## Boundaries

This is bounded data preparation, not a full-corpus training run or a model-quality claim. Native fitting exposes stage/elapsed time, not merge percentages. The future model/loss owns the one causal target shift, and its context/vocabulary configuration must match these exports. `documents.tokens.jsonl` is the authoritative full-document token stream; isolated byte-block decoding can split a Unicode character at a block boundary.
