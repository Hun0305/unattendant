"""경로와 한도. 값의 근거는 docs/blogops.md 1절."""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# site/content/series/ 에 정의된 시리즈
SERIES = ("ops-log", "weekly-report", "pi-llm", "pi-vision")
# 지금 단계에서 쓸 수 있는 시리즈 (실험 시리즈는 Phase 2부터, state/strategy.md)
CURRENT_SERIES = ("ops-log", "weekly-report")


def find_tool(name: str) -> Optional[str]:
    # systemd 환경에는 ~/.local/bin이 PATH에 없을 수 있다
    found = shutil.which(name)
    if found:
        return found
    local = Path.home() / ".local" / "bin" / name
    return str(local) if local.exists() else None


@dataclass(frozen=True)
class Config:
    root: Path  # 운영 레포 체크아웃 (작업실 또는 매장)
    max_pending_approval: int = 1
    daily_publish_limit: int = 1
    max_tool_calls_per_cycle: int = 60
    max_quality_failures: int = 3
    body_min_chars: int = 1000  # 한국어 본문 (docs/blogops.md 6절)
    body_max_chars: int = 6000
    en_body_min_chars: int = 500  # 영어판 본문
    site_root: Optional[Path] = None  # 사이트 레포 위치. 없으면 <root>/site
    clock: Optional[Callable[[], datetime]] = None  # 테스트에서 시각을 고정할 때

    @classmethod
    def from_env(cls) -> "Config":
        # BLOGOPS_ROOT가 없으면 이 파일이 들어 있는 체크아웃을 쓴다 (agent/blogops/config.py → 루트)
        root = os.environ.get("BLOGOPS_ROOT") or Path(__file__).resolve().parents[2]
        site = os.environ.get("BLOGOPS_SITE_DIR")
        return cls(root=Path(root), site_root=Path(site) if site else None)

    def now(self) -> datetime:
        return self.clock() if self.clock else datetime.now(KST)

    @property
    def state_dir(self) -> Path:
        return self.root / "state"

    @property
    def drafts_dir(self) -> Path:
        return self.state_dir / "drafts"

    @property
    def approvals_dir(self) -> Path:
        return self.state_dir / "approvals"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def site_dir(self) -> Path:
        return self.site_root or self.root / "site"

    @property
    def gitleaks_config(self) -> Path:
        return self.root / "ops" / "gitleaks.toml"
