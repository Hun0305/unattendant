"""경로와 한도. 값의 근거는 docs/blogops.md 1절."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# site/content/series/ 에 정의된 시리즈
SERIES = ("ops-log", "weekly-report", "pi-llm", "pi-vision")


@dataclass(frozen=True)
class Config:
    root: Path  # 운영 레포 체크아웃 (작업실 또는 매장)
    max_pending_approval: int = 1
    daily_publish_limit: int = 1
    max_tool_calls_per_cycle: int = 60
    max_quality_failures: int = 3
    clock: Optional[Callable[[], datetime]] = None  # 테스트에서 시각을 고정할 때

    @classmethod
    def from_env(cls) -> "Config":
        # BLOGOPS_ROOT가 없으면 이 파일이 들어 있는 체크아웃을 쓴다 (agent/blogops/config.py → 루트)
        root = os.environ.get("BLOGOPS_ROOT") or Path(__file__).resolve().parents[2]
        return cls(root=Path(root))

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
        return self.root / "site"
