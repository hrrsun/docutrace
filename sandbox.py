"""Explicit user-initiated Python execution in a disposable Linux container."""

import subprocess
import threading
import uuid
import json


def run_python(code):
    if len(code) > 8000:
        raise ValueError("代码过长")
    name = "docagent-" + uuid.uuid4().hex
    args = [
        "docker",
        "run",
        "--pull=never",
        "--rm",
        "--name",
        name,
        "-i",
        "--network=none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=8m",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=32",
        "--memory=128m",
        "--memory-swap=128m",
        "--cpus=0.5",
        "--user=65534:65534",
        "--log-driver=none",
        "python:3.12-alpine",
        "python",
        "-I",
        "-B",
        "-",
    ]
    proc = subprocess.Popen(
        args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    data = bytearray()

    def drain():
        while chunk := proc.stdout.read(4096):
            data.extend(chunk[: max(0, 8192 - len(data))])

    thread = threading.Thread(target=drain, daemon=True)
    thread.start()
    try:
        proc.stdin.write(code.encode())
        proc.stdin.close()
        status = proc.wait(timeout=12)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError("计算超过 12 秒，已终止")
    finally:
        if proc.poll() is None:
            proc.kill()
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10)
        thread.join(timeout=2)
    if status:
        raise RuntimeError(data.decode(errors="replace")[:1000])
    return json.dumps({"stdout": data.decode(errors="replace"), "exit": status}, ensure_ascii=False)
