"""Fixed-destination WeKnora adapter. No cloud URLs or caller-controlled proxy paths."""

import os
import requests
from fastapi import HTTPException

BASE = os.environ.get("WEKNORA_INTERNAL_URL", "http://127.0.0.1:18781")


def call(method, path, token="", **kwargs):
    with requests.Session() as session:
        session.trust_env = False
        try:
            response = session.request(
                method,
                BASE + "/api/v1" + path,
                headers={"Authorization": "Bearer " + token} if token else {},
                timeout=(5, 120),
                allow_redirects=False,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise HTTPException(503, "知识库平台暂时不可用") from exc
    if response.status_code not in range(200, 300):
        message = (
            "登录已过期或没有访问权限" if response.status_code in (401, 403) else "平台请求失败"
        )
        raise HTTPException(
            response.status_code if response.status_code in (400, 401, 403, 404, 409) else 502,
            f"{message}（HTTP {response.status_code}）",
        )
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(502, "平台返回格式不正确") from exc
