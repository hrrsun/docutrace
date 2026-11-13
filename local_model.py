"""Loopback-only Ollama transport. Never send documents to a configured proxy."""

import requests
import os


def post(route: str, payload: dict) -> dict:
    if route not in {"embed", "chat"}:
        raise ValueError("未知的 Ollama 接口")
    with requests.Session() as session:
        session.trust_env = False
        try:
            response = session.post(
                os.environ.get("OLLAMA_INTERNAL_URL", "http://127.0.0.1:11434") + f"/api/{route}",
                json=payload,
                timeout=(5, 240),
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Ollama {route} 请求失败：{exc}") from exc
        if response.status_code != 200:
            raise RuntimeError(f"Ollama {route} HTTP {response.status_code}: {response.text[:300]}")
        return response.json()
