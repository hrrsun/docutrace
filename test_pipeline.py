import pytest
from demo import fixtures, evaluate
from engine import Index, prepare, ask
from ingest import Unit, parse, markdown


def test_cross_page_identity_and_alignment(tmp_path):
    paths = fixtures(tmp_path)
    units, _ = parse(paths[0])
    rows = [u for u in units if u.group]
    assert len(rows) == 4
    assert len({u.group for u in rows}) == 1
    assert "BETA | pressure | 71 kPa" in rows[2].text
    assert "第 2 页" in rows[2].loc
    assert markdown(rows).count("| Item | Metric |") == 1
    report = evaluate(paths)
    assert report["hit_at_3"] == 1


def test_budget_and_memory_survive_duplicates():
    units = [Unit("x", "1", "冷链保温 36 小时")] * 30
    parts, sources, ledger = prepare(
        Index(units), "冷链保温", [("以后只用中文回答", "好的")] * 100, 2048
    )
    assert len(sources) == 1
    assert "只用中文" in parts["history"]
    assert ledger["total"] <= 2048
    with pytest.raises(ValueError):
        prepare(Index(units), "汉" * 1000, [], 2048)


def test_unmatched_query_abstains():
    text, src, _ = ask(Index([Unit("x", "1", "abcd efgh")]), "无关问题", [])
    assert not src and "没有找到" in text


def test_image_only_page_reports_gap(tmp_path):
    import pymupdf

    path = tmp_path / "blank.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(path)
    doc.close()
    units, notes = parse(path)
    assert not units and "OCR" in notes[0]


def test_web_opens_without_model():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file("app.py").run(timeout=45)
    assert not app.exception
    assert app.title[0].value == "文档证据台"
    next(b for b in app.button if b.label == "试用示例文档").click().run()
    assert not app.exception
    assert app.chat_input


def test_all_rows_counted_without_model_or_retrieval(monkeypatch):
    from ingest import table_rows

    rows = (
        [["日期", "活动名称"]]
        + [["2026-06-01", "现场服务"]] * 24
        + [["2026年6月30日至2026年7月2日", "跨月服务"], ["······", "······"]]
    )
    idx = Index(table_rows("events.xlsx", rows, lambda r: f"A{r}:B{r}", "活动"))

    def forbidden(*args, **kwargs):
        raise AssertionError("计数路径不应调用模型或检索")

    monkeypatch.setattr(idx, "search", forbidden)
    monkeypatch.setattr("engine.post", forbidden)
    for q, expected in [("一共多少活动", 25), ("7月有多少活动", 1), ("8月有几场活动", 0)]:
        answer, refs, ledger = ask(idx, q, [], "configured")
        assert ledger["matched_rows"] == expected and ledger["valid_rows"] == 25
        assert "[S1]" in answer and refs[0].file == "events.xlsx"
