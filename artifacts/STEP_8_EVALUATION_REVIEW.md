# Step 8 — Baseline Evaluation Review

Date: **20 November 2026, Asia/Dhaka**.

Status: **Baseline and external Markdown evaluation executed. Human/domain review remains pending.**

## 1. Result and decision

The original pilot's checkpoints **7/14/21** were evaluated on all seven training blocks and a frozen set of **12 completion prompts**. All **36 compared continuations contain only 32 newline characters**, with no EOS reached. A separate Playground generation reproduced the same output for the final checkpoint.

Training loss decreases across checkpoints, but these probes do not demonstrate useful text completion. Initially no external document had been supplied. The user subsequently provided the repository's `doc/` folder: two distinct OM-A Markdown documents were imported, technically reviewed and evaluated with the frozen tokenizer. Their external loss also decreases, **6.9118 → 6.8496 → 6.7999**, over **28 blocks / 27,075 supervised targets**.

**Next action:** review/correct extraction issues and obtain human/domain review, then choose one controlled next-pilot comparison against the frozen external corpus. No new training run, tokenizer fitting, original source edit or larger-epoch experiment was started. Step 21 has the lowest external loss among these three checkpoints on this limited corpus; that does not establish useful generation or an overall best model.

## 2. Frozen baseline and integrity

| Reference | Saved identity |
| --- | --- |
| Project | `mahin` — `6c465258-3451-4421-a797-730b5d982760` |
| Baseline pilot | `09f2260f-9ed6-4b3d-a2f7-1cade911511a` |
| Linked resumed pilot | `e916e14b-69fb-44cd-9847-4b050decb41e` |
| Model config | `43a0861c-7d0f-45e3-abe3-dcc8af429a52` |
| Dataset | `a2ce1a39-3aeb-41e5-95a6-08c11ef1d604` — `PPC Rule.pdf` |
| Reviewed dataset version | Version 3 — `6a80ee86-5ef8-4c75-b359-b4e51b2d9fdc` |
| Tokenizer run | `d6359610-da1a-46b2-b39a-f91f163a9572` |
| Sequence run | `95556465-6286-411f-a4a4-c45a52a6e213` |
| Architecture | GPT-2 style, 2 layers, hidden 128, 4 heads; 678,016 parameters |
| Tokenizer / context | 1,173 vocabulary; 1,024 positions; PAD/UNK/BOS/EOS = 0/1/2/3 |
| Original training | Random initialization, seed 42, CPU/FP32, AdamW 0.0003; 3 epochs / 21 updates |

Runtime: Python **3.14.4**, Torch **2.11.0+cpu**, Transformers **4.57.6**, tokenizers **0.22.2**, safetensors **0.8.0**. Runtime readiness and compatibility passed before evaluation.

Tokenizer SHA-256: `c09acc9c34339181c09a18bf6d4a1b79fa5332c6b8a5e5f435934e53b1d5aa49`.

Source identity: `06e2c926dcf5ac4eba6ed1f749b56c45c68b0a83cde52761e136ef62861ee69c`.

Baseline bundle SHA-256: `4ebcfcf8f23ce0ea5ea060c21a0e4ec9e0d534e8959517a11096388d3d245bdf`.

Registered baseline artifacts were downloaded through the existing API. Sizes, SHA-256 and ZIP contents passed verification. Complete reviewed-document → frozen-tokenizer → sequence coverage and all three checkpoint file manifests were verified before and after evaluation. The baseline API record remained identical, and the four existing training runs remained the only training runs.

| Step | Checkpoint ID | Model SHA-256 |
| --- | --- | --- |
| 7 | `5e56cc03-3b6a-46d6-b9d8-6338e3c7c294` | `abdc54ac5856fa6a14c937fa6e7335c94e4edd42cc0e67d2a6045a94f8f6e389` |
| 14 | `aca1489f-8b63-4d5d-8c96-d6e4bb81555e` | `a556804ee54d26adea467e638e0e7ad6695905a8b5f5c3c2d722cea70f04b477` |
| 21 | `cf958484-9ae2-45c7-944d-7479348921aa` | `8e95616a7ed6aedf6e58376299e92c7f8290014b7945527d5e3a9dfe06baead6` |

## 3. Numerical results

Evaluation run: `e3cf8d22-d433-4d70-aee6-1eb3b2bfe207`.

Protocol: **block-based NLL/PPL v1**, document-isolated non-overlapping blocks, one BOS/EOS per document, right padding, one internal causal shift. Loss is weighted by supervised targets; padding and each block's first token are excluded. No scoring weight updates occurred.

| Checkpoint | Training loss | Training block PPL | Train blocks / targets | Independent loss / PPL |
| --- | --- | --- | --- | --- |
| Step 7 | 6.547282 | 697.346 | 7 / 6,654 | 6.911798 / 1004.051 |
| Step 14 | 6.331947 | 562.250 | 7 / 6,654 | 6.849646 / 943.547 |
| Step 21 | 6.109946 | 450.314 | 7 / 6,654 | 6.799943 / 897.796 |

The training columns match the earlier saved diagnostics. The training corpus is one source document reconstructed from 27 PDF pages; its original validation/test exports remain empty. The external column scores the separate Markdown corpus with the same block protocol and tokenizer. Perplexity is not accuracy, and these results do not establish factual correctness or broad generalization.

### External Markdown corpus

External evaluation run: `0d38595c-f269-4b46-b7da-2ce44409e5e8`.

Dataset: `e1c1a986-9907-4ba4-bd52-b781a51627aa`; reviewed version 2: `2e1ad2ca-d81e-465f-b4fe-59fcd54c74ab`.

| Selected original | Blocks | Supervised targets |
| --- | --- | --- |
| `doc/section_4_4_scheduling.md` | 2 | 1,465 |
| `doc/Section_7_Flight_and_Duty_Time.md` | 26 | 25,610 |

Both files are user-supplied OM-A sections, with source editions/dates retained as written. Technical review checked readable canonical text, headings/tables and byte-preserving import; it does not approve the aviation rules. Markdown syntax stays in the scored text. Processing applies NFC/newline normalization and outer whitespace trim, with no HTML stripping or whitespace collapsing. Each file remains a separate document. The larger Section 7 accounts for most target tokens, so the weighted aggregate is not a balanced average of the two documents.

Known source/file/document/cleaned-content overlap checks passed. Normalized 8- and 12-word phrase checks found no matches for the selected files against the training text. Manual scope review found different scheduling/flight-duty-time subject matter from the recent-experience explanation. Same-airline terminology, possible paraphrases and domain expertise remain limitations; these checks are not proof of complete semantic independence.

`OM-D_Full_English.md` was excluded: 483 encoded blocks exceed the 256-block evaluation limit, and its OCR-heavy conversion needs separate review. `OM-D_Training_Summary.md` was excluded from this first corpus because its training/PPC/absence material is closely related to the baseline source. Neither excluded file was silently sampled or imported for training.

The external target's preparation export uses the existing 100/0/0 storage contract. Its role for this model is explicitly **evaluation-only**; no tokenizer/model fitting used these documents. Keep that version out of future candidate training if it continues to serve as held-out evidence.

## 4. Fixed prompts and qualitative observations

Saved prompt set: **Step 8 · PPC pilot baseline · 2026-11-20**, version **1**.

Set ID: `5daab631-107e-4f5f-8291-eab958682882`; version ID: `608df22a-167d-46db-b676-e4c72c065881`.

The source concerns flight-crew competency/recent experience. Prompts use that source's headings and wording; they are qualitative source-derived probes, not independent data or a gold question-answer benchmark. All prompt round trips and available context budgets passed for all checkpoints.

| Prompt | Text |
| --- | --- |
| 1 | `একজন pilot` |
| 2 | `এই rule-এর মূল উদ্দেশ্য` |
| 3 | `Final eligibility check করতে হবে` |
| 4 | `Licence Status:` |
| 5 | `Medical Status:` |
| 6 | `PPC / Skill Test Status:` |
| 7 | `Recent Experience Status:` |
| 8 | `Absence / Requalification Status:` |
| 9 | `Aircraft limitations\nNormal procedures` |
| 10 | `Full aircraft type technical training course` |
| 11 | `2.1 Eligible মানে কী?\n` |
| 12 | `What is pending?\n` |

Here `\n` denotes an actual newline in the saved prompt. Decoding was greedy, maximum **32 new tokens**, with identical prompts/settings for all three checkpoints.

Every compared output was token **202 repeated 32 times**; loading the frozen tokenizer confirms ID 202 decodes to newline. Each decoded continuation was exactly `"\n" × 32`, not an empty response or EOS stop. There was no visible language content to assess source agreement. This is an observation on these probes, not an accuracy percentage or a claim about every possible prompt.

All 36 outputs have saved provisional assistant observations: readability **Needs review**, repetition **Present**, source agreement **Not reviewed**. Notes explicitly identify **Codex (assistant)** and leave human/domain approval pending. No factual-match judgment or domain-expert approval was fabricated. The external run reused the same frozen prompts/settings and produced identical IDs/text; its notes record that fact. This is not an additional independent set of 36 probes.

Playground run `ecb8df39-19cd-4a02-98a5-fffff350e48e` reproduced the final checkpoint's newline-only continuation for prompt 1. Its artifacts were also downloaded and verified.

## 5. Source-quality review

Text samples from pages **1, 14 and 27** were inspected; rendered original PDF pages **1 and 14** were visually compared with extracted text. This is sampled review, not a new approval of all pages or of the document's domain rules.

- Rendered page 1 shows **হলো / কোনো**, while PDF text extraction and the saved reviewed corpus contain **হললো / ককোননো**. The saved corpus contains `হললো` once on page 1 and `ককোননো` on pages 1 and 2. These are extraction discrepancies; observing the same spelling in raw extracted text does not establish a source-author typo.
- The two-column table on page 14 is linearized into text with wrapped term/meaning rows. Preserve and review those associations when correcting the corpus; sampled text integrity alone does not validate every table.
- Token 202 occurs **776 times among 6,661 real exported IDs**, including boundaries. This documents the source's newline exposure; it does not prove why generation repeats newlines. A controlled data/training experiment is needed to identify the cause.

Keep the baseline unchanged. Publish corrections as a new reviewed version before making a new tokenizer/sequence/config chain for future training. Preserve meaningful paragraph boundaries during cleanup.

## 6. Artifacts and verification

Local backups are in **`data/assessments/step-8-2026-11-20/`**, deliberately ignored by Git:

- `baseline/`: complete training bundle, tokenizer/config, report, coverage, metrics and manifest.
- `evaluation/`: comparison report, all outputs, events, manifest and ZIP.
- `generation/`: reproduced Playground result artifacts.
- `prompt-set.json`, `annotations.json`, `prompt-observations.csv`, `execution.json`: frozen prompts, separate reviewer export, escaped output observations and checksum inventory.
- `source-review/`: rendered pages for local visual comparison.
- `external-markdown/`: candidate-file audit, reviewed dataset snapshot, external report/outputs/ZIP, annotations and checksum inventory.

Portable summaries: [baseline](STEP_8_BASELINE_SUMMARY.json), [external Markdown evaluation](STEP_8_MARKDOWN_EVALUATION.json). Existing Evaluation/Playground history contains the saved runs and downloads; review notes remain separate from immutable generated reports.

The discovered UI gap was fixed in existing output views: whitespace-only completions now show **[Whitespace-only continuation]**, and **Escaped generated text** exposes actual control characters. Pre-training samples, Evaluation and Playground share this presentation. Stored outputs and raw token IDs remain intact; an empty continuation has a distinct marker.

Verification: **93 backend tests passed, one CUDA test skipped; 36 frontend tests and production TypeScript/Vite build passed**. New Markdown tests cover UTF-8/BOM, uppercase extensions, unchanged table/code/Unicode content, byte/document limits, invalid encoding and API processing/review. Real desktop/mobile checks cover visible whitespace output, notes/downloads, external metric labels/counts, Markdown file selection and corpus selection, with no horizontal overflow or uncaught JavaScript errors. The numerical executor was unchanged; its standalone suite was not rerun for the file-format addition.

Screenshots: [baseline Evaluation](step8-evaluation-desktop.png), [baseline mobile](step8-evaluation-mobile.png), [Playground](step8-playground-desktop.png), [external Markdown results](step8-markdown-external-desktop.png), [external mobile](step8-markdown-external-mobile.png).

## 7. Remaining review and next action

1. **External corpus execution is complete:** two supplied Markdown documents were reviewed for technical text integrity and scored. Preserve their evaluation-only role; further independent documents would broaden the evidence.
2. **Human/domain review:** inspect the assistant's saved observations, sampled tables and extraction discrepancies. Current annotations are not expert validation.
3. **Next experiment:** both training and external loss improved across these checkpoints. A new 10-epoch pilot (70 updates on the unchanged seven-block source) is one possible controlled duration experiment after addressing source-quality issues; it is not an automatic remedy for newline-only generation. If source corrections change the tokenizer, start a new comparison series rather than directly comparing perplexity across tokenizers. No larger run or fine-tuning was launched.

Technical baseline and external evaluation are executed; human/domain review remains **pending**. Original validation/test splits remain empty and were not relabeled. Related: [Step 8 plan](../STEP_8_INDEPENDENT_EVALUATION_PLAN.md).
