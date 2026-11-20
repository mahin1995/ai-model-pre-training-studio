---
title: Display current dataset names in inference run selectors
type: bugfix
ticket: ''
created: '2026-11-20'
status: built
baseline_revision: '694525a2040c1161fa752e73398bced905f3e465'
route: oneshot
route_source: auto
risk: low
review: quick
review_source: pinned
lenses_ran: [quick]
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** After a dataset is renamed, evaluation's training run dropdown still shows the name saved at training time.

**Approach:** Return the current dataset name separately from the historical snapshot, display the current name in Evaluation and Playground, and preserve the historical source and checkpoint identity. Verify rename and project isolation through the existing API test.

</frozen-after-approval>

## Implementation Notes

A separate current-name API field drives Evaluation and Playground; snapshot names and checkpoint identity remain unchanged. Existing API integration tests check renamed datasets and project isolation.

## Plan Change Log

## Review Triage Log

- Medium, patched: review identified missing cross-project coverage; added a second-project assertion and reran the integration test.

## Verification

- `.venv/bin/python -m pytest -q --tb=short backend/tests/test_inference_api.py -k renamed` — verifies live rename and historical name preservation in a temporary PostgreSQL database.
- `npm run typecheck --prefix frontend` — verifies the display contract.
