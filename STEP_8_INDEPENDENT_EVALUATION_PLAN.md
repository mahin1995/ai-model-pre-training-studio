# Step 8 — Independent Evaluation and Data Expansion Plan

Status: **Baseline and external Markdown evaluation executed on 20 November 2026. Human/domain review remains pending.**

Evidence: [Step 8 review](artifacts/STEP_8_EVALUATION_REVIEW.md). Twelve fixed prompts were compared across three live checkpoints; backups and source/checkpoint integrity were verified. The user subsequently supplied `doc/` Markdown files; two technically reviewed OM-A documents were scored as an external corpus (28 blocks). No model/tokenizer training or original source edits were made. The sections below retain the original assessment plan.

Date: 19 November 2026, Asia/Dhaka.

## 1. Verified starting point

Read-only PostgreSQL inspection found completed live pilot runs in project **mahin**. The local HTTP API was unavailable during this inspection; saved database records were inspected without starting the server.

| Item | Observed result |
| --- | --- |
| Original pilot | `09f2260f-9ed6-4b3d-a2f7-1cade911511a` |
| Linked resumed pilot | `e916e14b-69fb-44cd-9847-4b050decb41e` |
| Coverage | All 7 train blocks, 3 completed epochs, 21 total updates |
| Supervised targets | 6,654 per epoch; 19,962 exposures across three epochs |
| Reload/gradients/weights | Reload matched; finite gradients and changed weights reported |
| Initial → final all-train loss | 7.0591 → 6.1099 |
| Original checkpoint evaluation | Step 7: 6.5473; step 14: 6.3319; step 21: 6.1099 |
| Evaluation scope observed | Training diagnostics; no independent evaluation attached to either pilot |

The resumed child starts at step 7 and finishes at the same total step 21 and final loss. These are three epochs across the lineage, not six epochs or additional independent training evidence.

The pilot tooling and live coverage work. The next question is whether the saved model predicts **independent text**, and what data/training changes the result supports. Lower loss on the original PDF alone cannot answer that question.

## 2. Goal and scope

Use existing **Datasets → Review & Correct → Evaluation → Playground** features to establish a reproducible independent baseline before increasing training or planning instruction fine-tuning.

Expected outputs:

1. One frozen baseline training run/checkpoint and downloaded bundle.
2. A reviewed independent evaluation corpus with documented provenance.
3. One saved prompt-set version and comparable checkpoint results.
4. A short human review and an evidence-based next-run decision.

This is primarily an **execution and assessment phase**. Existing UI/API already implement external frozen-tokenizer evaluation, prompt versions and annotations. No new screen, migration, dependency or duplicate evaluation pipeline is required for this plan. Fix concrete gaps only if execution reveals them.

## 3. Freeze the baseline and review source quality

- Use the original completed pilot for the first comparison: it contains checkpoints **7/14/21** from one run. Keep the linked resumed run as recovery evidence.
- Download **Complete training bundle**, manifest and metrics. Verify registered download checksums when executing; this planning inspection did not rehash stored checkpoint files.
- Record dataset version, tokenizer/sequence IDs, model config, seed, runtime, context and checkpoint hashes. Use the saved tokenizer for every evaluation of this baseline.
- Review source spelling, Bangla extraction and tables. If corrections are necessary, publish a new reviewed dataset version and generate its own tokenizer/sequences/config for a new training experiment. Keep the baseline chain intact.

A future model trained with a different tokenizer can have separate results, but raw NLL/PPL values from different tokenizations must not be treated as directly comparable.

## 4. Prepare independent evaluation documents

Input needed: separate, permission-compatible documents relevant to the intended domain. Start with a small corpus within the existing **256 evaluation-block** limit; document independence matters more than a page-count target.

- Upload independent TXT/JSONL/PDF content into the same project, review extraction and publish a reviewed version using the existing workflow.
- Do not use pages or reuploads from the original PDF. A different filename or file hash alone does not establish independent content.
- Check shared quotations, copied passages, repeated rules and related document editions. Existing exact-overlap checks block known overlaps; manually inspect possible near-duplicates.
- Keep a written record that the chosen version is evaluation-only for these experiments. Do not later add those documents to the candidate's training/tokenizer corpus while continuing to call the evaluation held-out.
- In Evaluation, choose **Independent reviewed external corpus**. The checkpoint tokenizer encodes this text without fitting or changing vocabulary. This evaluation role applies even if the external dataset's preparation export calls its records `train`.

If independent documents are not available, complete only the qualitative/train-diagnostic review and record independent evaluation as **Not available**. Do not create an artificial held-out set by splitting this PDF's pages.

## 5. Run checkpoint and prompt evaluation

### Numerical comparison

Select the original pilot's checkpoints **7, 14 and 21**, one reviewed external version and identical settings. Save the resulting report, source IDs and hashes.

Report token-weighted loss, block perplexity, document/block count and supervised target count using existing **block-based NLL/PPL v1**. Keep original full-train loss alongside the external metric. Padding and each independent block's unpredicted first token remain excluded.

Empty validation is unavailable, never zero. Perplexity is not accuracy; do not use the current training perplexity as evidence of independent performance. If loss is nonfinite or perplexity overflows, preserve the explicit result/error and investigate before interpreting it.

### Qualitative comparison

Save one immutable prompt-set version with **10–15 short completion prompts**, within the current 20-prompt cap. Cover Bangla, relevant English/mixed text, numbers, punctuation and representative domain phrasing. Review prompts for context fit.

- Use the same prompt bytes, greedy decoding and output limit across checkpoints. Default to 32 new tokens when the context budget permits.
- Use continuation prompts rather than assuming this base model follows chat instructions.
- Inspect readable characters, repetition, language consistency and agreement with the source. Save the existing manual annotations and reviewer notes.
- Reviewer context and source agreement are human judgments; do not invent an automatic factual-accuracy percentage.

Playground can reproduce individual examples. Keep numerical reports, generated text and human notes distinct.

## 6. Decide the next experiment

| Observation | Next action |
| --- | --- |
| Corrupt extraction or wrong source versions | Correct/publish new data and rebuild the affected training chain |
| Training loss decreases while external loss worsens | Record evidence of overfitting; inspect earlier checkpoints and improve/diversify training data |
| Training and external results remain poor | Review corpus, learning behavior and model/data limits; plan one controlled change |
| Repetitive/unreadable completions | Check source/tokenizer integrity and inspect multiple prompts; distinguish base-model limitations from pipeline failures |
| Stable results with usable independent evidence | Plan a controlled next pilot and document its hypothesis/budget |
| Independent evidence unavailable | Keep quality conclusions provisional; prioritize independent documents |

If a same-corpus longer pilot is justified, a **new immutable 10-epoch config** is a possible bounded experiment: with seven blocks it derives 70 updates. Keep architecture, tokenizer, source and seed fixed to isolate training duration. Start from random weights under current pilot semantics; do not extend a completed run through Resume. Do not automatically launch this experiment merely because the option exists.

The current Evaluation UI compares checkpoints from one run. Evaluate separate runs against the same frozen corpus/prompt version and compare their exported reports manually; cross-run UI comparison would be a separate feature request. Avoid searching many settings against a tiny evaluation corpus.

For broader training-data expansion, collect diverse independent documents, review permissions/extraction and group by document lineage before splitting. Fit any new final tokenizer only on the new training split. Reserve an untouched final test corpus before repeated tuning; the dedicated reserved-test workflow remains future work.

## 7. Acceptance and deliverables

Save `artifacts/STEP_8_EVALUATION_REVIEW.md` after execution with:

- Frozen baseline run/checkpoint/config/source/tokenizer/runtime IDs and verified artifacts.
- Independent corpus version, provenance, manual independence checks and any overlap rejection.
- Checkpoint table showing training/external loss, metric protocol and actual target counts.
- Prompt-set version, generation settings, examples and exported human annotations.
- Explicit unavailable metrics, remaining data-quality issues and the chosen next experiment with its rationale.

This assessment is complete when the available evidence and its limits are recorded and the next action is justified. The model does not need to produce good text for the assessment to be valid. A missing independent corpus leaves the independent-evaluation portion pending.

Use existing tests/builds if code changes become necessary, with temporary PostgreSQL/artifacts for integration tests. A documentation-only plan does not require rerunning training tests or starting a live job.

## 8. Following phase

After the assessment, choose between corrected/expanded pre-training data, another bounded pilot or a larger runtime/model budget. Fine-tuning preparation follows when there is a selected base checkpoint and a clear task: permission-compatible instruction/response data, independent splits, a saved template and assistant-response loss masking need their own plan. The current Fine-tuning screen remains future work.

Related: [whole-dataset pilot plan](STEP_7_WHOLE_DATASET_PILOT_PLAN.md), [pilot verification](artifacts/STEP_7_VERIFICATION.md), [Evaluation/Playground plan](STEP_6_EVALUATION_PLAYGROUND_PLAN.md), [roadmap](REMAINING_WORK_PLAN.md).
