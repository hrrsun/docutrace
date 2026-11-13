"""Create a project alias from a local, instruction-tuned model without downloading weights."""

from pathlib import Path
import subprocess
import requests

root = Path(__file__).resolve().parents[1]
with requests.Session() as session:
    session.trust_env = False
    response = session.post(
        "http://127.0.0.1:11434/api/show", json={"model": "qwen2.5:3b"}, timeout=10
    )
    if response.status_code != 200:
        raise RuntimeError("First prepare the local model with: ollama pull qwen2.5:3b")
target = root / ".runtime/knowledge.Modelfile"
target.parent.mkdir(exist_ok=True)
target.write_text(
    "FROM qwen2.5:3b\nPARAMETER num_ctx 8192\nPARAMETER temperature 0.15\n", encoding="utf-8"
)
subprocess.run(
    ["ollama", "create", "knowledge-local", "-f", str(target)],
    check=True,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
agent = root / ".runtime/agent.Modelfile"
agent.write_text(
    "FROM qwen3:30b-a3b\nPARAMETER num_ctx 16384\nPARAMETER temperature 0.1\n", encoding="utf-8"
)
subprocess.run(
    ["ollama", "create", "knowledge-agent", "-f", str(agent)],
    check=True,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
