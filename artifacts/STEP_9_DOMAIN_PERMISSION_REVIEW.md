# Step 9 — Source, domain and permission review

Reviewed: 20 November 2026. Status: **Technical comparison and limited source cross-check completed; domain approval and permission remain unverified.**

## Source and scope

The original 27-page `PPC Rule.pdf` is a Bangla/English explanatory analysis, not the original regulation. Its source PDF SHA-256 is `1545d04b185d7308cd3709db63dec13f0ba001378674607768956fbc76904d69`; the baseline used dataset version `6a80ee86-5ef8-4c75-b359-b4e51b2d9fdc`. The [CAAB-hosted ANO 1, gazetted 8 April 2024, Annexure 8](https://new.caab.gov.bd/ano/ANO%201-GAZETTE.pdf) is a relevant primary comparison (printed pages 5846–5850). This review did not establish whether it is the controlling version for the actual operator, date, aircraft and circumstances; current amendments, applicable operator procedures and authority interpretation must be checked by an aviation specialist. Do not use these observations for operational eligibility decisions.

## Page-level extraction review

All 27 rendered pages were inspected for layout. Saved training text was checked against a second extraction across every page with Unicode/whitespace normalization; selected transcription differences and table relationships were compared visually. This is a technical review, **not a character-by-character certification**: the two extractors may share errors, table transcription can lose layout, zero-width characters and line breaks were normalized for the comparison, and domain meaning was not approved. The source version and raw PDF remain unchanged.

| Page | Main content reviewed | Outcome or specific issue |
| --- | --- | --- |
| 1 | Title, eligibility introduction | `হললো` and `ককোননো` corrected in draft; confirm final reading. |
| 2 | Eligibility and 90-day example | `ককোননো` corrected in draft. |
| 3 | PPC comparison table and decision steps | Four `কররো` corrections in draft; table associations checked. |
| 4 | 90-day rule and logic | Four `কররো` corrections in draft; Boolean precedence remains a domain concern. |
| 5 | Two pilot-record tables | Date, type and numeric row associations checked. |
| 6 | Wrong-type example table | B737/3/3 row checked. |
| 7 | Absence-bracket table | Wrapped header and row explicitly structured in table draft. |
| 8 | 180–365-day explanation | Automated extractors agree after normalization; domain review pending. |
| 9 | Training requirements table | Wrapped clause identifiers rejoined in table draft; compare authority before application. |
| 10 | Training hours and example | Automated extractors agree after normalization. |
| 11 | Route-sector example table | `ভাললো` corrected in draft; route/count associations checked. |
| 12 | Route training/check table | Two item/meaning associations checked. |
| 13 | Technical-course explanation | Automated extractors agree after normalization. |
| 14 | Technical course/type-rating table | Two term/meaning associations checked; wrapped text preserved. |
| 15 | Agent inputs and output | Automated extractors agree after normalization. |
| 16 | Scenario 1 and beginning of 2 | Automated extractors agree after normalization. |
| 17 | Scenarios 2 and 3 | Automated extractors agree after normalization. |
| 18 | Scenarios 3 and 4 | Automated extractors agree after normalization. |
| 19 | Scenarios 4–6 | Automated extractors agree after normalization. |
| 20 | Scenarios 6–7 | Automated extractors agree after normalization. |
| 21 | Scenarios 7–8 | Automated extractors agree after normalization. |
| 22 | Status/meaning table | `কোননো` corrected in draft; 11 status/meaning associations checked. |
| 23 | Decision tree | Automated extractors agree after normalization; operational logic not certified. |
| 24 | Decision tree and prompt | Automated extractors agree after normalization. |
| 25 | Prompt and stakeholder questions | One normalized space differs between extractors; no semantic change inferred. |
| 26 | Open questions and summary | `ককোন` corrected in draft; stakeholder questions remain unresolved. |
| 27 | Final two questions | Automated extractors agree after normalization. |

The [proposed transcription draft](../data/assessments/step-9-2026-11-20/proposed-processed-table-draft.jsonl) includes 14 targeted character changes and table reformatting on pages 7 and 9. Its [change log](../data/assessments/step-9-2026-11-20/proposed-corrections-table-draft.json) preserves prior and replacement text. All 27 identifiers and non-text metadata were verified unchanged. The draft has not been published or expert approved. Detailed table observations are in [table review](STEP_9_TABLE_REVIEW.md).

## Limited cross-check against the 2024 gazette

- The PDF's basic 90-day discussion reflects a similar requirement in Annexure 8 §2.2.1. However, that clause specifies PIC/co-pilot operation **at the flight controls during take-off and landing**, on the same type or an appropriately approved simulator. The PDF's broad “flight duty” / eligibility shorthand can overstate the clause's scope and should not drive an automated decision without the omitted context. Its page 4 `AND ... OR ...` pseudocode also needs explicit parentheses and specialist validation.
- The PDF's 90–180-day (12 hours or 50%, whichever is less, examination, route training/check) and 180–365-day (30 hours or 50%, examination, simulator training followed by skill test, route training/check) summaries broadly track Annexure 8 §§2.3–2.4, **conditional on the correct applicability and current version**. They are summaries, not a complete compliance determination.
- The PDF's summaries and agent prompt often state simulator sessions as mandatory without preserving the full alternative aircraft-training path when FSTD is unavailable. The 2024 gazette §§2.4.1.2 and 2.5.1.2 contains distinct simulator/aircraft options and training details. The page 9 table mentions fallback but is not a full statement of its conditions; see source before using it.
- Pages 25–26 explicitly contain assumptions to confirm. Other conditions, exceptions, aircraft category, FSTD approval, validity and operator-specific requirements may affect a real case. Annexure 8 also has a separate section for single-pilot operations; the simplified decision tree must not be generalized to all operations.
- In the 2024 PDF, the 2.6 aircraft-training paragraph is printed under the same subnumber as the simulator paragraph, while preceding text refers to a different number. This appears to be an internal source numbering inconsistency, not evidence to silently rewrite the source; ask the authority/operator for clarification.

These are selected source comparisons, not a complete legal/regulatory review or certification. A qualified operator/domain reviewer must validate each rule, scope, edition, amendments and page-26 open questions before operational use.

## Permission and provenance

| Material | Current evidence | Decision |
| --- | --- | --- |
| User-supplied explanatory PDF | Present locally; author, source licence, ownership and permission evidence not established by the file alone. The app's saved permission flag is not independent proof. | **Unverified** for further training and distribution pending owner confirmation. |
| Two OM-A Markdown evaluation documents | Supplied locally; operator provenance, rights to process and content lineage are unconfirmed. | **Unverified** for future processing or distribution; retain existing evaluation-only role. |
| CAAB-hosted gazette | Publicly accessible official copy. | Availability establishes access to the source, not permission to republish or reuse every derivative or operator manual. Confirm applicable terms. |
| Other OM-D candidates | User-supplied; lineage and permission not established. | Unverified; do not assign to training or final evaluation on this review alone. |

Requested from user: document ownership/source, authority to use for model training and evaluation, restrictions on distribution and the applicable operator/edition. No authorization was inferred from upload, local availability, or a metadata flag. The earlier experimental runs remain historical facts; this review does not retroactively certify their permissions.

## Decision

Preserve baseline and correction drafts. Do not mark the corpus domain-approved or permission-verified, publish the corrected version as fully reviewed, or use it for operational eligibility decisions until the outstanding source and reviewer decisions are resolved. Technical transcription changes can be reviewed independently from the substantive rules.
