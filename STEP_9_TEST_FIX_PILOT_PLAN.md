# Step 9 — PDF Review, Newline Diagnosis and Pilot: Test and Fix Plan

Status: **Proposed; execution has not started under this plan.**  
Date: 20 November 2026.

## Objective and baseline

Review all 27 PDF pages against the actual saved training extraction, diagnose the newline-only generation, fix defects supported by evidence, and prepare one reproducible small pilot. Preserve the original source and Step 8 baseline. Domain approval, document rights and the final-test corpus are separate outstanding decisions; technical review does not substitute for them.

Baseline: original pilot checkpoints 7/14/21; seven training blocks, three epochs, seed 42. All 36 fixed-prompt outputs were 32 newline tokens. External loss improved 6.911798 → 6.799943 on two documents using the frozen tokenizer. Newline was the top next token for two inspected prompts, which explains the immediate greedy choice but not its underlying cause. See [Step 8 review](artifacts/STEP_8_EVALUATION_REVIEW.md) and [Step 9 progress](artifacts/STEP_9_REVIEW_PROGRESS.md).

## 1. Inspect and correct PDF extraction

1. Identify and hash the exact PDF and saved version 3 extracted text, including page mappings. Render each original page at readable resolution and display its matching saved text; use bounded page batches. Confirm that comparison uses the text actually supplied to training, not merely a fresh alternative extraction.
2. Visually compare every page for missing or duplicated text, Bangla characters, numbers, reading order, headings and table row/column associations. Record one row per page in `artifacts/STEP_9_PAGE_REVIEW.md`: page, checked status, observed text, source reading, issue category, proposed correction, confidence and unresolved items. A page is checked only after visually comparing both; unreadable pages and uncertain domain meanings stay open. Recheck known page 1–2 spellings and page 14 table.
3. Verify proposed transcription against the rendered source, without rewriting domain rules or silently normalizing meaningful paragraphs. Retain all corrections in a reviewable diff. Test that corrected output preserves page order, document grouping, line and table meaning, Unicode and original provenance. Keep the original and existing version untouched.
4. If corrections are supported, use the existing Review & Correct workflow to create a new immutable version only once its prerequisites and permissions are satisfied; record parent/version IDs, checksums and correction log. Otherwise retain the proposed diff and explicitly record what blocks publication. Do not call an assistant's review domain approval.

**Exit evidence:** all 27 pages accounted for, with issues and uncertainties recorded; any published version independently reloaded and checked against the reviewed diff and original hashes.

## 2. Reproduce, test and fix newline generation

1. Reproduce the saved baseline with the original checkpoints, frozen tokenizer and all 12 fixed prompts. Capture prompt IDs, generation parameters, top-k next-token probabilities and generated IDs for steps 7/14/21, including after the first and subsequent newline tokens. Compare a cached greedy pass with an uncached forward pass under identical inputs. Preserve settings and artifacts; sampling or newline suppression may be diagnostic only and must not replace the baseline.
2. Quantify newline frequency, consecutive-newline runs and newline contexts in actual training token IDs; compare them with extracted text and block boundaries. Check BOS/EOS/PAD/UNK mappings and tokenizer round trips. Account for document boundaries and excluded padding.
3. Verify checkpoint/config/tokenizer identity, token/position alignment, all-ones prompt mask, right-padding masks and causal-label shift against the model's loss. Compare library generation with a direct forward-pass argmax using the same suppression and context. Use isolated fixtures with known expected IDs/loss and reload checkpoints when needed. Review `backend/app/inference/core.py`, `backend/app/training/data.py`, `backend/app/training/core.py` and `backend/app/tokenizers/sequences.py` as applicable.
4. For each hypothesis, record the observation, discriminating test and result. If a reproducible code defect is found, add a regression test that fails before the smallest targeted fix and passes after it; run relevant existing tests. If source extraction is responsible, fix it through the versioned correction workflow. If no defect is demonstrated, record the unresolved hypothesis and avoid claiming newline frequency alone proves causation.

**Exit evidence:** a diagnosis report with reproducible commands, checkpoint/prompt identities, observations and limits; any fix accompanied by relevant regression and integration results. Do not modify saved outputs or checkpoints.

## 3. Prepare one controlled pilot

Select the comparison after steps 1–2, and record the choice and justification before running. Preferred first experiment **if the existing source can be used for a diagnostic and no pipeline defect remains**: a duration comparison using the original tokenizer, dataset version, architecture, seed, optimizer, batch size and evaluation settings. Start a separate random-initialized 10-epoch pilot (70 updates at seven blocks/epoch); compare its checkpoint at step 21 with the original step 21 to check reproducibility, then compare its step 70 with its step 21. Do not resume the completed run. Confirm the current checkpoint policy actually saves the needed steps; if not, record a compatible policy before execution, with no change to training semantics.

If the review instead identifies a material source defect whose correction is the intended variable, prepare a separate corrected-data comparison: control and candidate must use the same frozen tokenizer, model, seed, schedule and evaluation protocol, with only the dataset version changed. **First verify that the application's provenance and sequence pipeline permit a corrected version to use the existing frozen tokenizer.** If they do not, do not bypass integrity checks; record the limitation and define a separate experiment. Different tokenizers make raw token-level loss/PPL unsuitable for direct comparison.

Before any pilot, write `artifacts/STEP_9_EXPERIMENT_CARD.md` with hypothesis, expected observation, single variable, exact control and candidate IDs/configs, prompt-set and external-corpus IDs, checkpoint selection, time/disk budget, cancellation and stop conditions, and measurable decision thresholds. Default to CPU only after readiness and disk checks; CUDA remains unverified. User-defined budget and thresholds are open inputs, not facts to invent. Preserve the Step 8 OM-A corpus as evaluation-only for this comparison, and report its narrow scope and lack of domain approval.

Run only when prerequisites and budget are established. Stop for nonfinite loss/gradients, failed integrity checks, exhausted budget or cancellation. Save coverage, metrics, runtime, model and source hashes. Compare outputs using identical 12 prompts and greedy settings, and compare target-weighted external loss on the same frozen corpus and tokenization; report counts and qualitative repetition separately. Never represent perplexity as accuracy or claim broad model quality from these data.

**Exit evidence:** an executable experiment card or an explicit, evidence-based no-run decision; if run, saved reports, resource usage, numerical and prompt comparison, and a conclusion against the predeclared thresholds.

## Verification and completion

- Review log covers 27 distinct pages and explicitly identifies unresolved items; source and baseline hashes still match.
- Reproduction records exact inputs and distinguishes observation from cause. Any code change passes a meaningful regression and the relevant project tests; dataset changes pass review, reload and provenance checks.
- The pilot changes one variable, or its infeasibility is documented. Final test remains separate and unused for tuning.
- Update [Step 9 progress](artifacts/STEP_9_REVIEW_PROGRESS.md) and [remaining work](REMAINING_WORK_PLAN.md) with actual verified results only. Record domain review, permissions, budget, final-test availability and acceptance thresholds as pending until supplied.
