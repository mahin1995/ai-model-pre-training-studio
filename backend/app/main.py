import logging
import os
from contextlib import asynccontextmanager
from datetime import timezone
from pathlib import Path
from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from psycopg.types.json import Jsonb
from psycopg_pool import PoolTimeout

from .config import ROOT, database_url
from .database import make_pool, migrate
from .environment import inspect_environment
from .schemas import Project

# Pool messages may include connection details; return actionable generic errors instead.
logging.getLogger("psycopg.pool").setLevel(logging.CRITICAL)


def create_app(url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        pool = make_pool(url or database_url())
        app.state.pool = pool
        try:
            pool.open(wait=True, timeout=12)
            migrate(pool)
        except Exception:
            pool.close()
            raise RuntimeError("PostgreSQL startup failed. Check your .env connection settings and database availability.") from None
        try:
            yield
        finally:
            pool.close()

    app = FastAPI(title="Pre-training Studio API", version="0.2.0", lifespan=lifespan)

    @app.middleware("http")
    async def local_origins(request: Request, call_next):
        origin = request.headers.get("origin")
        port = os.getenv("FRONTEND_PORT", "5173")
        api_port = os.getenv("API_PORT", "8000")
        allowed = {f"http://{host}:{p}" for host in ("localhost", "127.0.0.1") for p in (port, api_port)}
        if origin and request.method not in {"GET", "HEAD", "OPTIONS"} and origin not in allowed:
            return JSONResponse({"detail": "This local workspace does not accept requests from that origin."}, status_code=403)
        return await call_next(request)

    @app.exception_handler(psycopg.OperationalError)
    @app.exception_handler(PoolTimeout)
    def database_unavailable(_request, _exc):
        return JSONResponse({"detail": "PostgreSQL is unavailable. Check the database service and retry; your edits have not been saved."}, status_code=503)

    def serialize(row) -> dict:
        return {**row["document"], "id": str(row["id"]), "revision": row["revision"],
                "updatedAt": row["updated_at"].astimezone(timezone.utc).isoformat()}

    @app.get("/api/health")
    def health(request: Request):
        with request.app.state.pool.connection() as conn:
            conn.execute("SELECT 1")
        return {"status": "ok", "database": "postgresql"}

    @app.get("/api/projects", response_model=list[Project])
    def projects(request: Request):
        with request.app.state.pool.connection() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC, id").fetchall()
        return [serialize(row) for row in rows]

    @app.get("/api/projects/{project_id}", response_model=Project)
    def get_project(project_id: UUID, request: Request):
        with request.app.state.pool.connection() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = %s", (project_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Project not found.")
        return serialize(row)

    @app.post("/api/projects", response_model=Project, status_code=201)
    def create_project(project: Project, request: Request):
        if project.revision != 0:
            raise HTTPException(409, "This project already has a saved revision. Reload it before saving.")
        with request.app.state.pool.connection() as conn:
            row = conn.execute("INSERT INTO projects (id, document) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING RETURNING *",
                               (project.id, Jsonb(project.model_dump(mode="json", exclude={"revision", "updatedAt"})))).fetchone()
        if row is None:
            raise HTTPException(409, "This project is already saved. Reload it before saving again.")
        return serialize(row)

    @app.patch("/api/projects/{project_id}", response_model=Project)
    def update_project(project_id: UUID, project: Project, request: Request):
        if project.id != project_id:
            raise HTTPException(422, "Project ID must match the URL.")
        with request.app.state.pool.connection() as conn:
            row = conn.execute("UPDATE projects SET document = %s, revision = revision + 1, updated_at = clock_timestamp() WHERE id = %s AND revision = %s RETURNING *",
                               (Jsonb(project.model_dump(mode="json", exclude={"revision", "updatedAt"})), project_id, project.revision)).fetchone()
            if row is None:
                exists = conn.execute("SELECT 1 FROM projects WHERE id = %s", (project_id,)).fetchone()
                raise HTTPException(409 if exists else 404, "This project changed in another tab. Reload before saving; your edits are still open." if exists else "Project not found.")
        return serialize(row)

    @app.get("/api/environment")
    def environment():
        return inspect_environment()

    # API routes must retain JSON 404 responses even when static assets are served.
    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
    def unknown_api(path: str):
        raise HTTPException(404, "API route not found.")

    dist = ROOT / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=Path(dist), html=True), name="frontend")
    return app


app = create_app()
