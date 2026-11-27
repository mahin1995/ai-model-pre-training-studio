# Step 13 — Supervised fine-tuning

Covers the remaining M6 instruction-data workflow and M11 SFT. Uses a qualified [base checkpoint](STEP_11_FULL_PRETRAINING_PLAN.md), with [mid-training](STEP_12_MID_TRAINING_PLAN.md) as an optional comparison.

## Implementation status

Reviewed Q&A examples use the normal versioned dataset workflow. The Source Q&A sequence objective creates one answer-masked block per example. The training job requires a compatible parent checkpoint, and Playground uses the saved source Q&A template. Both parent routes ran with synthetic data; acceptance on real documents remains separate.

## Work

1. Add versioned instruction dataset import, review, preview and source-family splits. For aviation Q&A, capture the question, reviewed excerpt, expected answer, source revision and supporting clauses. Include insufficient-evidence examples and keep final-test documents and derived examples outside all training.
2. Reuse the existing `source-qa-v1` preview API as the starting point for formatting. Apply the same prompt tokens at inference. Verify that the causal shift supervises the first answer token and EOS, with prompt and padding labels masked. Reject examples that exceed the configured context budget.
3. Add configuration and UI for selecting use case, approved data, parent checkpoint and budget. Use full fine-tuning for the bounded native-checkpoint path. Add adapters only if model size and measured runtime make them necessary. Reuse the job queue, runtime checks, cancellations and checkpoint storage while recording immutable lineage.
4. Run a fixture pilot from training through reload and Playground inference. On approved data, run direct SFT first and compare with the optional mid-trained parent if qualified. Freeze decoding and evaluation inputs across candidates and select on validation scores.

## Exit criteria

Tests cover template parity, label masks, overlong examples, permissions, project isolation, and reload/resume. A real release candidate includes the model or adapter with required parent identity, tokenizer, prompt template, reviewed data version and validation report.
