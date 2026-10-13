#!/usr/bin/env python3
"""experiments/models.toml의 GGUF 파일을 받고 sha256을 대조한다 (docs/experiments.md 3.1절).

    python3 -I experiments/runner/fetch_models.py                 # 모든 모델
    python3 -I experiments/runner/fetch_models.py --group round1  # 그룹 하나
    python3 -I experiments/runner/fetch_models.py --only llama-3.2-1b,gemma-3-1b
    python3 -I experiments/runner/fetch_models.py --check         # 받지 않고 있는 파일만 대조

- 받는 곳은 레포 밖 ~/models/gguf/ (환경 변수 EXP_MODELS_DIR로 바꿀 수 있다)
- models.toml에 고정한 저장소 커밋(revision)에서 받는다. 같은 이름의 파일이 나중에 바뀌어도 그 판을 받는다
- 받는 중에는 <파일>.part에 쓰고, 끊기면 이어 받는다. 해시가 다르면 .part를 지우고 실패로 끝낸다
- 대조가 끝난 파일 옆에 <파일>.sha256을 남겨, 다음 실행은 크기와 이 기록만 보고 건너뛴다
- 받은 파일은 남이 만든 데이터라 다른 모듈을 import하지 않는다. -I로 실행한다
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

MODELS_TOML = Path(__file__).resolve().parents[1] / "models.toml"
CHUNK = 1 << 20
REPORT_EVERY = 200 << 20


def models_dir() -> Path:
    return Path(os.environ.get("EXP_MODELS_DIR", "~/models/gguf")).expanduser()


def selected_files(models: list[dict], only: set[str], group: str | None) -> list[tuple[str, dict]]:
    out = []
    for model in models:
        if only and model["id"] not in only:
            continue
        if group and group not in model.get("groups", []):
            continue
        out.extend((model["id"], f) for f in model.get("file", []))
    return out


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def verified(path: Path, entry: dict) -> bool:
    """크기가 맞고, 대조 기록이 기대 해시와 같은가 (파일을 다시 읽지 않는다)."""
    record = path.with_name(path.name + ".sha256")
    return (path.exists() and path.stat().st_size == entry["size"]
            and record.exists() and record.read_text().split()[0] == entry["sha256"])


def download(entry: dict, target: Path) -> None:
    url = f"https://huggingface.co/{entry['repo']}/resolve/{entry['revision']}/{entry['file']}"
    part = target.with_name(target.name + ".part")
    h = hashlib.sha256()
    have = part.stat().st_size if part.exists() else 0
    if have > entry["size"]:
        part.unlink()
        have = 0
    if have:
        with part.open("rb") as f:  # 이어 받으려면 받은 부분부터 해시에 넣는다
            while chunk := f.read(CHUNK):
                h.update(chunk)
    request = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    with urllib.request.urlopen(request, timeout=60) as response:
        if have and response.status != 206:  # 이어 받기를 안 받아 주면 처음부터
            have = 0
            h = hashlib.sha256()
        mode = "ab" if have else "wb"
        done, next_report, started = have, have + REPORT_EVERY, time.monotonic()
        with part.open(mode) as f:
            while chunk := response.read(CHUNK):
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if done >= next_report:
                    rate = (done - have) / max(time.monotonic() - started, 1e-6) / 1e6
                    print(f"    {done / 1e6:,.0f} / {entry['size'] / 1e6:,.0f} MB ({rate:.1f} MB/s)", flush=True)
                    next_report += REPORT_EVERY
    if done != entry["size"]:
        raise RuntimeError(f"크기가 다르다: 받은 {done}, 기대 {entry['size']}")
    digest = h.hexdigest()
    if digest != entry["sha256"]:
        part.unlink()
        raise RuntimeError(f"sha256이 다르다: 받은 {digest}, 기대 {entry['sha256']}")
    part.rename(target)
    target.with_name(target.name + ".sha256").write_text(f"{digest}  {target.name}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", default="", help="모델 id 목록(쉼표)")
    parser.add_argument("--group", help="models.toml의 groups 값 (예: round1)")
    parser.add_argument("--check", action="store_true", help="받지 않고, 있는 파일의 sha256을 다시 계산해 대조한다")
    args = parser.parse_args()

    with MODELS_TOML.open("rb") as f:
        models = tomllib.load(f).get("model", [])
    files = selected_files(models, {s for s in args.only.split(",") if s}, args.group)
    if not files:
        print("고른 모델이 없다", file=sys.stderr)
        return 2
    root = models_dir()
    root.mkdir(parents=True, exist_ok=True)

    failed = 0
    for model_id, entry in files:
        target = root / entry["file"]
        label = f"{model_id} {entry['quant']} ({entry['size'] / 1e6:,.0f} MB)"
        try:
            if args.check:
                if not target.exists():
                    print(f"없음  {label}")
                    failed += 1
                    continue
                ok = sha256_of(target) == entry["sha256"]
                print(f"{'맞음' if ok else '다름'}  {label}")
                failed += 0 if ok else 1
                continue
            if verified(target, entry):
                print(f"있음  {label}")
                continue
            if target.exists():  # 대조 기록이 없거나 크기가 다르면 다시 계산해 본다
                if target.stat().st_size == entry["size"] and sha256_of(target) == entry["sha256"]:
                    target.with_name(target.name + ".sha256").write_text(f"{entry['sha256']}  {target.name}\n")
                    print(f"있음  {label} (다시 대조함)")
                    continue
                target.unlink()
            print(f"받기  {label}", flush=True)
            download(entry, target)
            print(f"완료  {label}", flush=True)
        except (OSError, urllib.error.URLError, RuntimeError) as e:
            print(f"실패  {label}: {e}", file=sys.stderr, flush=True)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
