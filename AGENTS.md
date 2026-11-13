# Repository Guidelines

## Project Structure & Module Organization

- `frontend/src/`: React/TypeScript UI. Components live in `components/`, API adapters in `services/`, shared contracts in `types/`, and project validation in `features/project-setup/`.
- `backend/app/`: FastAPI application; dataset import, cleaning, storage and background jobs live in `datasets/`.
- `backend/migrations/`: numbered PostgreSQL migrations, such as `002_datasets.sql`. Add migrations instead of rewriting applied ones.
- `backend/tests/`: Python tests. Frontend tests sit beside modules as `*.test.ts`.
- `scripts/dev.py`: local launcher. `artifacts/` holds screenshots and verification notes; root Markdown files document milestones.

## Build, Test, and Development Commands

Run from the repository root:

- `python3 scripts/dev.py`: configure dependencies, start PostgreSQL, apply migrations, and launch API/UI.
- `npm run typecheck --prefix frontend`: check TypeScript.
- `npm test --prefix frontend`: run Vitest tests.
- `npm run build --prefix frontend`: type-check and generate the production frontend.
- `.venv/bin/python -m pytest -q --tb=short`: run backend tests.
- `.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000`: serve API and built UI together.

## Coding Style & Naming Conventions

Use two-space indentation in TypeScript/CSS and four spaces in Python. Name React components/types in PascalCase, JavaScript functions in camelCase, and Python functions/modules in snake_case. Follow existing API field names. Keep HTTP calls in frontend services and validation in backend schemas. No formatter or linter is configured; match surrounding code and avoid unrelated reformatting.

## Testing Guidelines

Use Vitest and pytest; Python tests follow `test_*.py`/`test_*` naming. No coverage threshold is configured. Test changed behavior, validation, project isolation, failure handling and artifact integrity. Integration tests require real PostgreSQL and create a temporary database using a role with `CREATEDB`; alternatively configure a dedicated `TEST_DATABASE_URL` containing `test`. Never target production data. Keep queued test jobs from contaminating subsequent tests.

## Commit & Pull Request Guidelines

History uses concise `feat:` subjects; follow that style and use `fix:` for corrections. Keep commits focused. PRs should explain behavior changes, list validation commands/results, reference relevant issues or milestones, and include screenshots for UI changes. Mention migrations and dependency changes explicitly.

## Configuration & Data Safety

Keep `.env`, credentials, uploads and checkpoints untracked. PostgreSQL stores metadata; `STUDIO_DATA_DIR` stores artifacts. Preserve originals, provenance and immutable versions. Keep related PDF pages in the same split. Train tokenizers only on training data. Preserve existing uncommitted work and update milestone documentation only after verification.
