import os
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest
from fastapi.testclient import TestClient

from app.config import database_url
from app.main import create_app


@pytest.fixture(scope="session")
def test_database():
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        # Only use a database explicitly named as a test database.
        if "test" not in conninfo_to_dict(explicit).get("dbname", ""):
            raise ValueError("TEST_DATABASE_URL must point to a dedicated database with 'test' in its name.")
        yield explicit
        return
    config = conninfo_to_dict(database_url())
    name = f"studio_test_{uuid4().hex}"
    with psycopg.connect(make_conninfo(**{**config, "dbname": "postgres"}), autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            yield make_conninfo(**{**config, "dbname": name})
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def client(test_database):
    with TestClient(create_app(test_database)) as client:
        yield client
