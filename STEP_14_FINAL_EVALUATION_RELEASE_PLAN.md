# Step 14 — Final evaluation and local release

Completes M11 after [Step 13](STEP_13_SUPERVISED_FINE_TUNING_PLAN.md) produces a qualified candidate. Local document study is the release target. External serving, quantization and adapter merging are conditional on the target and require revalidation if selected.

## Implementation status

Evaluation can select the reserved test split from a checkpoint's published sequence artifact. The backend verifies the split against the frozen tokenizer and reviewed source before scoring. The final acceptance protocol, SFT candidate evaluation and release package still need implementation and execution.

## Work

1. Freeze the selected checkpoint, evaluator, decoding parameters, task rubric and acceptance thresholds. Compare the base and selected candidate once on reserved test documents and prompts. Record correctness, whether each citation supports its claim, treatment of insufficient excerpts, Bangla quality, repetition and general-language regression.
2. Record domain reviewer decisions, failure examples and data usage terms. Report aggregate scores with example counts. If the candidate fails, return to validation for iteration and reserve a fresh final test set if the failed test outputs guide revisions.
3. Integrate the selected template and checkpoint into the local Playground. Verify limits, loading, cancellation, error handling and history. Deliver streaming for the final interactive flow and measure time to first token, total latency, tokens per second and peak memory on the target runtime.
4. Package model artifacts, tokenizer, template, checksums, runtime requirements, model card and the evaluation report. Validate a fresh local install, checkpoint load, source-backed response and insufficient-evidence response using the packaged artifacts.

## Exit criteria

The final report records pass/fail against the agreed thresholds and scope. The packaged model can be restored and used on the supported local runtime. Track app verification, runtime verification and domain/model acceptance separately in the roadmap.
