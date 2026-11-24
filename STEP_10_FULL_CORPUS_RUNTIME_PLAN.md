# Step 10 — Full corpus and training runtime

Covers remaining M8 and M9 work. Continue from the [Step 9 quality pilot](STEP_9_DATA_QUALITY_PILOT_PLAN.md). Build and verify with fixtures while awaiting the real inputs.

## Inputs

- Scope for the first release: Bangla and mixed-language aviation document study with source-backed answers.
- Corpus inventory with source lineage, document revisions, usage permissions and a named reviewer. Finish the PDF correction and review gate before publishing an approved corrected version.
- Target training machine, sustained compute time, storage and cost ceilings, and a recorded stopping policy.

## Work

1. Freeze the corpus inventory. Assign reviewed sources to train, validation and final test by document family. Keep related versions, pages and near-duplicates together. Define a separate development prompt set and hold final test out of all training and checkpoint selection.
2. Scale import and preprocessing to the agreed corpus bounds. Measure CPU time, memory and disk on a representative batch before increasing existing limits. Verify deduplication, split reproducibility, and provenance. Record the tokenizer's training split and publish checksummed packed sequences and coverage counts for each split.
3. Install the pinned training runtime on the target machine. Run a small CUDA forward/backward and checkpoint reload when GPU is the selected target. Record device/runtime versions, memory, throughput and checkpoint disk use. Keep the verified CPU fixture path available for development.
4. Use the measured supervised tokens per second to estimate full-run time, and include evaluation and checkpoint overhead. Choose model dimensions, context length, training budget and retention settings within measured limits. Run a target-configuration smoke test with finite gradients and reproducible reload/resume.

## Exit criteria

Publish the corpus, tokenizer and sequence manifests with hashes, split counts and source approvals. Record the target runtime probe, model configuration, smoke-test report and budget. Carry unresolved source rights, review and target-device access as concrete blockers to the real run.
