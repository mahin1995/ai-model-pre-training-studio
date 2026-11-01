import os
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def database_url() -> str:
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        if not explicit.startswith(("postgresql://", "postgres://")):
            raise ValueError("DATABASE_URL must use PostgreSQL.")
        return explicit
    password = os.getenv("POSTGRES_PASSWORD", "")
    if not password or password == "change-me":
        raise ValueError("Set POSTGRES_PASSWORD or DATABASE_URL in .env. Run python3 scripts/dev.py for local setup.")
    user = quote(os.getenv("POSTGRES_USER", "studio"), safe="")
    name = quote(os.getenv("POSTGRES_DB", "pretraining_studio"), safe="")
    return f"postgresql://{user}:{quote(password, safe='')}@127.0.0.1:{int(os.getenv('POSTGRES_PORT', '55432'))}/{name}"
