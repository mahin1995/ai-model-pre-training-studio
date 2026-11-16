# Step 6 — Checkpoint Evaluation and Playground Plan

Status: **Planned; implementation has not started.**

Date: 16 November 2026, Asia/Dhaka. This delivers the next bounded part of roadmap M7. Whole-dataset pilot training follows separately; this phase does not expand or rerun training automatically.

## 1. Current state and objective

Live read-only inspection found two completed, passed, independent 200-step smoke runs. The latest run matches the screenshot: **678,016 parameters**, **1,173 vocabulary**, **1,024 context**, CPU/FP32, same-subset loss **7.0572 → 1.0992**, and verified checkpoint reload. Checkpoints exist at steps **50/100/150/200**. No linked resumed run was present during inspection.

The smoke executor repeatedly trained on at most two blocks. The corpus has seven training blocks; the smoke result does not establish full-corpus learning or independent evaluation. Current validation/test are empty.

Next objective: use the saved model directly, inspect its generated text, compare checkpoints under identical conditions, and measure clearly scoped losses. Independent evaluation must remain unavailable until independent documents exist. CPU is sufficient to build and verify this feature; CUDA is an optional later runtime check.

## 2. Existing actions before larger training

These controls already exist; they do not require new implementation:

1. Download the successful run's **Complete training bundle** as a backup.
2. Run **Resume verification**, for example step 50 → 200, once for the chosen live configuration. Confirm completion, correct starting step and a final result consistent with the original run under the same runtime/settings.
3. Inspect the existing generated sample and review source spelling/table extraction. Corrections create a new reviewed version, tokenizer and sequences; keep the existing checkpoint and sources intact.

These actions are recommendations, not tasks executed by writing this plan. Their completion does not block independent UI/API development. Two from-scratch runs do not establish that live resume was tested.

## 3. Phase 6A — Functional checkpoint Playground

Workflow: **Playground → Saved run/checkpoint → Prompt → Generate → Inspect/save result**.

- Choose a completed same-project run and registered checkpoint. Default to its final checkpoint for convenience; do not call the latest checkpoint the best model.
- Display step, parameter count, actual vocabulary, context, tokenizer checksum and runtime. Load the exact saved tokenizer; do not train/replace it.
- Provide a plain text-completion prompt, not a chat interface. The current model has not been instruction/chat fine-tuned.
- Default generation: greedy, **32 new tokens**; bounded choices **8/16/32/64/128**, subject to available context. Add sampling later after deterministic comparison works.
- Prompt limit: **4 KiB UTF-8**. Require `1 BOS + prompt tokens + requested new tokens <= context length`; show token usage and reject overflow without silently truncating.
- Preserve literal `[BOS]`/`[EOS]` spellings as ordinary prompt content, insert actual BOS once, stop on actual EOS, suppress generated PAD/UNK/BOS, and store raw generated IDs.
- Show prompt and continuation separately, generated-token count, elapsed time and measured generation throughput. Byte fragments can decode poorly; this is not an extraction round-trip check.
- Save reproducible generation records containing checkpoint/tokenizer hashes, prompt, decoding settings, runtime and output. Include loading, cancel, error, history and refresh recovery states.

Initial scope is CPU inference on CPU-trained checkpoints in the pinned runtime. No model downloads, fine-tuning, optimizer update or automatic CPU/GPU conversion. Other runtime/device combinations need explicit testing before enabling them.

## 4. Phase 6B — Evaluation and checkpoint comparison

Workflow: **Evaluation → One saved run → Up to four checkpoints → Versioned prompt set / metric source → Run → Compare/export**.

### Saved prompt sets

- Support create/save/load/export of immutable prompt-set versions: name, language, up to **20 prompts**, and optional expected-content/reviewer notes.
- Use the same prompt bytes, maximum output tokens and greedy decoding across selected checkpoints. First version compares checkpoints from one training run to keep source/tokenizer/configuration consistent.
- Compare outputs side by side with generation timing and optional manual annotations for readability, repetition and agreement with the source. Save annotations separately from immutable generated results.
- Completion prompts and optional human notes are not a gold QA benchmark. Do not invent an accuracy percentage, use string matches as factual correctness, or declare rule accuracy automatically.

### Two distinct metric scopes

| Scope | Data | What the UI may claim |
| --- | --- | --- |
| Training diagnostic | Original source's train export | Fit/coverage diagnostic; no generalization claim |
| Independent evaluation | Nonempty original held-out split or a separately reviewed independent corpus | Measured held-out loss/perplexity with recorded provenance and protocol |

- For current data, evaluate all **seven** original training blocks without weight updates. Report original trained-subset loss separately from all-train-block loss. The other five blocks are not an independent held-out set: they share the PDF/source and training-tokenizer corpus.
- Empty validation/test shows **Not available — add independent documents**. It must not display zero loss, zero perplexity or a fake pass.
- For valid held-out data, report token-weighted mean next-token negative log-likelihood and `perplexity = exp(mean loss)`. Perplexity is not accuracy. Record target-token count, document/block count and padding exclusions; handle nonfinite loss and exponent overflow explicitly.
- Evaluation uses `model.eval()` plus no-grad/inference mode. Labels remain unshifted for the model's single internal shift; ignore `-100`, exclude the unpredicted first token of each block, and aggregate by actual target counts rather than averaging batch losses equally.
- First version reuses non-overlapping, source-isolated blocks. Label the protocol **block-based NLL/PPL v1**, including block length and boundary policy. This is not the sliding-window corpus PPL protocol; compare only identical tokenizer/data/protocol configurations. Sliding-window scoring is a later enhancement.
- No automatic best-checkpoint selection using training loss. Reserved test data is not used repeatedly for tuning; final test evaluation remains a separate explicit workflow.

## 5. Independent evaluation data without tokenizer refitting

Existing sequence generation is tied to the tokenizer's original reviewed dataset version. Selecting a new PDF in Evaluation therefore requires an explicit frozen-tokenizer encoding path; the current endpoint alone cannot do this.

- Allow the metric target to be an existing nonempty validation split, or an external **reviewed dataset version** with confirmed usage permission.
- Snapshot that target, extract its reviewed documents with provenance, and encode them with the checkpoint's frozen tokenizer. Preserve document boundaries, add one BOS/EOS pair per document and pad tails using the existing sequence contract. Never fit the tokenizer on evaluation text.
- Treat the external corpus as evaluation data for this checkpoint even if its original processing export calls its records `train`. Record this distinction; never change the original dataset split or submit training updates.
- Compare target source/file hashes, document/group lineage and exact cleaned-document hashes against the checkpoint's complete training source. Block known overlaps. Record that exact checks cannot rule out near-duplicates; independent-source review remains necessary.
- For the current single PDF, require additional independent documents for this scope. Do not split its existing pages into artificial train/validation groups or relabel the remaining five blocks as held-out.

## 6. Backend, persistence and UI integration

- Add the next unapplied numbered migration, expected **007_evaluation_playground.sql**, for immutable prompt sets/versions, inference jobs/results and revisioned manual annotations. Do not edit migrations 001–006.
- Reference the original project, run, checkpoint, tokenizer and optional evaluation dataset version. Protect referenced checkpoints, parent runs and datasets from deletion; checksum verification precedes every load/download.
- Extend the existing worker/advisory-lock queue so generation, evaluation and preparation/training do not execute simultaneously. Torch/model loading stays in a credential-free `.venv-training` subprocess; the API interpreter does not import Torch.
- Reuse checkpoint validation while separating inference-only weight loading from training resume. Inference must not restore optimizer/RNG state into a training loop, change checkpoints or mutate model weights. Verify model/special-token/context compatibility.
- States: queued → validating → loading → running → verifying → completed, with failed/cancelled terminals. Parent heartbeat, cancellation, runtime loading, native execution and timeouts remain cancellable; restart expires interrupted leases without automatic reruns.
- Initial bounds: one job at a time, four checkpoints, 20 prompts, up to 128 new tokens per prompt, **256 evaluation blocks**, 15-minute wall limit and **128 MiB result artifacts**. Validate disk/RAM before execution; over-limit requests fail clearly without silent sampling or dropping records.
- Persist CPU/runtime versions, source snapshots, protocol and checksum-registered JSON/JSONL/ZIP reports. Generated text, numerical metrics and human annotations stay distinguishable.
- Implement existing **Evaluation** and **Playground** sidebar destinations. Use existing services/types/components conventions, accessible labels, responsive comparisons, real progress and consistent error states. No chat streaming is needed for the first version.

Proposed API under `/api/projects/{project_id}`:

- `GET /inference-sources`: selectable completed runs/checkpoints and eligibility reasons.
- `GET/POST /prompt-sets`, `GET /prompt-sets/{id}/versions/{version}` and export.
- `POST /generation-runs` with checkpoint ID, prompt and bounded decoding settings.
- `POST /evaluation-runs` with checkpoint IDs, prompt-set version and explicit metric scope/target.
- List/detail/cancel/retry/delete/download routes for generation/evaluation runs; annotation updates use optimistic revisions.

## 7. Verification and acceptance

1. **Inference:** registered step-200 checkpoint → exact tokenizer → deterministic greedy continuation → saved/reloaded output and downloadable report. Weights/checkpoint hashes remain unchanged.
2. **Comparison:** steps 50/100/150/200 receive identical prompts/settings; source/tokenizer/config mismatch blocks comparison. No unsupported quality ranking.
3. **Loss:** manually computed shifted/masked cross-entropy matches reported token-weighted loss; padding contributes no targets; overflow/nonfinite cases produce explicit states.
4. **Current corpus:** all seven training blocks are included in diagnostic mode. Empty held-out splits show unavailable metrics and no fabricated zeros.
5. **External corpus:** isolated independent-document fixtures verify frozen encoding with no fitting; known duplicate/source overlap is blocked; valid independent text receives correctly labeled metrics.
6. **Lifecycle:** project isolation, checksum corruption, dependency deletion, context overflow, excessive limits, native cancellation and restart recovery are tested.
7. **UI:** saved prompts → checkpoint comparison → report export; Playground generation → cancel/history/refresh; keyboard and mobile checks. Run pytest, standalone training-runtime tests, Vitest and production build using temporary PostgreSQL/data.

Done when these workflows run on real local checkpoints and isolated fixtures. Do not require readable output or improved held-out loss to mark the tooling functional; poor model results must remain visible as results.

## 8. Following phase — Whole-dataset training pilot

After this evaluation/inspection workflow, plan a separate **bounded whole-dataset pilot**:

- Review/correct source text and freeze a chosen dataset/tokenizer/sequence version.
- Train on all seven available blocks if that remains the selected corpus; introduce epoch/data-cursor settings instead of only increasing the current two-block smoke step count.
- Start a new training run with explicit initialization policy. Do not silently continue the overfit smoke checkpoint or reinterpret its existing resume action as full-dataset training.
- Record all-block coverage, epoch progress, checkpoint policy and runtime budget; evaluate on independent validation data when available. Without it, label the run a learning experiment and avoid automatic quality selection.
- CPU can support the small pilot; CUDA installation and a fresh device smoke test can be added when scaling demands it. Larger corpus collection, fine-tuning and broader quality evaluation remain later work.

## References

- [Hugging Face: generation settings and token limits](https://huggingface.co/docs/transformers/main_classes/text_generation)
- [Hugging Face: perplexity, tokenizer dependence and windowing](https://huggingface.co/docs/transformers/perplexity)
- [Hugging Face: causal language modeling and evaluation](https://huggingface.co/docs/transformers/en/tasks/language_modeling)
- [PyTorch: checkpoint state for inference/resume](https://docs.pytorch.org/tutorials/beginner/saving_loading_models)
- Repository context: [smoke-test implementation plan](STEP_5_MODEL_SMOKE_TEST_PLAN.md), [remaining roadmap](REMAINING_WORK_PLAN.md).
