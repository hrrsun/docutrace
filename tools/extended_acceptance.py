"""Synthetic accounts only: collaboration boundaries, privacy and sandbox acceptance."""

import json
import secrets
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    root = "http://127.0.0.1:18781/api/v1"
    studio = "http://127.0.0.1:18780/studio/api"
    a = requests.Session()
    a.trust_env = False
    credential = json.loads((ROOT / ".runtime/qa-account.json").read_text())
    login = a.post(root + "/auth/login", json=credential, timeout=10)
    login.raise_for_status()
    a.headers["Authorization"] = "Bearer " + login.json()["token"]
    b = requests.Session()
    b.trust_env = False
    other = ROOT / ".runtime/qa-account-second.json"
    if not other.exists():
        account = {
            "username": "collab-qa",
            "email": "qa-" + secrets.token_hex(5) + "@example.test",
            "password": secrets.token_urlsafe(18),
        }
        r = b.post(root + "/auth/register", json=account, timeout=15)
        r.raise_for_status()
        other.write_text(json.dumps(account))
    r = b.post(root + "/auth/login", json=json.loads(other.read_text()), timeout=15)
    r.raise_for_status()
    b.headers["Authorization"] = "Bearer " + r.json()["token"]
    state = json.loads((ROOT / ".runtime/qa-state.json").read_text())
    checks = []
    forbidden = b.post(
        studio + "/ask",
        json={"question": "BETA pressure", "libraries": [state["library"]]},
        timeout=15,
    )
    checks.append({"name": "unauthorized_library_denied", "ok": forbidden.status_code == 403})
    records = a.get(studio + "/records", timeout=15).json()["records"]
    assert records
    forbidden = b.get(studio + "/records/" + records[0]["id"], timeout=15)
    checks.append({"name": "other_users_record_denied", "ok": forbidden.status_code == 404})
    p = a.post(
        studio + "/privacy/redact",
        json={
            "text": "星河公司联系张三，13800138000。星河公司使用本地部署。",
            "values": ["星河公司", "张三", "13800138000"],
            "password": "Local-QA-Passphrase-2026",
        },
        timeout=20,
    )
    p.raise_for_status()
    v = p.json()
    restore = a.post(
        studio + "/privacy/restore",
        json={
            "text": v["text"],
            "mapping_package": v["mapping_package"],
            "password": "Local-QA-Passphrase-2026",
        },
        timeout=15,
    )
    restore.raise_for_status()
    checks.append(
        {
            "name": "encrypted_mapping_round_trip",
            "ok": "星河公司" not in v["text"] and "星河公司" in restore.json()["text"],
        }
    )
    wrong = a.post(
        studio + "/privacy/restore",
        json={
            "text": v["text"],
            "mapping_package": v["mapping_package"],
            "password": "wrong-QA-Passphrase-2026",
        },
        timeout=15,
    )
    checks.append({"name": "wrong_password_denied", "ok": wrong.status_code == 400})
    cross = b.post(
        studio + "/privacy/restore",
        json={
            "text": v["text"],
            "mapping_package": v["mapping_package"],
            "password": "Local-QA-Passphrase-2026",
        },
        timeout=15,
    )
    checks.append({"name": "mapping_owner_enforced", "ok": cross.status_code == 403})
    code = 'import os,socket\nprint(sum([17,71,48]))\nprint(os.path.exists("/workspace"))\ns=socket.socket();s.settimeout(1)\nprint(s.connect_ex(("1.1.1.1",443)))'
    result = a.post(studio + "/compute", json={"code": code}, timeout=40)
    result.raise_for_status()
    lines = result.json()["stdout"].splitlines()
    checks.append(
        {
            "name": "sandbox_compute_no_mount_no_network",
            "ok": lines[0] == "136" and lines[1] == "False" and lines[2] != "0",
            "stdout": lines,
        }
    )
    timeout = a.post(studio + "/compute", json={"code": "while True: pass"}, timeout=40)
    checks.append({"name": "sandbox_timeout", "ok": timeout.status_code == 422})
    # A dedicated test organization shares only this synthetic KB; no email or external message is sent.
    orgs = a.get(root + "/organizations", timeout=15).json()["data"]["organizations"]
    org = next((o for o in orgs if o["name"] == "本机合成协作验收"), None)
    if org is None:
        r = a.post(
            root + "/organizations",
            json={"name": "本机合成协作验收", "searchable": False, "require_approval": False},
            timeout=15,
        )
        r.raise_for_status()
        org = r.json()["data"]
    r = a.post(root + f"/organizations/{org['id']}/invite-code", json={}, timeout=15)
    r.raise_for_status()
    code_data = r.json()["data"]
    invite = code_data.get("invite_code") or code_data.get("code")
    if not invite:
        raise RuntimeError("组织邀请码响应与文档不一致")
    r = b.post(root + "/organizations/join", json={"invite_code": invite}, timeout=15)
    if r.status_code not in (200, 409):
        raise RuntimeError("测试空间加入失败")
    shares = a.get(root + f"/knowledge-bases/{state['library']}/shares", timeout=15).json()["data"][
        "shares"
    ]
    share = next((s for s in shares if s.get("organization_id") == org["id"]), None)
    if share is None:
        r = a.post(
            root + f"/knowledge-bases/{state['library']}/shares",
            json={"organization_id": org["id"], "permission": "viewer"},
            timeout=15,
        )
        r.raise_for_status()
        share = r.json()["data"]
    result = b.post(
        root + "/knowledge-search",
        json={
            "query": "BETA pressure",
            "knowledge_base_ids": [state["library"]],
            "rerank": {"enabled": False},
            "match_count": 3,
        },
        timeout=90,
    )
    result.raise_for_status()
    checks.append({"name": "authorized_shared_retrieval", "ok": bool(result.json().get("data"))})
    view = b.get(studio + "/libraries", timeout=15)
    view.raise_for_status()
    checks.append(
        {
            "name": "shared_library_visible_in_studio",
            "ok": any(k["id"] == state["library"] for k in view.json()["libraries"]),
        }
    )
    r = a.delete(root + f"/knowledge-bases/{state['library']}/shares/{share['id']}", timeout=15)
    r.raise_for_status()
    result = b.post(
        root + "/knowledge-search",
        json={
            "query": "BETA pressure",
            "knowledge_base_ids": [state["library"]],
            "rerank": {"enabled": False},
        },
        timeout=60,
    )
    denied = result.status_code in (403, 404) or not result.json().get("data")
    checks.append({"name": "sharing_revocation_effective", "ok": denied})
    forbidden = b.post(
        studio + "/ask",
        json={"question": "BETA pressure", "libraries": [state["library"]]},
        timeout=20,
    )
    checks.append({"name": "revoked_library_denied_in_studio", "ok": forbidden.status_code == 403})
    report = {"dataset": "synthetic-only", "checks": checks, "passed": all(c["ok"] for c in checks)}
    (ROOT / "docs/evidence/extended-acceptance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
