# Step 9 — Newline diagnosis and source review

Date: 20 November 2026. Status: **Diagnostic checks completed; full page-by-page transcription comparison pending.**

## Reproduction

Re-run from repository root with `.venv-training/bin/python artifacts/step9_diagnose.py`. It reads the Step 8 baseline bundle, frozen tokenizer, prompt set and sequence records; checkpoint files are extracted to a temporary directory and it writes `/tmp/studio-step9-diagnosis.json`. The saved output of this run is [STEP_9_DIAGNOSIS.json](STEP_9_DIAGNOSIS.json). No training job or weight mutation occurs.

- All 12 prompts at each of checkpoints 7, 14 and 21 reproduced 32 consecutive newline IDs, 36/36 total.
- At each checkpoint and prompt, direct uncached forward-pass greedy argmax with PAD/UNK/BOS suppressed agreed with cached `generate` for the all 32 generated tokens (36/36 comparisons). This does not exhaustively prove all inference paths correct.
- For the final training block at all three checkpoints, library causal loss matched independently calculated shifted cross-entropy with ignored padding (absolute difference 0.0 at displayed precision).
- The saved sequence has 6,661 real IDs including boundaries; newline ID 202 occurs 776 times (11.65%). There are 402 runs of one newline and 187 runs of two; no longer run in the concatenated exported real IDs. In contrast, greedy output repeats it 32 times. This establishes an observed distribution difference, not a causal explanation.
- Source tokenization and label masks were inspected; existing tokenizer pipeline tests passed: `.venv/bin/python -m pytest -q --tb=short backend/tests/test_tokenizer_pipeline.py` (2 passed; one dependency deprecation warning).

These checks did not establish an inference or loss implementation defect. They show the immediate selection comes from the model's logits under greedy decoding. Do not apply a newline suppression patch as a causal fix. Additional diagnosis, including evaluation after a controlled change, may still reveal issues.

## Source observations

All 27 PDF pages were rendered and visually inspected for layout. The 27 corresponding saved version 3 records were identified; text presence or viewing a rendering alone is not a full transcription comparison. Paired spot checks identify:

| Page | Saved extraction | Visually observed source | Status |
| --- | --- | --- | --- |
| 1 | `হললো`, `ককোননো` | `হলো`, `কোনো` | Transcription discrepancies, already noted in Step 8. |
| 3 | `কররো` in numbered steps | `করো` | Four saved occurrences; correction proposed, not published. |
| 11 | `ভাললো` | `ভালো` | Correction proposed, not published. |
| 22 | `কোননো` | `কোনো` | Correction proposed, not published. |
| 14 | Two-column table linearized with wrapped rows | Two distinct rows associating terms with meanings | Preserve associations in a reviewed correction; extraction's wraps need careful checking. |

A literal scan also found `ককোননো` on page 2, `কররো` on page 4, and zero-width spaces in a number of records. These are candidates for paired review; zero-width characters alone are not proof of an error. Many pages have tables, multi-line headings and page-spanning text. Complete side-by-side comparison of all saved text and a reviewed correction diff remain outstanding; no corrected version has been published, and aviation/domain approval is not implied.

## Next comparison

See [experiment card](STEP_9_EXPERIMENT_CARD.md). Existing 10-epoch checkpoint scheduling yields steps 21, 35, 56 and 70. Current sequence creation inherits the tokenizer's source snapshot, so it does not offer a corrected-dataset/same-tokenizer comparison via the existing API. That comparison requires a separately designed provenance-safe capability, not a bypass.

## Follow-up: full-page extractor comparison and correction draft

The exact saved version 3 records were compared page by page with a separate `pdftotext -layout` extraction of the original PDF (SHA-256 `1545d04b185d7308cd3709db63dec13f0ba001378674607768956fbc76904d69`). After NFC normalization, whitespace folding and ignoring zero-width spaces, automated comparison identified duplicated Bengali characters on pages 1, 2, 3, 4, 11, 22 and 26. Both extractors can share errors, and normalization hides layout differences; their agreement is not proof of complete transcription accuracy. All pages were rendered for layout inspection; a line-by-line visual transcription audit and domain review remain pending.

A draft under the ignored `data/assessments/step-9-2026-11-20/` folder applies 14 targeted replacements, preserving all 27 page IDs and every non-text metadata field. Its correction list and page comparison are saved beside it. After those replacements, 26 pages match the alternative extraction under the normalization above; page 25 differs by one space. Tables on pages 3, 5, 7, 9, 11, 12, 14 and 22 still require detailed association review; identical linearized text does not validate row/column relationships. This is a review draft only, not a published dataset version or an approval of its contents.

The local API was unavailable at the time of this check. No training run, reviewed dataset publication or model changes were made.
