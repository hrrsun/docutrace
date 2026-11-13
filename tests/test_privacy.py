import json
import pytest
from studio import privacy


def test_mapping_round_trip_and_ciphertext():
    original = "星河公司联系张三：13800138000，邮箱 zhang@example.com。星河公司要求下周交付。"
    values = ["星河公司", "张三"] + [item["value"] for item in privacy.detect(original)]
    redacted, mapping = privacy.redact(original, values)
    assert "星河公司" not in redacted and "13800138000" not in redacted
    package = privacy.seal(mapping, "a sufficiently long passphrase")
    assert "星河公司".encode() not in package
    restored = privacy.restore(redacted, privacy.unseal(package, "a sufficiently long passphrase"))
    assert restored["text"] == original and not restored["missing"]


def test_wrong_password_tampering_and_cross_task():
    text, mapping = privacy.redact("星河公司需求", ["星河公司"])
    blob = privacy.seal(mapping, "very-long-password")
    with pytest.raises(ValueError):
        privacy.unseal(blob, "another-long-password")
    corrupt = json.loads(blob)
    corrupt["nonce"] = "AAAAAAAAAAAAAAAA"
    with pytest.raises(ValueError):
        privacy.unseal(json.dumps(corrupt).encode(), "very-long-password")
    other, other_map = privacy.redact("星河公司需求", ["星河公司"])
    assert privacy.restore(other, mapping)["blocked"]
    assert privacy.restore(text.replace("PRIVATE", "PRIVATE-X"), mapping)["blocked"]


def test_overlap_literal_and_missing():
    text, mapping = privacy.redact("张三丰与张三参加 A+B 项目", ["张三", "张三丰", "A+B"])
    assert len(mapping["mapping"]) == 3
    assert privacy.restore(text, mapping)["text"] == "张三丰与张三参加 A+B 项目"
    shortened = privacy.restore("这里没有任何占位符", mapping)
    assert shortened["missing"] and shortened["text"] == "这里没有任何占位符"


def test_limits_and_short_password():
    with pytest.raises(ValueError):
        privacy.redact("姓名", ["姓"])
    with pytest.raises(ValueError):
        privacy.seal({}, "short")
    with pytest.raises(ValueError):
        privacy.detect("x" * 500001)
