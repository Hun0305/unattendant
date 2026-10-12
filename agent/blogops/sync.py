"""매장 동기화 (docs/blogops.md 7절). cycle.py가 사이클 앞뒤로 부른다.

- pull_all: 사이클 시작에 두 레포를 git pull --ff-only로 받고, 사이트가 바뀌었으면 다시 빌드한다
- commit_state: 사이클 끝에 Huninn이 바꾼 state/를 작성자 Huninn으로 운영 레포에 커밋·push한다.
  push가 겹치면 rebase 후 한 번 더, 그래도 안 되면 SyncError (호출한 쪽이 #긴급으로 알린다)
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .config import Config
from .publish import HUNINN_EMAIL, HUNINN_NAME, _real_build

STATE_PATHS = ("state",)  # 비공개 하위 폴더(drafts, approvals)는 .gitignore가 빼 준다


class SyncError(Exception):
    pass


def _git(repo: Path, *args: str, author: bool = False, stdin: str | None = None) -> subprocess.CompletedProcess:
    cmd = ["git", "-C", str(repo)]
    if author:
        cmd += ["-c", f"user.name={HUNINN_NAME}", "-c", f"user.email={HUNINN_EMAIL}"]
    return subprocess.run(cmd + list(args), input=stdin, capture_output=True, text=True, timeout=180)


def _out(result: subprocess.CompletedProcess) -> str:
    return (result.stderr or result.stdout).strip()[-300:]


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _pull(repo: Path, label: str) -> bool:
    """받아서 HEAD가 바뀌었는지 돌려준다."""
    before = _head(repo)
    result = _git(repo, "pull", "-q", "--ff-only")
    if result.returncode != 0:
        raise SyncError(f"{label} 레포를 받지 못했다 (git pull --ff-only): {_out(result)}")
    return _head(repo) != before


def pull_all(config: Config) -> dict:
    changed = {"ops": _pull(config.root, "운영"), "site": _pull(config.site_dir, "사이트")}
    if changed["site"]:
        result = _real_build(config.site_dir)
        if result.returncode != 0:
            raise SyncError(f"사이트 빌드가 실패했다: {(result.stderr or result.stdout).strip()[-300:]}")
    return changed


def commit_state(config: Config, cycle_id: str) -> str | None:
    """바뀐 state/가 없으면 None, 있으면 커밋 해시. push까지 못 하면 SyncError."""
    root = config.root
    if not _git(root, "status", "--porcelain", "--", *STATE_PATHS).stdout.strip():
        return None
    message = (f"chore(agent): 사이클 {cycle_id}의 state 변경\n\n"
               f"- state/ 아래 Huninn이 바꾼 파일 (백로그 등)\n\n"
               f"왜: 다음 사이클의 git pull --ff-only가 막히지 않게 매장 상태를 운영 레포에 맞춘다\n"
               f"확인: 사이클 {cycle_id} 종료 시 자동 커밋\n")
    for args, kw in ((("add", "--", *STATE_PATHS), {}),
                     (("commit", "-q", "-F", "-", "--", *STATE_PATHS), {"author": True, "stdin": message})):
        result = _git(root, *args, **kw)
        if result.returncode != 0:
            raise SyncError(f"state를 커밋하지 못했다 (git {args[0]}): {_out(result)}")
    commit = _head(root)[:12]
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if _git(root, "push", "-q", "origin", branch).returncode == 0:
        return commit
    # 사람이 먼저 push했으면 받아서 내 커밋을 위에 얹고 한 번 더
    if _git(root, "pull", "-q", "--rebase", "origin", branch, author=True).returncode != 0:
        _git(root, "rebase", "--abort")
        raise SyncError(f"state 커밋 {commit}을 push하지 못했다 (rebase 충돌)")
    result = _git(root, "push", "-q", "origin", branch)
    if result.returncode != 0:
        raise SyncError(f"state 커밋 {commit}을 push하지 못했다: {_out(result)}")
    return _head(root)[:12]
