# Step 11 — Full pre-training and base evaluation

Covers M10. Start on the target corpus after [Step 10](STEP_10_FULL_CORPUS_RUNTIME_PLAN.md) qualifies the data and runtime.

## Implementation status

The full profile uses the existing worker queue, epoch coverage, time and disk limits, and bounded checkpoint schedule. Nonempty validation is scored at checkpoint steps after source verification. Training and validation loss are reported separately. Target-budget execution and quality-based base selection remain local acceptance tasks.

## Work

1. Extend the bounded pilot into a budgeted pre-training path. Preserve immutable run inputs, deterministic data order and checkpoint lineage. Enforce step/time/disk limits and checkpoint retention that preserves checkpoints referenced by other runs or evaluations.
2. Report training and validation loss separately, plus supervised token counts, throughput, memory, checkpoint use and sample completions. Handle cancellation, interruptions and worker recovery with registered checkpoints. Verify exact resume against an uninterrupted fixture run.
3. Freeze development prompts and the baseline protocol before training. Include Bangla, English and mixed-language completion, repetition and whitespace-only checks, and independently held-out language-model loss. Compare perplexity only under consistent tokenizer and scoring settings.
4. Run an approved target-budget training job. Evaluate candidate checkpoints on validation data, document stability and generation failures, and select a base checkpoint using the recorded thresholds. The Step 9 run remains a diagnostic reference; its longer pilot produced whitespace-only output on 11 of 12 prompts.

## Exit criteria

Publish a loadable base checkpoint and tokenizer pair, an immutable run report and the validation comparison. Checkpoint selection requires a recorded decision and a passing quality screen. Investigate failed screens in data, training or decoding before qualifying a base for later stages.
