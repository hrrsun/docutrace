"""Verify that native WeKnora actually calls the registered local tools."""

import json
from pathlib import Path
import requests

root = Path(__file__).resolve().parents[1]
s = requests.Session()
s.trust_env = False
creds = json.loads((root / ".runtime/qa-account.json").read_text())
r = s.post("http://127.0.0.1:18781/api/v1/auth/login", json=creds, timeout=15)
r.raise_for_status()
s.headers["Authorization"] = "Bearer " + r.json()["token"]
api = "http://127.0.0.1:18781/api/v1"
r = s.post("http://127.0.0.1:18780/studio/api/setup-agent", timeout=60)
r.raise_for_status()
agent = r.json()["agent_id"]
r = s.post(api + "/sessions", json={"title": "合成工具调用验收"}, timeout=15)
r.raise_for_status()
sid = r.json()["data"]["id"]
query = (
    "请用 check_threshold 工具核对以下用户提供的合成数据，然后用一句话解释结果："
    "要求至少71 kPa，实测72 kPa，requirement_source 为 spec.pdf 第2页表1行2，"
    "measurement_source 为 acceptance.pdf 第1页表1行2，relation 为 minimum。不要自行心算代替工具。"
)
events = []
with s.post(
    api + "/agent-chat/" + sid,
    json={
        "query": query,
        "agent_id": agent,
        "reasoning_effort": "off",
        "web_search_enabled": False,
    },
    stream=True,
    timeout=(10, 300),
) as response:
    response.raise_for_status()
    for line in response.iter_lines(chunk_size=1):
        if line.startswith(b"data:"):
            try:
                events.append(json.loads(line[5:].decode()))
            except ValueError:
                pass
            if events and events[-1].get("type") in {"complete", "error"}:
                break
text = json.dumps(events, ensure_ascii=False)
tool_events = [event for event in events if "tool" in str(event.get("type", ""))]
report = {
    "synthetic": True,
    "session": sid,
    "event_count": len(events),
    "tool_events": tool_events,
    "events": events,
    "tool_name_seen": any("check_threshold" in json.dumps(event) for event in tool_events),
}
(root / "docs/evidence/native-agent-acceptance.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(report, ensure_ascii=False, indent=2))
if not report["tool_name_seen"]:
    raise SystemExit(1)
