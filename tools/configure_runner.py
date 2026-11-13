from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
key = (root / ".runtime/runner.key").read_text().strip()
if not re.fullmatch(r"[A-Za-z0-9_-]{40,100}", key):
    raise ValueError("Invalid runner key")
env = root / "deploy/weknora/.env"
text = env.read_text(encoding="utf-8")
text = re.sub(r"^RUNNER_TOKEN=.*\n?", "", text, flags=re.M)
env.write_text(text.rstrip() + "\nRUNNER_TOKEN=" + key + "\n", encoding="utf-8")
