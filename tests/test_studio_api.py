from fastapi.testclient import TestClient
import pytest
from studio.api import app
from studio import platform, store


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB", str(tmp_path / "store.db"))

    def fake(method, path, token="", **kwargs):
        if path == "/auth/me":
            if token not in {"alice", "bob"}:
                from fastapi import HTTPException

                raise HTTPException(401, "invalid")
            return {
                "data": {
                    "tenant": {"id": 10},
                    "user": {"id": token, "username": token, "tenant_id": 1},
                }
            }
        if path == "/knowledge-bases":
            return {"data": [{"id": "kb-" + token, "name": token}]}
        if path == "/shared-knowledge-bases":
            return {"data": []}
        if path == "/knowledge-search":
            return {"data": []}
        raise AssertionError(path)

    monkeypatch.setattr(platform, "call", fake)
    return TestClient(app)


def test_endpoints_need_identity(client):
    assert client.get("/studio/api/libraries").status_code == 401
    assert client.post("/studio/api/privacy/detect", json={"text": "abc"}).status_code == 401
    assert client.get("/studio/").status_code == 200


def test_cross_user_scope_and_saved_artifacts(client):
    alice = {"Authorization": "Bearer alice"}
    bob = {"Authorization": "Bearer bob"}
    result = client.post(
        "/studio/api/ask", headers=alice, json={"question": "test", "libraries": ["kb-bob"]}
    )
    assert result.status_code == 403
    saved = store.save(
        "10:alice",
        "conversation",
        "private",
        {"libraries": ["kb-alice"], "turns": [{"answer": "value", "sources": []}]},
    )
    assert client.get("/studio/api/records/" + saved["id"], headers=bob).status_code == 404
    assert (
        client.get("/studio/api/records/" + saved["id"] + "/export", headers=bob).status_code == 404
    )
    assert client.get("/studio/api/records", headers=bob).json()["records"] == []
    response = client.get(
        "/studio/api/records/" + saved["id"] + "/export?format=docx", headers=alice
    )
    assert response.status_code == 200 and response.content[:2] == b"PK"


def test_no_evidence_does_not_invent_answer(client):
    r = client.post(
        "/studio/api/ask",
        headers={"Authorization": "Bearer alice"},
        json={"question": "无法回答的问题", "libraries": ["kb-alice"]},
    )
    assert r.status_code == 200
    assert "没有找到" in r.json()["body"]["turns"][0]["answer"]


def test_privacy_api_never_persists_mapping(client):
    headers = {"Authorization": "Bearer alice"}
    r = client.post(
        "/studio/api/privacy/redact",
        headers=headers,
        json={
            "text": "星河公司联系 13800138000",
            "values": ["星河公司", "13800138000"],
            "password": "test-private-passphrase",
        },
    )
    assert r.status_code == 200
    result = r.json()
    assert "星河公司" not in result["text"]
    restored = client.post(
        "/studio/api/privacy/restore",
        headers=headers,
        json={
            "text": result["text"],
            "mapping_package": result["mapping_package"],
            "password": "test-private-passphrase",
        },
    )
    assert restored.json()["text"] == "星河公司联系 13800138000"
    denied = client.post(
        "/studio/api/privacy/restore",
        headers={"Authorization": "Bearer bob"},
        json={
            "text": result["text"],
            "mapping_package": result["mapping_package"],
            "password": "test-private-passphrase",
        },
    )
    assert denied.status_code == 403
    assert store.listing("10:alice", "conversation") == []
