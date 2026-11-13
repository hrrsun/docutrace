"""Create private per-install credentials exactly once."""

from pathlib import Path
import secrets
import re

root = Path(__file__).resolve().parent
env = root / ".env"
if not env.exists():
    text = (root / ".env.example").read_text("utf-8")
    settings = {
        "WEKNORA_VERSION": "v0.9.0",
        "FRONTEND_PORT": "127.0.0.1:18780",
        "APP_PORT": "127.0.0.1:18781",
        "DB_PASSWORD": secrets.token_hex(24),
        "REDIS_PASSWORD": secrets.token_hex(24),
        "JWT_SECRET": secrets.token_hex(32),
        "SYSTEM_AES_KEY": secrets.token_hex(16),
    }
    for key, value in settings.items():
        text, n = re.subn(rf"^{key}=.*$", f"{key}={value}", text, flags=re.M)
        if n != 1:
            raise ValueError(f"Unexpected upstream template: {key}")
    with env.open("x", encoding="utf-8") as out:
        out.write(text)
