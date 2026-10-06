"""파일 쓰기와 잠금. 초안·승인 기록과 백로그가 같이 쓴다."""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import Config


def write_atomic(path: Path, text: str) -> None:
    # 쓰는 도중 전원이 나가도 반쯤 쓴 파일이 남지 않게, 같은 폴더에 쓰고 바꿔치기한다
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def write_json(path: Path, data) -> None:
    write_atomic(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


@contextmanager
def state_lock(config: Config) -> Iterator[None]:
    # Huninn 사이클과 사람의 review 명령이 동시에 고쳐도 기록이 섞이지 않게 한다.
    # 같은 프로세스 안에서 겹쳐 잡으면 멈추므로, 잠근 안에서 다시 잠그지 않는다
    config.drafts_dir.mkdir(parents=True, exist_ok=True)
    with open(config.drafts_dir / ".lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
