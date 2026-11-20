# Step 9 — Review Progress

Date: 20 November 2026. Status: **Partial; no training decision approved.**

## Source and role inventory

| Source | Current role | Evidence and outstanding review |
| --- | --- | --- |
| `doc/PPC Rule.pdf` | Existing baseline training source | 27 pages have extractable text (checked with `pdfinfo` and `pdftotext -layout`). Text presence is not a visual comparison or approval. Step 8 identified Bangla discrepancies on pages 1–2 and a linearized table on page 14. Page-by-page visual and domain review remains pending. |
| `doc/section_4_4_scheduling.md`; `doc/Section_7_Flight_and_Duty_Time.md` | Step 8 iterative evaluation only | Existing saved version and reports identify these as held out. Technical checks and phrase matching are not proof of independence, permission or aviation accuracy; domain review remains pending. Keep them out of model/tokenizer training when using them for comparison. |
| `doc/OM-D_Full_English.md` | Unassigned / excluded from Step 8 | 483 frozen-tokenizer blocks exceed the 256-block evaluation limit; OCR-heavy text and one eight-word match to training were recorded in the Step 8 candidate audit. Source lineage, permission and intended role need review. |
| `doc/OM-D_Training_Summary.md` | Unassigned / excluded from Step 8 | Related PPC/training subject matter requires lineage and near-duplicate review despite no recorded eight- or twelve-word exact phrase hits. Permission and role remain undecided. |
| Separate final-test corpus | Not identified | No corpus is reserved; identifying one requires suitable independent, permission-compatible documents. |

The candidate-file audit is saved in the ignored Step 8 assessment folder, `data/assessments/step-8-2026-11-20/external-markdown/candidate-documents.json`. Full hashes, evaluation identifiers, limitations and existing review evidence are in [Step 8 review](STEP_8_EVALUATION_REVIEW.md). No roles above assert permission or expert approval.

## Diagnostic baseline

The saved Step 8 report records token 202 repeated 32 times in all 36 completions, and 776 occurrences of that token among 6,661 real exported training IDs. Both training and external loss improved during the three-checkpoint pilot. A read-only forward pass through the saved weights and frozen tokenizer reproduced newline as the top next token for two prompts at steps 7, 14 and 21. After suppressing PAD/UNK/BOS as in generation, newline probabilities were 0.775%, 1.111%, 1.611% for `একজন pilot` and 0.892%, 1.274%, 1.987% for `Licence Status:`; colon ranked second in all six cases. Greedy decoding selects the highest-probability token even when its absolute probability is low. The inference path supplies BOS and an all-ones attention mask; sequence labels mask padding. These observations identify the immediate greedy selection, but do not establish why the model ranks newline first or rule out other defects. Source frequency and learning dynamics remain hypotheses. See [Step 8 review](STEP_8_EVALUATION_REVIEW.md) for protocol and counts.

## Decision and outstanding gates

**No new pilot yet.** The original PDF has known extraction discrepancies, human/domain and permission review has not been recorded, a final test corpus has not been identified, and a compute/disk budget and acceptance thresholds are not specified. A controlled hypothesis and comparable training setup should be selected after review and diagnosis. No corrected dataset has been published and no domain or permission approval is implied.

Next: review the original PDF page by page against its extraction; confirm source rights and document lineage; inspect the saved generation pipeline and checkpoint probabilities; then specify one comparison, budget and stopping/acceptance criteria. Record reviewer decisions and retain immutable baseline artifacts. See [Step 9 plan](../STEP_9_DATA_QUALITY_PILOT_PLAN.md).

## Follow-up — 27-page automated comparison and full decoding check

All 27 rendered pages were inspected for layout and compared automatically, page by page, against an independently extracted text. A review draft proposes 14 targeted Bengali character corrections across pages 1, 2, 3, 4, 11, 22 and 26; all 27 IDs and other record metadata were verified unchanged. After Unicode/whitespace normalization, 26 corrected page texts match the alternative extraction; page 25 differs by one space. Extractor agreement does not validate table structure or replace line-by-line visual/domain review. The draft and correction list are under the ignored `data/assessments/step-9-2026-11-20/` folder; no new dataset version was published.

Cached generation and direct uncached greedy decoding agree for **all 32 generated tokens** of each of 36 checkpoint/prompt combinations. The source extraction discrepancies are real; a general safe code fix for arbitrary PDF glyph extraction has not been established. See [diagnosis report](STEP_9_DIAGNOSIS_REPORT.md), [results](STEP_9_DIAGNOSIS.json) and [pilot card](STEP_9_EXPERIMENT_CARD.md). The API was unavailable during the check; no pilot was started.

## Table follow-up

Compared the visible tables on pages 3, 5, 6, 7, 9, 11, 12, 14 and 22 with their saved text. A separate draft makes page 7 row associations explicit and rejoins wrapped identifiers in page 9's table; a 27-record/metadata check passed. See [table review](STEP_9_TABLE_REVIEW.md). This is technical transcription work, not aviation approval or publication.

## Duration pilot executed

The approved bounded CPU diagnostic completed 70 updates in 18.2 seconds; step 21 reproduced the original checkpoint hash. The frozen external evaluation improved from 6.799943 to 6.754163 loss at step 70, but 11/12 prompt continuations remained whitespace-only. See [pilot result](STEP_9_PILOT_RESULT.md). Source transcription review and domain/permission decisions are still pending; this does not make Step 9 fully complete.

## Source and domain cross-check

A 27-page technical review ledger and a limited comparison against the CAAB-hosted 2024 ANO 1 Annexure 8 are recorded in [domain and permission review](STEP_9_DOMAIN_PERMISSION_REVIEW.md). Notable issues are the broader shorthand for the 90-day flight-controls rule, ambiguous Boolean logic and omitted aircraft-training alternatives in portions of the summary. Current applicability, expert approval and rights for the user-supplied PDF and OM-A documents remain unverified; no corrected version was published or declared domain-approved.

## Controlled decoding probe

Compared the original greedy output with repeated-bigram blocking and three seeded top-k samples for both saved step 21/70 models and the same 12 prompts. Although the alternative settings avoid all-whitespace outputs, inspected text remains fragmented and repetitive; this is not a demonstrated fix. Results and reproducible process graph are in [decoding probe](STEP_9_DECODING_PROBE.md). The probe ran twice with identical output hash and unchanged checkpoints.
