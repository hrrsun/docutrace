from studio.rerank import rank


def test_lexical_rank_normalized_and_stable():
    results = rank("BETA pressure", ["ALPHA voltage 24V", "BETA pressure 71kPa", "无关资料"])
    assert results[0]["index"] == 1
    assert all(0 <= r["score"] <= 1 for r in results)
    assert len({r["index"] for r in results}) == 3
