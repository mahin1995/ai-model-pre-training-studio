# Step 9 — Controlled duration pilot result

Date: 20 November 2026. The 10-epoch CPU diagnostic and external evaluation completed; source review and domain approval are still pending.

The new run `78be46dd-652c-45db-8ea0-4b4734a7ebdf` used configuration `eaec134b-c637-4460-ad49-557c77837714`, the original seven training blocks and frozen tokenizer, architecture, seed and optimizer. It completed 70 updates / ten epochs, 66,540 supervised-target exposures, in 18.2 seconds. Saved run files use 92,975,028 bytes; the 900-second limit and one-GiB checkpoint estimate were not exceeded. Configuration estimated 163,733,504 bytes. CPU runtime was ready; CUDA was not used. The existing baseline and source were not modified.

The candidate's step-21 model SHA-256 `8e95616a7ed6aedf6e58376299e92c7f8290014b7945527d5e3a9dfe06baead6` matches the original step-21 model exactly. This meets the pre-run reproducibility criterion. Evaluation `2a9c7145-829e-4145-adcd-f175cb552a83` used the same frozen 12 prompts, 32-token greedy decoding and evaluation-only external corpus as Step 8: two documents, 28 blocks and 27,075 target tokens. This corpus is small, unbalanced and not domain approved.

| Checkpoint | All-train diagnostic loss | External loss | External block PPL | Whitespace-only outputs |
| --- | ---: | ---: | ---: | ---: |
| 21 | 6.109946 | 6.799943 | 897.796 | 12 / 12 |
| 70 | 4.890068 | 6.754163 | 857.622 | 11 / 12 |

At step 70, the one non-whitespace output begins with a short malformed Bangla fragment then repeats newlines. The predeclared zero-whitespace-only screen was **not met**; it was a crude diagnostic screen, not a domain acceptance criterion. External loss improved slightly on this particular corpus while training loss improved much more; neither loss nor perplexity is factual accuracy, and the difference does not establish the cause of repetition or generalization. Longer training alone did not yield usable output on these probes. Avoid scaling or selecting this checkpoint as a usable model on this evidence.

The structured [summary](STEP_9_PILOT_SUMMARY.json) records checkpoint/report hashes and coverage. Full generated outputs and reports are saved in the application's evaluation history. The external corpus must remain evaluation-only. Further work: complete source correction review, confirm document rights and domain meaning, and design a comparison that changes one variable; the current API binds sequences to the tokenizer's original dataset snapshot, which constrains a corrected-data-only comparison. No corrected dataset has been published.
