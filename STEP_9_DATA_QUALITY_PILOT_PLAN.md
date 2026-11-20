# Step 9 — Data Quality Review and Controlled Pilot Plan

Status: **Draft; execution and human/domain review pending.**  
Date: 20 November 2026, Asia/Dhaka.

## Goal and starting evidence

Decide whether a narrowly scoped next pilot is justified, after checking training-source quality and the independence of evaluation data. Preserve the Step 8 baseline and document the decision even if no pilot is run.

The existing pilot trained on seven blocks for three epochs. Its external loss decreased from 6.9118 to 6.7999 over checkpoints 7/14/21, but all 36 fixed-prompt continuations contained only newline characters. This is evidence of poor output on those probes, not proof of the cause. The external corpus has two documents and is dominated by one of them. PDF inspection found Bangla extraction discrepancies and a linearized table. See [Step 8 review](artifacts/STEP_8_EVALUATION_REVIEW.md).

## Boundaries and safeguards

- Keep the original PDF, baseline dataset version, tokenizer, sequences, configurations, checkpoints, prompt set and reports unchanged. Publish corrections as a new version with provenance.
- Keep the two Step 8 OM-A documents evaluation-only for any model compared using them. Their technical review is not domain approval, and existing overlap checks do not prove semantic independence.
- Reserve separate, permission-compatible documents as a final test set before iterative tuning. Record their identity and lineage; do not inspect them for checkpoint selection or fit a tokenizer/model on them. No dedicated reserved-test enforcement exists yet, so this is a documented manual control.
- Human/domain review, permissions, available compute budget and acceptance thresholds remain open decisions; do not invent approvals or silently label documents independent.
- Do not launch training, change production data, or mark this plan complete solely because a plan exists.

## 1. Review the sources

1. Compare each original PDF page with its extracted text, recording page, issue, correction and reviewer. Prioritize the known page 1 spellings and page 14 table associations; inspect all 27 pages before claiming a complete review. Preserve intended paragraphs and tables.
2. Have a domain reviewer assess the corrected text and the two held-out OM-A documents for meaning, source edition, permission and potential overlap or shared lineage. Record reviewer, date and unresolved issues. Technical checks can assist but cannot replace this review.
3. Classify additional candidate documents by source, permission, lineage and intended role: training, iterative evaluation, final test, or excluded. Check exact matches and meaningful near-duplicates across roles. Do not assign related versions or pages to different roles.
4. Publish a new reviewed training version only after corrections are checked; record its ID, parent, change summary and artifact hashes. If no corrections are needed, record the review and retain the existing version.

**Gate:** unresolved material extraction, permission or leakage concerns block any claim that the data is ready. If a reviewer or suitable independent documents are unavailable, record the gap and stop the dependent work.

## 2. Diagnose newline-only output

Using saved artifacts and bounded, read-only analysis, inspect source newline distribution and document boundaries, tokenizer encode/decode and special-token mappings, prompt/token IDs, generation settings, padding/masks and a few next-token probabilities at the same checkpoints. Compare the observations with existing numerical tests and training/evaluation configuration. Preserve the original outputs and record findings separately.

A high newline frequency or a low loss alone does not establish the cause. If there is evidence of a code or data defect, define and verify a targeted fix before interpreting a training experiment; keep any corrected artifacts versioned. If no defect is demonstrated, record the hypothesis as unresolved.

## 3. Choose one controlled comparison

Choose the variable only after source review and diagnosis. Record the hypothesis, expected signal, control, candidate, fixed settings, resource ceiling, stop conditions and decision thresholds **before** execution.

- **Duration candidate:** if the existing source is accepted for a diagnostic, compare a new random-initialized 10-epoch / 70-update pilot against the original three-epoch lineage, keeping source, tokenizer, architecture, seed and optimizer fixed. Resume is not used to extend a completed run. This isolates duration but does not correct known data issues.
- **Corrected-data candidate:** if corrections matter, first establish a control and candidate with the same frozen tokenizer, architecture, seed, optimizer and training schedule, provided the corrected source is compatible with the existing pipeline. Change the dataset version only. If a new tokenizer is needed, treat that as a separate comparison series: token-level loss and perplexity across tokenizers are not directly comparable.
- **No-run decision:** if data quality, independence, runtime readiness or the budget is unresolved, document the blocker and defer the experiment.

The two options answer different questions. Select one; do not combine duration, corpus, tokenizer and architecture changes in the same causal comparison. Verify whether current pipeline constraints permit the selected comparison before creating artifacts.

## 4. Budget, run and evaluate

Before starting, confirm a concrete CPU/GPU time and disk ceiling with the owner, runtime readiness, checkpoint retention, available space and cancellation procedure. CPU is verified for bounded work; CUDA remains unverified. Set a maximum runtime and stop for nonfinite loss/gradients, integrity failures, budget exhaustion or cancellation. Never infer GPU capacity from hardware detection.

If the gate passes and the run is authorized:

1. Save immutable source/config/tokenizer references, seed, runtime versions, hashes, budget and experiment hypothesis. Run the bounded pilot and retain metrics, coverage and checkpoints.
2. Evaluate control and candidate with the same frozen external version, prompt bytes, decoding settings and block protocol; export each report. Compare runs manually because the current UI compares checkpoints within one run. Evaluate equivalent checkpoint selection rules, fixed in advance.
3. Report target-weighted external loss, block/target counts and train diagnostics, alongside generated text, newline repetition and other observed failure modes. Do not treat perplexity as accuracy. Keep original empty validation/test splits marked unavailable.
4. Have a human/domain reviewer inspect outputs and source agreement, recording criteria, reviewer and limitations. Do not claim generalization or factual accuracy from this small corpus.
5. Record actual time, resource use, integrity checks, result against the predeclared thresholds and the decision to stop, revise data, run a further controlled test or plan scale-up. Use the untouched final test only after model selection and its protocol are agreed.

## Deliverables and acceptance

- Page-level source review and correction log, including domain approval or explicit unresolved issues.
- Dataset role/lineage and permission inventory; frozen iterative evaluation and separately reserved final-test identities where available.
- A diagnosis note distinguishing observed facts, hypotheses and defects.
- A pre-run experiment card with a single variable, control, comparison protocol, limits and acceptance thresholds, or a documented no-run decision.
- If executed, saved run/evaluation IDs, hashes, metrics, human review, resource use and a reproducible decision report. Update [remaining work](REMAINING_WORK_PLAN.md) only after verification.

Step 9 is complete when these reviews and the experiment decision are recorded, with any approved pilot evaluated and its limitations stated. If required review, data or budget is unavailable, mark the affected work pending rather than complete. Fine-tuning and full-scale training require separate plans and decisions.

## Open decisions

1. Who will perform and approve aviation/domain and permission review?
2. Which additional documents are eligible for training and for an untouched final test?
3. What time, compute and disk budget is acceptable, and what thresholds would justify another pilot or scaling?
4. After the review and diagnosis, which single comparison should be run, if any?
