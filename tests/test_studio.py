import pytest
from studio import store, context


def test_records_isolation_and_revision(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DB", str(tmp_path / "workspace.db"))
    r = store.save("alice", "conversation", "title", {"x": 1})
    with pytest.raises(KeyError):
        store.get("bob", r["id"])
    assert store.listing("bob", "conversation") == []
    changed = store.save("alice", "conversation", "updated", {"x": 2}, r["id"], 1)
    assert changed["revision"] == 2
    with store.connect() as db:
        assert (
            db.execute("SELECT count(*) FROM revisions WHERE record_id=?", (r["id"],)).fetchone()[0]
            == 2
        )
    with pytest.raises(ValueError):
        store.save("alice", "conversation", "old", {}, r["id"], 1)
    with pytest.raises(ValueError):
        store.save("bob", "conversation", "attack", {}, r["id"], 2)


def test_budget_and_whole_table_rows():
    rows = [
        {
            "id": "p2",
            "content": "| 对象 | 压力 |\n|---|---|\n| BETA | 71 kPa |",
            "knowledge_title": "参数表",
        }
    ] * 20
    msgs, sources, ledger = context.prepare("BETA 压力", rows, [], "ask", "使用中文", 4096)
    assert len(sources) == 1
    assert "71 kPa" in msgs[-1]["content"]
    assert ledger["estimated_total"] <= 4096
    with pytest.raises(ValueError):
        context.prepare("汉" * 3000, rows, [], "ask", "", 2048)


def test_user_constraints_are_preserved():
    turns = [{"question": "以后只用中文并保留单位", "answer": "好的"}] * 30
    _, _, ledger = context.prepare(
        "解释参数", [{"content": "BETA 71 kPa", "id": "1"}], turns, "review", "只看2026版", 4096
    )
    assert ledger["constraints_estimate"] > 0 and ledger["estimated_total"] <= 4096
