from uuid import uuid4

import psycopg
from psycopg_pool import PoolTimeout


def draft():
    return {"id": str(uuid4()), "name": "Bangla Mini", "hardware": {}, "budget": {}, "successCriteria": {}, "revision": 0}


def test_project_lifecycle_uses_postgres_and_server_revisions(client, test_database):
    project = draft()
    created = client.post("/api/projects", json=project)
    assert created.status_code == 201
    saved = created.json()
    assert saved["revision"] == 1 and saved["updatedAt"]
    assert client.get(f"/api/projects/{saved['id']}").json() == saved
    assert saved in client.get("/api/projects").json()
    with psycopg.connect(test_database) as conn:
        row = conn.execute("SELECT document, revision FROM projects WHERE id = %s", (saved["id"],)).fetchone()
    assert row[0]["name"] == "Bangla Mini" and row[1] == 1
    saved["name"] = "Updated model"
    updated = client.patch(f"/api/projects/{saved['id']}", json=saved)
    assert updated.status_code == 200 and updated.json()["revision"] == 2
    assert client.patch(f"/api/projects/{saved['id']}", json=saved).status_code == 409
    assert client.post("/api/projects", json=project).status_code == 409
    assert client.get(f"/api/projects/{saved['id']}").json()["name"] == "Updated model"


def test_validation_and_scope_ready_gate_cannot_be_bypassed(client):
    for patch in [{"hardware": {"gpuCount": -1}}, {"hardware": {"gpuCount": 1.5}}, {"hardware": {"gpuCount": True}}, {"budget": {"maxHours": "10"}}, {"status": "scope-ready"}, {"sources": [{"id": "s", "permission": "forged"}]}]:
        assert client.post("/api/projects", json={**draft(), **patch}).status_code == 422
    assert client.post("/api/projects", json={**draft(), "budget": {"maxCost": 0}}).status_code == 201


def test_complete_scope_ready_and_permission_gate(client):
    p = {**draft(), "task": "chatbot", "language": "bn", "objective": "Learning", "hardware": {"location": "cloud", "status": "entered", "gpuModel": "Test GPU", "gpuCount": 1, "vramPerGpuGb": 24, "ramGb": 64, "freeDiskGb": 100}, "budget": {"maxHours": 10, "maxCost": 0}, "hasExistingData": False, "sources": [{"id": "s", "name": "Corpus", "reference": "/data", "language": "bn", "permissionNote": "Public domain", "permission": "confirmed"}], "successCriteria": {"qualityNotes": "Coherent fixed-prompt responses"}, "status": "scope-ready"}
    assert client.post("/api/projects", json=p).status_code == 201
    p["id"] = str(uuid4()); p["sources"][0]["permission"] = "unknown"
    assert client.post("/api/projects", json=p).status_code == 422


def test_not_found_mismatched_ids_and_origin(client):
    p = draft()
    assert client.get(f"/api/projects/{p['id']}").status_code == 404
    assert client.get("/api/projects/not-a-uuid").status_code == 422
    assert client.patch(f"/api/projects/{uuid4()}", json=p).status_code == 422
    assert client.post("/api/projects", json=p, headers={"Origin": "https://unrelated.example"}).status_code == 403
    assert client.get("/api/does-not-exist").status_code == 404
    assert client.get("/api/health").json()["database"] == "postgresql"


def test_unavailable_database_returns_actionable_503(client, monkeypatch):
    def unavailable(*args, **kwargs):
        raise PoolTimeout("internal connection details must not be exposed")
    monkeypatch.setattr(client.app.state.pool, "connection", unavailable)
    response = client.post("/api/projects", json=draft())
    assert response.status_code == 503
    assert "PostgreSQL is unavailable" in response.json()["detail"]
    assert "internal connection" not in response.text
