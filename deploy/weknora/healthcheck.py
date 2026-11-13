"""Read-only readiness checks. Does not authenticate as any platform user."""

import json
import subprocess
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent


def check() -> dict:
    result = {"checks": [], "ready": True}
    with requests.Session() as session:
        session.trust_env = False
        for name, url in [
            ("web", "http://127.0.0.1:18780"),
            ("studio", "http://127.0.0.1:18780/studio/health"),
            ("api", "http://127.0.0.1:18781/health"),
            ("ollama", "http://127.0.0.1:11434/api/tags"),
        ]:
            try:
                response = session.get(url, timeout=5, allow_redirects=False)
                ok = response.status_code == 200
                if name == "api":
                    ok = ok and response.json().get("status") == "ok"
                if name == "ollama":
                    models = {m["name"] for m in response.json().get("models", [])}
                    ok = ok and {"bge-m3:latest", "knowledge-local:latest"}.issubset(models)
                item = {"name": name, "ok": ok, "http": response.status_code}
            except (requests.RequestException, ValueError) as exc:
                item = {"name": name, "ok": False, "error": type(exc).__name__}
            result["checks"].append(item)
        process = subprocess.run(
            ["docker", "compose", "-p", "docagent", "ps", "--format", "json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
        )
        if process.returncode:
            result["checks"].append({"name": "containers", "ok": False})
        else:
            services = [json.loads(line) for line in process.stdout.splitlines() if line.strip()]
            expected = {
                "app",
                "frontend",
                "postgres",
                "redis",
                "docreader",
                "evidence-tools",
                "studio",
            }
            running = {
                row["Service"]
                for row in services
                if row["State"] == "running" and row.get("Health", "") in {"", "healthy"}
            }
            result["checks"].append(
                {"name": "containers", "ok": expected.issubset(running), "running": sorted(running)}
            )
    result["ready"] = all(row["ok"] for row in result["checks"])
    return result


if __name__ == "__main__":
    report = check()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["ready"] else 1)
