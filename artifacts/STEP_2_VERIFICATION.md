# Step 2 verification

Verified locally on 2026-11-01 (Asia/Dhaka).

## Automated checks

- `npm run build --prefix frontend`: TypeScript and production build passed.
- `npm test --prefix frontend`: **13 tests passed** (scope validation, HTTP persistence adapter, error/conflict handling, legacy draft import).
- `.venv/bin/python -m pytest -q`: **9 tests passed**, using a real isolated PostgreSQL test database for the API tests.
- Backend tests cover persisted JSONB documents/revisions, duplicate creation, optimistic concurrency, strict schema validation, permission/readiness gates, missing IDs, origin handling, 503 database errors, missing PyTorch, CUDA visibility, timeouts and inaccessible disk paths.
- Backend test client emitted one upstream Starlette deprecation warning about HTTPX; tests passed.
- npm installation/audit reported 0 vulnerabilities.

## Running services and persistence

- `python3 scripts/dev.py` successfully started Docker PostgreSQL, migrations, FastAPI and Vite.
- Existing-project frontend server was replaced with the unified launcher on the same frontend port.
- PostgreSQL was stopped while the API ran: `/api/health` returned the expected actionable **503** without database credentials.
- PostgreSQL was started again: saved projects, values and revisions survived unchanged.
- Python served the built frontend at `/` alongside `/api/health` and `/api/projects` successfully.
- Browser QA used uniquely identified disposable project records; only those records were removed after checking. Original browser drafts were not changed.

## Browser checks

Headless local Chrome with temporary Playwright/Axe tooling; desktop 1440×1100 and mobile 390×844.

Passed: PostgreSQL project creation, reload restoration, multiple-project selection, conflicting edits across two tabs, failed-save retention, explicit non-destructive browser-draft import, real environment checks, retry after a probe error, disabled hardware copy when PyTorch visibility is unverified, and mobile layouts without horizontal overflow.

No uncaught browser errors during those flows. Axe WCAG A/AA checks reported no violations in the checked desktop/mobile Environment, updated Overview, and mobile setup snapshots. These automated snapshots are not an exhaustive accessibility audit.

## Actual environment result

The backend environment runs Python 3.14.4. The NVIDIA driver reports an RTX 3060 with 12 GB VRAM. RAM and disk checks return real host measurements. PyTorch, Transformers, Datasets and Tokenizers are not installed in the new backend `.venv`; the UI correctly reports missing packages and unverified PyTorch CUDA access. No training packages or drivers were installed, and no training run was started.

## Screenshots

- [Environment desktop](environment-desktop.png)
- [Environment mobile](environment-mobile.png)
- [PostgreSQL overview](overview-postgres.png)
- [PostgreSQL setup mobile](setup-postgres-mobile.png)
