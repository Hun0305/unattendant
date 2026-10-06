"""비밀값 읽기. 값은 출력하거나 기록하지 않는다.

찾는 순서: BLOGOPS_ENV_FILE → ~/.config/huninn/huninn.env (매장, docs/blogops.md 7절) → <루트>/.env
프로세스 환경변수(systemd EnvironmentFile 등)에 같은 이름이 있으면 그쪽이 먼저다.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .config import Config


class EnvError(Exception):
    pass


def env_file(config: Config) -> Optional[Path]:
    candidates = [os.environ.get("BLOGOPS_ENV_FILE"), Path.home() / ".config" / "huninn" / "huninn.env",
                  config.root / ".env"]
    for c in candidates:
        if c and Path(c).is_file():
            return Path(c)
    return None


def load(config: Config) -> dict[str, str]:
    values: dict[str, str] = {}
    path = env_file(config)
    if path:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.removeprefix("export ").partition("=")
            values[key.strip()] = value.strip().strip("'\"")
    return values


def get(config: Config, key: str) -> str:
    value = os.environ.get(key) or load(config).get(key)
    if not value:
        where = env_file(config) or "env 파일 없음"
        raise EnvError(f"{key}가 설정되지 않았다 ({where})")
    return value
