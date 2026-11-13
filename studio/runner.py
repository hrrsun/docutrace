"""Host-side narrow Docker executor. No Docker socket is mounted into web containers."""

import json
import secrets
import threading
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from sandbox import run_python

ROOT = Path(__file__).resolve().parents[1]
KEY_FILE = ROOT / ".runtime/runner.key"
app = FastAPI(docs_url=None, redoc_url=None)
lock = threading.Lock()


def secret():
    return KEY_FILE.read_text().strip()


class Job(BaseModel):
    code: str = Field(min_length=1, max_length=8000)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/execute")
def execute(job: Job, authorization: str = Header(default="")):
    if not secrets.compare_digest(authorization, "Bearer " + secret()):
        raise HTTPException(401, "未授权")
    if not lock.acquire(blocking=False):
        raise HTTPException(429, "另一个计算正在执行，请稍后重试")
    try:
        return json.loads(run_python(job.code))
    except (RuntimeError, FileNotFoundError) as exc:
        raise HTTPException(422, str(exc)[:1000]) from exc
    finally:
        lock.release()


if __name__ == "__main__":
    import uvicorn

    KEY_FILE.parent.mkdir(exist_ok=True)
    if not KEY_FILE.exists():
        KEY_FILE.write_text(secrets.token_urlsafe(32))
    uvicorn.run(app, host="127.0.0.1", port=18783, access_log=False)
