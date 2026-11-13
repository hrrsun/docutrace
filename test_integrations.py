import subprocess
import pytest
import engine
import sandbox
from ingest import Unit


def test_ollama_contract(monkeypatch):
    def reply(route, payload):
        assert route == "chat"
        assert payload["stream"] is False
        assert "71 kPa" in payload["messages"][1]["content"]
        assert payload["options"]["num_ctx"] == 2048
        return {"message": {"content": "71 kPa [S1]"}, "prompt_eval_count": 76}

    monkeypatch.setattr(engine, "post", reply)
    answer, refs, ledger = engine.ask(
        engine.Index([Unit("test", "p2", "BETA 71 kPa")]), "BETA", [], "example", 2048
    )
    assert refs and "[S1]" in answer and ledger["actual_prompt_tokens"] == 76


def test_invalid_embedding_count(monkeypatch):
    monkeypatch.setattr(engine, "post", lambda route, payload: {"embeddings": []})
    with pytest.raises(ValueError, match="条数"):
        engine.embed(["x"], "model")


def test_docker_unavailable_never_executes_on_host(monkeypatch):
    def missing(args, **kwargs):
        assert args[0] == "docker"
        for limit in (
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--pids-limit=32",
            "--pull=never",
        ):
            assert limit in args
        assert not any(x in args for x in ("-v", "--mount", "--privileged"))
        raise FileNotFoundError("docker missing")

    monkeypatch.setattr(subprocess, "Popen", missing)
    with pytest.raises(FileNotFoundError):
        sandbox.run_python("print(1)")
