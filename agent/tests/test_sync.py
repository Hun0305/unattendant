import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from blogops import cycle, sync
from blogops.config import Config
from helpers import HUGO_TOML, git
from test_cycle import CycleBase
from test_notify import FakeTransport


def init_pair(tmp: Path, name: str) -> tuple[Path, Path]:
    """bare origin과 그걸 clone한 체크아웃(매장). 첫 커밋은 다른 clone에서 올린다."""
    origin, seed, live = tmp / f"{name}-origin.git", tmp / f"{name}-seed", tmp / f"{name}-live"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(seed)], check=True, capture_output=True)
    return origin, seed


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        hooks = tmp / "no-hooks"
        hooks.mkdir()
        # 운영 레포 + 사이트 레포. 사이트는 운영 레포 안의 site/ (운영 레포는 .gitignore로 site/를 뺀다)
        self.ops_origin, self.ops_seed = init_pair(tmp, "ops")
        (self.ops_seed / ".gitignore").write_text("site/\nstate/drafts/\nstate/approvals/\n")
        (self.ops_seed / "state").mkdir()
        (self.ops_seed / "state" / "backlog.json").write_text('{"items": []}\n')
        self.site_origin, self.site_seed = init_pair(tmp, "site")
        (self.site_seed / "hugo.toml").write_text(HUGO_TOML)
        (self.site_seed / "layouts").mkdir()
        (self.site_seed / "layouts" / "home.html").write_text("home\n")
        for seed in (self.ops_seed, self.site_seed):
            git(seed, "add", "-A")
            git(seed, "commit", "-q", "-m", "초기")
            git(seed, "push", "-q", "origin", "main")
        self.root = tmp / "live"
        subprocess.run(["git", "clone", "-q", str(self.ops_origin), str(self.root)], check=True, capture_output=True)
        self.site = self.root / "site"
        subprocess.run(["git", "clone", "-q", str(self.site_origin), str(self.site)], check=True, capture_output=True)
        for repo in (self.root, self.site):
            git(repo, "config", "core.hooksPath", str(hooks))
        self.config = Config(root=self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def push_from_seed(self, seed: Path, path: str, text: str):
        (seed / path).parent.mkdir(parents=True, exist_ok=True)
        (seed / path).write_text(text)
        git(seed, "add", "-A")
        git(seed, "commit", "-q", "-m", "사람 커밋")
        git(seed, "pull", "-q", "--rebase", "origin", "main")
        git(seed, "push", "-q", "origin", "main")

    def test_pull_reports_changes_and_rebuilds_site(self):
        self.assertEqual(sync.pull_all(self.config), {"ops": False, "site": False})
        self.push_from_seed(self.site_seed, "layouts/home.html", "새 홈\n")
        self.push_from_seed(self.ops_seed, "docs.md", "문서\n")
        self.assertEqual(sync.pull_all(self.config), {"ops": True, "site": True})
        self.assertEqual((self.site / "public" / "index.html").read_text().strip(), "새 홈")

    def test_pull_fails_when_diverged(self):
        (self.root / "state" / "backlog.json").write_text('{"items": [1]}\n')
        git(self.root, "commit", "-aqm", "로컬 커밋")
        self.push_from_seed(self.ops_seed, "docs.md", "문서\n")
        with self.assertRaises(sync.SyncError) as ctx:
            sync.pull_all(self.config)
        self.assertIn("운영 레포", str(ctx.exception))

    def test_commit_state_nothing_to_commit(self):
        (self.root / "state" / "drafts").mkdir()
        (self.root / "state" / "drafts" / "x.md").write_text("비공개\n")  # gitignore 대상
        self.assertIsNone(sync.commit_state(self.config, "c1"))

    def test_commit_state_pushes_as_huninn(self):
        (self.root / "state" / "backlog.json").write_text('{"items": [{"id": "a"}]}\n')
        (self.root / "docs.md").write_text("사람이 고치던 파일\n")  # state 밖은 건드리지 않는다
        commit = sync.commit_state(self.config, "cycle-1")
        self.assertTrue(commit)
        log = git(self.ops_origin, "log", "-1", "--format=%an|%ae|%s", "main").stdout.strip()
        self.assertEqual(log, "Huninn|huninn@unattendant.dev|chore(agent): 사이클 cycle-1의 state 변경")
        self.assertIn("docs.md", git(self.root, "status", "--porcelain").stdout)

    def test_commit_state_rebases_when_human_pushed_first(self):
        self.push_from_seed(self.ops_seed, "docs.md", "문서\n")
        (self.root / "state" / "backlog.json").write_text('{"items": [{"id": "a"}]}\n')
        commit = sync.commit_state(self.config, "cycle-1")
        self.assertTrue(commit)
        self.assertEqual(git(self.root, "rev-parse", "HEAD").stdout.strip()[:12], commit)
        self.assertEqual(git(self.root, "rev-parse", "HEAD").stdout, git(self.ops_origin, "rev-parse", "main").stdout)
        self.assertTrue((self.root / "docs.md").exists())

    def test_commit_state_conflict_raises(self):
        self.push_from_seed(self.ops_seed, "state/backlog.json", '{"items": ["사람"]}\n')
        (self.root / "state" / "backlog.json").write_text('{"items": ["huninn"]}\n')
        with self.assertRaises(sync.SyncError):
            sync.commit_state(self.config, "cycle-1")
        self.assertNotIn("rebase", git(self.root, "status").stdout)  # rebase를 중단해 둔다


class CycleSyncTest(CycleBase):
    """CycleTest의 가짜 claude를 재사용하되, 시험 실행 옵션을 꺼서 동기화가 돌게 한다."""
    def setUp(self):
        super().setUp()
        os.environ.pop("BLOGOPS_NO_PUBLISH")
        self.calls = []
        self.p1 = mock.patch.object(cycle.sync, "pull_all", side_effect=self.fake_pull)
        self.p2 = mock.patch.object(cycle.sync, "commit_state", side_effect=self.fake_commit)
        self.p1.start(), self.p2.start()
        self.pull_error = self.commit_error = None

    def tearDown(self):
        self.p1.stop(), self.p2.stop()
        super().tearDown()

    def fake_pull(self, config):
        self.calls.append("pull")
        if self.pull_error:
            raise cycle.sync.SyncError(self.pull_error)
        return {"ops": True, "site": False}

    def fake_commit(self, config, cycle_id):
        self.calls.append("commit")
        if self.commit_error:
            raise cycle.sync.SyncError(self.commit_error)
        return "abc123"

    def test_sync_runs_around_claude(self):
        t = FakeTransport()
        record = cycle.run(self.config, transport=t)
        self.assertEqual(self.calls, ["pull", "commit"])
        self.assertEqual(record["state_commit"], "abc123")
        self.assertEqual(record["pulled"], {"ops": True, "site": False})
        self.assertFalse(record["is_error"])
        self.assertEqual(t.calls, [])

    def test_pull_failure_skips_claude_and_alerts(self):
        self.pull_error = "운영 레포를 받지 못했다"
        t = FakeTransport()
        record = cycle.run(self.config, transport=t)
        self.assertTrue(record["is_error"])
        self.assertFalse(self.out.exists())
        self.assertEqual(self.calls, ["pull"])
        self.assertTrue(t.calls[0][2]["content"].startswith("<@222> **긴급**"))
        self.assertIn("운영 레포를 받지 못했다", t.calls[0][2]["content"])

    def test_commit_failure_alerts_but_keeps_claude_result(self):
        self.commit_error = "push하지 못했다"
        t = FakeTransport()
        record = cycle.run(self.config, transport=t)
        self.assertTrue(record["is_error"])
        self.assertEqual(record["total_cost_usd"], 0.4321)
        self.assertIn("push하지 못했다", t.calls[0][2]["content"])

    def test_state_committed_even_if_claude_fails(self):
        os.environ["FAKE_CLAUDE_MODE"] = "fail"
        cycle.run(self.config, transport=FakeTransport())
        self.assertEqual(self.calls, ["pull", "commit"])

    def test_dry_run_skips_sync(self):
        os.environ["BLOGOPS_NO_PUBLISH"] = "1"
        cycle.run(self.config, transport=FakeTransport())
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
