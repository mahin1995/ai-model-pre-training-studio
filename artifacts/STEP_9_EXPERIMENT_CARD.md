# Step 9 — Candidate duration pilot

Status: **Prepared, not run.** This is a diagnostic proposal, not a claim of model readiness.

- **Hypothesis:** additional training on the unchanged tiny corpus changes the model's loss and greedy continuation behavior. It may remain newline-only or overfit; neither outcome identifies source quality as the cause.
- **Control:** original pilot `09f2260f-9ed6-4b3d-a2f7-1cade911511a`, step 21, configuration and source identities in [Step 8 review](STEP_8_EVALUATION_REVIEW.md).
- **Candidate:** new random-initialized 10-epoch CPU pilot, 70 updates, same seven blocks, sequence/tokenizer, seed 42, architecture, optimizer, learning rate, precision and batch size. Only duration changes; no resume. Current `checkpoint_steps(7, 10)` produces 21/35/56/70. Compare candidate step 21 against original step 21 for repeatability, then candidate 70 versus candidate 21.
- **Measures:** frozen 12 prompts, greedy 32-token limit and saved external corpus `2e1ad2ca-d81e-465f-b4fe-59fcd54c74ab`, identical scoring/tokenizer and block protocol; record target-weighted external loss, counts, newline-only continuations, train diagnostics and representative raw token IDs. External data remains evaluation-only; it is small and not domain approved.
- **Prerequisites:** complete relevant source review; confirm rights and safe runtime; agree time/disk limits and thresholds before execution. Known extraction discrepancies mean this duration test cannot assess corrected data. Original dataset, tokenizer, checkpoints and outputs remain intact. The separately reserved final test is not used.
- **Stop:** nonfinite loss/gradient, failed artifact integrity, timeout/resource ceiling, or cancellation. Retain error and coverage rather than reporting a partial run as complete.
- **Decision:** compare step 21 reproducibility and predeclared limits, then record whether loss and prompt outputs change; do not infer quality, accuracy or broad generalization. Exact acceptance thresholds and budget remain unspecified, so execution is pending.

The app's sequence route binds a sequence to its tokenizer run's original source snapshot; it cannot presently generate corrected-version sequences using that existing tokenizer through the exposed flow. A corrected-data-only experiment needs a separate provenance-safe design and verification; do not bypass the snapshot checks.
