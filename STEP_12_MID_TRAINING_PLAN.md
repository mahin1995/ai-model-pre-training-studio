# Step 12 — Optional mid-training

This is the conditional bridge from M10 to M11 in the [use-case plan](MID_TRAINING_FINE_TUNING_PLAN.md). A qualified base can go directly to [Step 13](STEP_13_SUPERVISED_FINE_TUNING_PLAN.md). Record the decision using development evaluation.

## Implementation status

Sequence generation can now select a reviewed corpus version while reusing a saved tokenizer. The manifest records the corpus version and tokenizer fit source separately. Model source snapshots retain both sources for permission and held-out overlap checks. The mid-training executor and its stage-specific checkpoint lineage still need implementation.

## Work

1. Choose a measurable domain gap, such as weak aviation terminology completion on held-out development documents. Set a budget, a target improvement and a general-language regression threshold before running.
2. Add the frozen-tokenizer preparation path for a separate reviewed domain dataset. Validate tokenizer and checkpoint compatibility, source permissions, split provenance and artifact hashes. Keep final-test document families outside all training.
3. Add an explicit mid-training stage initialized from the selected parent's weights with a fresh optimizer and scheduler. Reuse causal next-token training and job lifecycle machinery. Record parent, corpus and runtime identities. Exact resume within this stage restores the same run state.
4. Compare the result against the original base under fixed settings. Carry eligible checkpoints into SFT so it can compare direct SFT against the optional route using identical SFT data and settings.

## Exit criteria

Run a fixture through frozen-tokenizer encoding, training, exact resume and checkpoint reload. Reject incompatible artifacts and cross-project inputs. For a real run, publish a domain and general-language comparison and record whether the extra stage earns its place. If the evidence favors direct SFT, record why the optional run was skipped.
