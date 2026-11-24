# Test roadmap for the Studio

## Scope and order

Finish the code for Steps 10–14, add focused tests with each change, then run the complete regression and release checks on the same commit. The software acceptance run uses small synthetic or permission-cleared fixtures, PostgreSQL and a pinned CPU training runtime. A separate target-machine run measures GPU capacity and a domain reviewer evaluates the real aviation model.

Cloud code verification recorded 99 backend passes with one CUDA skip, 15 CPU numerical passes, 36 frontend passes and a successful production build. The focused CPU integration test exercised direct SFT, mid-training followed by SFT, cross-run final-test scoring and restore of the packaged model. Repeat the acceptance scenario on your local checkout and record the tested commit.

## 1. Start with the existing suites

From the repository root, start `python3 scripts/dev.py` in a terminal and verify that the UI loads and the API can query PostgreSQL. Run the remaining commands from a second terminal.

```bash
npm test --prefix frontend
npm run build --prefix frontend
python3 scripts/setup_training.py --profile cpu
.venv/bin/python -m pytest -q --tb=short -rs
.venv-training/bin/python -m pytest -q backend/training_tests --tb=short -rs
```

To rerun the two training routes and package restore on a small fixture, use:

```bash
.venv/bin/python -m pytest -q backend/tests/test_pilot_api.py -k checkpoint_initialization --tb=short -rs
```

Use a disposable local PostgreSQL instance. The default backend test fixture creates and drops a temporary database through the local role. If supplying `TEST_DATABASE_URL`, point it to a dedicated disposable test database. Use temporary artifact storage and start the end-to-end scenario from a clean project.

## 2. Verify each implementation step

| Step | Code and regression checks | Passing evidence |
| --- | --- | --- |
| [10. Data and runtime](STEP_10_FULL_CORPUS_RUNTIME_PLAN.md) | Import, review, group and deduplicate a small multi-document corpus. Check deterministic splits, train-only tokenizer fitting, exact text round-trip, artifact hashes and resource-limit handling. Test CPU readiness and clear errors for unavailable CUDA. | The same source and settings reproduce the split and sequence contents. No source family crosses splits. A real CPU forward/backward pass succeeds. |
| [11. Pre-training](STEP_11_FULL_PRETRAINING_PLAN.md) | Start a bounded run through the normal queue. Check full train coverage, validation separation, finite loss, throughput, reported budget, cancellation, restart recovery, disk limits and retention of referenced checkpoints. | An interrupted run resumes from a registered checkpoint and matches uninterrupted training within the recorded determinism tolerance. A fresh process reloads the selected checkpoint and generates a completion. |
| [12. Mid-training](STEP_12_MID_TRAINING_PLAN.md) | Use the same tokenizer on a second reviewed corpus. Check new-stage initialization from parent weights, fresh optimizer state, independent permission and artifact checks, checkpoint lineage and exact resume within that stage. | Manifest identifies both corpora and the parent checkpoint. Incompatible artifacts, revoked permissions and cross-project inputs are rejected. Both the direct route and the optional mid-training route remain usable. |
| [13. SFT](STEP_13_SUPERVISED_FINE_TUNING_PLAN.md) | Import, review, split and persist source-backed Bangla Q&A examples. Check prompt and padding masks, first answer token and EOS supervision, template parity at inference, over-context handling and checkpoint reload. Test the resulting UI through the normal workflow. | A bounded CPU SFT job completes and its checkpoint loads in Playground. Fixtures demonstrate gradient updates and correct label masking. Target-domain factual quality is assessed in the real model run. |
| [14. Evaluation and release](STEP_14_FINAL_EVALUATION_RELEASE_PLAN.md) | Check that validation and reserved test inputs are distinct. Verify held-out artifact reconstruction, overlap rejection, report lineage, source-backed and insufficient-evidence cases, streaming cancellation, and package checksums and restore. | The final report identifies both candidates and the frozen protocol. A clean local setup can restore the exported model, tokenizer and template and run inference. |

For concurrent or retried jobs, confirm that failed or cancelled runs never publish partial artifacts, and successful runs have a single recoverable result. Include failures the user can hit from the UI, such as a deleted dependency, stale revision, incompatible context, or unavailable runtime.

## 3. Run the final acceptance scenario

1. Create a clean project. Import and review synthetic documents with separate train, validation and final test source families. Verify dataset versions and export checksums.
2. Fit a tokenizer on train, generate sequences and complete a bounded base training run. Cancel or interrupt a second run and verify resume.
3. From the same base, run direct SFT. In a separate branch of model lineage, run mid-training on a reviewed second corpus and then use the same SFT configuration. Verify lineage and run isolation in both paths.
4. Select a candidate using validation. Open the reserved test split only after freezing the candidate and scoring protocol. Exercise both supported-answer and insufficient-evidence prompts, and inspect the saved comparison and human review fields.
5. Load the candidate in Playground, verify generation and cancellation in the browser, then export and restore the package in a clean local workspace. Recheck the recorded sample prompts using the shipped template.

## Release gates

- **Code complete:** Steps 10–14 have working UI/API entry points where the roadmap requires them. Both CPU routes pass end to end with fixtures. Frontend build, backend integration and numerical tests pass. Record all intentional skips with reasons. A skip for an uninstalled CPU runtime does not meet the release gate.
- **Target runtime verified:** On the intended GPU machine, run the pinned CUDA setup, numerical checks and a small real training job. Record VRAM, throughput, checkpoint restore and the measured compute budget.
- **Real model accepted:** Confirm corpus permissions and domain review, run the agreed training budget, and measure final model quality on reserved documents. Record clause support, correctness, insufficient-evidence behavior, Bangla quality and known limitations against thresholds agreed before evaluation.

Record the tested commit, commands, test counts, skipped cases, fixture identifiers, artifact hashes and failed checks in the release verification report.
