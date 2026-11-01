from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def make_pool(url: str) -> ConnectionPool:
    return ConnectionPool(url, min_size=1, max_size=5, timeout=5, open=False,
                          kwargs={"connect_timeout": 5, "row_factory": dict_row})


def migrate(pool: ConnectionPool) -> None:
    with pool.connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(734120501)")
        conn.execute("CREATE TABLE IF NOT EXISTS studio_migrations (name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
        for path in sorted((Path(__file__).resolve().parents[1] / "migrations").glob("*.sql")):
            if not conn.execute("SELECT 1 FROM studio_migrations WHERE name = %s", (path.name,)).fetchone():
                conn.execute(path.read_text())
                conn.execute("INSERT INTO studio_migrations (name) VALUES (%s)", (path.name,))
