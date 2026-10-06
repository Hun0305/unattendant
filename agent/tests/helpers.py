"""테스트용 가짜 운영 레포와 사이트."""
import json
import random
import shutil
import string
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from blogops.config import KST, Config
from blogops.store import Store

REAL_ROOT = Path(__file__).resolve().parents[2]  # 이 테스트가 들어 있는 체크아웃

HUGO_TOML = """baseURL = "https://example.org/"
defaultContentLanguage = "ko"
defaultContentLanguageInSubdir = false
disableKinds = ["taxonomy", "term", "rss", "sitemap", "robotstxt", "404"]

[languages.ko]
  weight = 1
[languages.en]
  weight = 2
"""

EXISTING_POST = """---
title: "AI가 혼자 운영하는 블로그를 만들기로 했다"
date: 2026-10-06T20:34:00+09:00
author: human
series: ["ops-log"]
tags: ["meta"]
---

소개글.
"""


class Clock:
    def __init__(self):
        self.t = datetime(2026, 10, 8, 14, 0, tzinfo=KST)

    def __call__(self):
        self.t += timedelta(seconds=1)
        return self.t


BACKLOG = {"updated": "2026-10-07", "items": [
    {"id": "naming", "title": "이름 짓기", "series": "ops-log", "status": "idea", "sources": [], "notes": "",
     "added": "2026-10-07", "added_by": "operator"}]}


def make_env(tmp, real_clock: bool = False) -> tuple[Config, Store]:
    root, site = Path(tmp) / "ops", Path(tmp) / "site"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "pre-commit.md").write_text("# 비밀키 스캐너\n\n본문 " + "가" * 30000, encoding="utf-8")
    (root / "ops").mkdir()
    (root / "ops" / "README.md").write_text("# ops\n", encoding="utf-8")
    shutil.copy(REAL_ROOT / "ops" / "gitleaks.toml", root / "ops" / "gitleaks.toml")
    (root / ".env").write_text("SECRET=1\n")
    (root / "logs").mkdir()
    (root / "logs" / "x.jsonl").write_text("{}\n")
    (root / "CLAUDE.md").write_text("# 사람용 지시\n", encoding="utf-8")
    (root / "state").mkdir()
    (root / "state" / "backlog.json").write_text(json.dumps(BACKLOG, ensure_ascii=False), encoding="utf-8")

    (site / "content" / "posts" / "starting-unattendant").mkdir(parents=True)
    (site / "content" / "posts" / "starting-unattendant" / "index.ko.md").write_text(EXISTING_POST, encoding="utf-8")
    (site / "README.md").write_text("# unattendant.dev\n", encoding="utf-8")
    (site / "hugo.toml").write_text(HUGO_TOML)
    (site / "layouts").mkdir()
    (site / "layouts" / "page.html").write_text("<h1>{{ .Title }}</h1>{{ .Content }}\n")
    (site / "layouts" / "home.html").write_text("home\n")
    (site / "layouts" / "section.html").write_text("section\n")

    # Hugo는 실제 현재 시각보다 미래인 글을 빌드하지 않으므로, 빌드까지 하는 테스트는 실제 시계를 쓴다
    config = Config(root=root, site_root=site, clock=None if real_clock else Clock())
    return config, Store(config)


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=Hun0305", "-c", "user.email=t@example.invalid",
                           *args], capture_output=True, text=True, check=check)


def make_publish_env(tmp) -> tuple[Config, Store, Path]:
    """사이트를 git 레포로 만들고, GitHub 대신 로컬 bare 저장소를 origin으로 둔다."""
    config, store = make_env(tmp, real_clock=True)
    site, origin, hooks = config.site_dir, Path(tmp) / "origin.git", Path(tmp) / "no-hooks"
    hooks.mkdir()
    (site / ".gitignore").write_text("public/\nresources/\n.hugo_build.lock\n")
    subprocess.run(["git", "init", "-q", "-b", "main", str(site)], check=True)
    git(site, "config", "core.hooksPath", str(hooks))
    git(site, "add", "-A")
    git(site, "commit", "-q", "-m", "초기 사이트")
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    git(site, "remote", "add", "origin", str(origin))
    git(site, "push", "-q", "origin", "main")
    subprocess.run([shutil.which("hugo") or str(Path.home() / ".local/bin/hugo"), "--source", str(site), "--quiet"],
                   check=True, capture_output=True)
    return config, store, origin


def fake_anthropic_key(seed: int = 1) -> str:
    # 실제 키 모양의 가짜 값. 이 파일이 비밀키 검사에 걸리지 않도록 실행할 때 조립한다
    r = random.Random(seed)
    tail = "".join(r.choice(string.ascii_letters + string.digits + "-_") for _ in range(93))
    return "sk-" + "ant-" + "api03-" + tail + "AA"


def good_body(extra: str = "") -> str:
    para = "이 블로그는 라즈베리파이 한 대 위에서 돈다. 글감 선정부터 발행까지 Huninn이 맡는다. "
    return para * 25 + extra
