"""Live, synthetic-only integration acceptance against the local WeKnora deployment."""

import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/evidence/live-acceptance.json"


def main():
    session = requests.Session()
    session.trust_env = False
    base = "http://127.0.0.1:18781/api/v1"
    credpath = ROOT / ".runtime/qa-account.json"
    if not credpath.exists():
        raise RuntimeError("缺少本地专用 QA 账号")
    cred = json.loads(credpath.read_text())
    response = session.post(base + "/auth/login", json=cred, timeout=10)
    response.raise_for_status()
    token = response.json()["token"]
    session.headers["Authorization"] = "Bearer " + token
    checks = []

    def request(method, path, **kwargs):
        result = session.request(method, base + path, timeout=180, **kwargs)
        if result.status_code not in range(200, 300):
            raise RuntimeError(f"{path} HTTP {result.status_code}: {result.text[:250]}")
        return result.json()

    models = request("GET", "/models")["data"]
    ids = {}
    for kind, name in [("KnowledgeQA", "qwen3:30b-a3b"), ("Embedding", "bge-m3:latest")]:
        existing = next((m for m in models if m["name"] == name and m["type"] == kind), None)
        if not existing:
            result = request(
                "POST",
                "/models",
                json={
                    "name": name,
                    "type": kind,
                    "source": "local",
                    "parameters": {
                        "base_url": "http://host.docker.internal:11434",
                        "provider": "ollama",
                        "dimension": 1024 if kind == "Embedding" else 0,
                        "context_window": 8192,
                    },
                },
            )
            existing = result["data"]
        ids[kind] = existing["id"]
    checks.append({"name": "local_models", "ok": True})
    libraries = request("GET", "/knowledge-bases")["data"]
    library = next((k for k in libraries if k["name"] == "集成验收合成资料"), None)
    if not library:
        library = request(
            "POST",
            "/knowledge-bases",
            json={
                "name": "集成验收合成资料",
                "type": "document",
                "embedding_model_id": ids["Embedding"],
                "summary_model_id": ids["KnowledgeQA"],
                "chunking_config": {"chunk_size": 700, "chunk_overlap": 80},
            },
        )["data"]
    state = {"token": token, "library": library["id"], "models": ids}
    (ROOT / ".runtime/qa-state.json").write_text(json.dumps(state))
    print("QA models and library ready", flush=True)
    studio = "http://127.0.0.1:18780/studio/api"
    r = session.get(studio + "/me", timeout=15)
    r.raise_for_status()
    checks.append({"name": "studio_identity", "ok": bool(r.json().get("name"))})
    path = ROOT / "examples/spec.pdf"
    with path.open("rb") as stream:
        r = session.post(
            studio + "/import",
            files={"file": ("spec.pdf", stream, "application/pdf")},
            data={"kb": library["id"], "course": "系统集成", "semester": "2026"},
            timeout=120,
        )
    r.raise_for_status()
    checks.append({"name": "structured_import", "ok": True})
    for attempt in range(36):
        data = request(
            "POST",
            "/knowledge-search",
            json={
                "query": "BETA pressure",
                "knowledge_base_ids": [library["id"]],
                "match_count": 5,
                "rerank": {"enabled": False},
            },
        )
        if any("71" in str(row) for row in data.get("data") or []):
            checks.append({"name": "indexed_retrieval", "ok": True})
            break
        time.sleep(5)
    else:
        raise RuntimeError("资料未在时限内完成索引")
    r = session.post(
        studio + "/ask",
        json={
            "question": "BETA 的 pressure 要求是多少？请给出单位和引用。",
            "libraries": [library["id"]],
            "mode": "ask",
            "budget": 8192,
        },
        timeout=300,
    )
    r.raise_for_status()
    record = r.json()
    turn = record["body"]["turns"][-1]
    checks.append(
        {
            "name": "answer_value_and_citation",
            "ok": "71" in turn["answer"] and bool(turn["sources"]),
            "answer": turn["answer"],
            "ledger": turn["ledger"],
        }
    )
    r = session.get(studio + "/records/" + record["id"] + "/export", timeout=15)
    r.raise_for_status()
    checks.append({"name": "saved_export", "ok": "71" in r.text})
    r = session.put(
        studio + "/records/" + record["id"],
        json={"revision": record["revision"], "text": "验收编辑版本 71 kPa"},
        timeout=15,
    )
    r.raise_for_status()
    checks.append({"name": "edit_revision", "ok": r.json()["revision"] == record["revision"] + 1})
    report = {"data": "synthetic-only", "checks": checks, "passed": all(c["ok"] for c in checks)}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
