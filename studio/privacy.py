"""Task-scoped pseudonymisation; mapping remains an authenticated encrypted artifact."""

import base64
import hashlib
import json
import re
import secrets
from collections import Counter

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MARKER = re.compile(r"⟦PRIVATE_[A-F0-9]{16}_[0-9]{4}⟧")
PATTERNS = {
    "邮箱": r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "手机": r"(?<!\d)(?:\+86[ -]?)?1[3-9]\d{9}(?!\d)",
    "身份证候选": r"(?<![\w])[1-9]\d{16}[0-9Xx](?![\w])",
}


def detect(text: str) -> list[dict]:
    if len(text) > 500_000:
        raise ValueError("文本超过 50 万字符，请按文档拆分")
    found = {}
    for kind, pattern in PATTERNS.items():
        for match in re.finditer(pattern, text):
            found.setdefault(match.group(), kind)
    return [
        {"value": value, "kind": kind, "count": text.count(value)} for value, kind in found.items()
    ]


def redact(text: str, values: list[str]) -> tuple[str, dict]:
    if MARKER.search(text):
        raise ValueError("原文包含脱敏标记，请使用原始文档创建新任务")
    if len(text) > 500_000 or len(values) > 1000:
        raise ValueError("超过文本或替换项上限")
    values = sorted({v.strip() for v in values if v.strip()}, key=lambda x: (-len(x), x))
    if any(len(v) < 2 for v in values):
        raise ValueError("替换项至少两个字符，避免单字误替换")
    task = secrets.token_hex(8).upper()
    lookup = {value: f"⟦PRIVATE_{task}_{i:04d}⟧" for i, value in enumerate(values, 1)}
    counts = Counter()

    def substitute(match):
        counts[match.group()] += 1
        return lookup[match.group()]

    output = re.sub("|".join(map(re.escape, values)), substitute, text) if values else text
    mapping = {lookup[value]: value for value in values if counts[value]}
    # Overlapping entities can leave a shorter term as part of an unmatched phrase.
    leftovers = [value for value in values if value in output]
    if leftovers:
        raise ValueError("仍存在选定替换项，请检查重叠词或原文")
    envelope = {
        "schema": 1,
        "task": task,
        "mapping": mapping,
        "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "redacted_sha256": hashlib.sha256(output.encode()).hexdigest(),
        "occurrences": {key: output.count(key) for key in mapping},
    }
    return output, envelope


def _key(password: str, salt: bytes) -> bytes:
    if len(password) < 12 or len(password) > 256:
        raise ValueError("映射口令需为 12–256 个字符")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode())


def seal(mapping: dict, password: str) -> bytes:
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    ciphertext = AESGCM(_key(password, salt)).encrypt(
        nonce, json.dumps(mapping, ensure_ascii=False).encode(), b"private-knowledge-map-v1"
    )
    return json.dumps(
        {
            "format": "private-knowledge-map-v1",
            "salt": base64.b64encode(salt).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode(),
        }
    ).encode()


def unseal(blob: bytes, password: str) -> dict:
    if len(blob) > 2_000_000:
        raise ValueError("映射包过大")
    try:
        data = json.loads(blob)
        if data["format"] != "private-knowledge-map-v1":
            raise ValueError("不支持的映射包")
        salt, nonce, ciphertext = (
            base64.b64decode(data[k], validate=True) for k in ("salt", "nonce", "ciphertext")
        )
        if len(salt) != 16 or len(nonce) != 12:
            raise ValueError("映射包格式错误")
        plain = AESGCM(_key(password, salt)).decrypt(nonce, ciphertext, b"private-knowledge-map-v1")
        mapping = json.loads(plain)
        if mapping["schema"] != 1 or not isinstance(mapping["mapping"], dict):
            raise ValueError("映射结构不支持")
        if not all(
            MARKER.fullmatch(k)
            and k.startswith("⟦PRIVATE_" + mapping["task"] + "_")
            and isinstance(v, str)
            for k, v in mapping["mapping"].items()
        ):
            raise ValueError("映射任务不一致")
        return mapping
    except (InvalidTag, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("口令错误或映射包已损坏") from exc


def restore(text: str, envelope: dict) -> dict:
    mapping = envelope["mapping"]
    present = set(MARKER.findall(text))
    unknown = sorted(present - mapping.keys())
    missing = sorted(mapping.keys() - present)
    suspicious = [line[:240] for line in text.splitlines() if "PRIVATE" in MARKER.sub("", line)]
    if unknown or suspicious:
        return {
            "text": None,
            "unknown": unknown,
            "missing": missing,
            "suspicious": suspicious,
            "blocked": True,
        }
    output = MARKER.sub(lambda m: mapping[m.group()], text)
    return {
        "text": output,
        "unknown": [],
        "missing": missing,
        "suspicious": [],
        "blocked": False,
        "task": envelope["task"],
    }
