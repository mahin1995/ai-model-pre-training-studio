# Use-case-based mid-training and fine-tuning

## First use case

Add a workflow for Bangla aviation document Q&A. The user can ask for a plain Bangla explanation of a rule, optionally in mixed Bangla and English. The model should explain the rule, preserve conditions and exceptions, and cite the clause supported by the supplied excerpt. When the excerpt is insufficient, it should say so. The initial pilot uses a reviewed excerpt supplied with each prompt and is scoped to document study. A domain reviewer must verify the interpretation and applicability of the source.

## Choose a route by use case

| Observed need | Route | Dataset |
| --- | --- | --- |
| The base model understands the domain but struggles with instructions, Bangla explanations, citations, or insufficient-context responses | Base checkpoint → supervised fine-tuning (SFT) | Reviewed questions, source excerpts and target answers |
| The base model struggles with domain terminology or text completion on independent examples | Base checkpoint → optional mid-training → SFT if instruction following is needed | Reviewed domain documents for mid-training and separate instruction examples for SFT |
| The task is domain text completion without a Q&A requirement | Base checkpoint → optional mid-training | Reviewed domain documents and held-out completion prompts |

Start the aviation use case with a baseline evaluation and plan direct SFT as the first comparison. Run mid-training only when the baseline shows a domain-language gap worth testing. Compare direct SFT and mid-training followed by SFT using the same original base, SFT data, template and evaluation settings when possible.

## Delivery order

1. **Data and baseline.** Finish the Step 9 source correction, permission and domain review before using those documents for training. Reserve validation and final-test documents by source family, including revised or near-duplicate versions. Keep final-test documents and derived examples out of both training stages. Select a compatible local base checkpoint and record generation quality, domain comprehension and Bangla quality on development prompts. The Step 9 checkpoint can serve as diagnostic evidence. Its 11 whitespace-only completions out of 12 require baseline qualification before it can be selected for this workflow.
2. **Direct SFT pilot.** Add import and preview for reviewed instruction examples with a question, source excerpt, target answer and source revision or clause metadata. Version the dataset and prompt template. Preview role boundaries, context limits and assistant-only loss masking. Train from a selected checkpoint using a bounded configuration. Export the resulting checkpoint with its tokenizer and template and test it in the Playground.
3. **Optional mid-training pilot.** Select a reviewed document version and tokenize it with the parent checkpoint's exact tokenizer. Create a new run initialized from parent model weights with a fresh optimizer and scheduler. Train on causal next-token prediction and record the parent, corpus version, sequence artifact and budget. Evaluate domain and general-language quality before using the resulting checkpoint as a parent for SFT.
4. **Compare and publish the result.** Use the existing Evaluation and Playground where practical. Compare the base and trained candidates using the same prompts, source excerpts and decoding settings. Pick a candidate using validation results, then evaluate it on the reserved final test set. Export the selected model with its tokenizer, template where applicable, evaluation report and known limitations.

## SFT example preview

The tokenizer API accepts a single example at `POST /api/projects/{projectId}/tokenizers/{runId}/sft-preview`. Send `question`, `excerpt`, `answer` and `contextLength` to preview the `source-qa-v1` template. The response includes input IDs, an attention mask, loss labels and the prompt and supervised token counts. The formatter rejects oversized examples so citations and answer text stay intact. This endpoint is the first part of the SFT data workflow. Persistence, dataset splits and the training executor are planned in the delivery order above.

## Studio changes

- In Model Config and Training, add a use-case selection, explicit training stage, compatible parent checkpoint selector, source preview and budget. Start with Studio-native local checkpoints. Treat external checkpoint import and adapters as follow-up work after compatibility is verified.
- Reuse the existing queue, runtime checks, cancellation, logs and checkpoint verification. Store immutable parent and artifact identities for each stage. Exact resume restores the state of the same run. A transition to a new stage initializes a new run and preserves parent lineage.
- Add a frozen-tokenizer sequence path for a different reviewed domain corpus. The current sequence pipeline binds artifacts to the tokenizer's original dataset snapshot. Validate tokenizer identity and provenance for both datasets and keep each artifact versioned.
- Add source-backed Q&A as an evaluation task. Record answer correctness, whether cited clauses support the answer, handling of insufficient evidence, Bangla quality and repetition. Keep general-language regressions and runtime cost visible alongside task scores.

## Acceptance criteria

- A bounded direct SFT run can start from a compatible base checkpoint, reload its result and generate a response using the recorded template. Tests verify that user prompts and padding are excluded from the SFT loss and that incompatible artifacts and cross-project inputs are rejected.
- When enabled, a bounded mid-training run accepts a separate approved corpus with the frozen parent tokenizer. Tests verify new-stage initialization, exact resume within the stage, and reproducible lineage through subsequent SFT.
- Before each pilot, record the reviewer, run budget, fixed comparison prompts and pass thresholds. Require review of wrong citations, incorrect rule interpretations and answers based on insufficient excerpts before accepting the result. Keep an evaluation-only record of the comparison and select the simpler route when the additional training fails to justify its cost.

See the [Step 9 pilot result](artifacts/STEP_9_PILOT_RESULT.md) and [source and permission review](artifacts/STEP_9_DOMAIN_PERMISSION_REVIEW.md) for the current starting point.
