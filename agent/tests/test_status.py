import contextlib
import io
import json
import os
import stat
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from blogops import status
from blogops.config import KST

MEMINFO = """MemTotal:        3977000 kB
MemFree:          500000 kB
MemAvailable:    2297000 kB
Buffers:          100000 kB
"""
NOW = datetime(2026, 10, 14, 21, 5, tzinfo=KST)
# site/README.md의 status.json 형식 중 이 모듈이 쓰는 필드. unattended_days·cost_today_krw는 쓰지 않는다
OURS = {"updated", "cpu_temp_c", "mem_used_gb", "mem_total_gb", "uptime_s", "disk_free_pct"}


def sources(tmp, temp="52123\n", meminfo=MEMINFO, uptime="352800.55 1200000.10\n"):
    d = Path(tmp)
    files = {"thermal": temp, "meminfo": meminfo, "uptime": uptime}
    out = {}
    for name, text in files.items():
        out[name] = d / name
        if text is not None:
            out[name].write_text(text)
    return {**out, "disk": d, "cycles": d / "cycles.jsonl"}  # 사이클 기록은 없는 것이 기본


class CollectTest(unittest.TestCase):
    def test_정상이면_공개_필드_여섯_개만(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = status.collect(NOW, **sources(tmp))
        self.assertEqual(set(s), OURS)
        self.assertEqual(s["updated"], "2026-10-14T21:05:00+09:00")
        self.assertEqual(s["cpu_temp_c"], 52.1)
        self.assertEqual(s["uptime_s"], 352800)
        self.assertTrue(0 < s["disk_free_pct"] <= 100)

    def test_메모리는_전체에서_사용_가능을_뺀다(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = status.collect(NOW, **sources(tmp))
        # (3977000 - 2297000) kB = 1.6 GB 사용, 전체 3.8 GB
        self.assertEqual((s["mem_used_gb"], s["mem_total_gb"]), (1.6, 3.8))

    def test_읽지_못한_값은_필드를_뺀다(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = status.collect(NOW, **sources(tmp, temp=None, meminfo=None, uptime=None))
        self.assertEqual(set(s), {"updated", "disk_free_pct"})

    def test_엉뚱한_내용이면_그_필드만_뺀다(self):
        bad_mem = "MemTotal: 3977000 kB\n"  # MemAvailable이 없다
        with tempfile.TemporaryDirectory() as tmp:
            s = status.collect(NOW, **sources(tmp, temp="abc", meminfo=bad_mem, uptime=""))
        self.assertEqual(set(s), {"updated", "disk_free_pct"})

    def test_디스크를_못_읽어도_나머지는_간다(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = sources(tmp)
            src["disk"] = Path(tmp) / "없는 폴더"
            s = status.collect(NOW, **src)
        self.assertNotIn("disk_free_pct", s)
        self.assertIn("cpu_temp_c", s)

    def test_무인_운영일과_비용은_아직_안_쓴다(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = status.collect(NOW, **sources(tmp))
        self.assertNotIn("unattended_days", s)
        self.assertNotIn("cost_today_krw", s)


class WriteTest(unittest.TestCase):
    def test_누구나_읽을_수_있는_json_하나만_남는다(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run" / "huninn" / "status.json"  # 폴더가 없어도 만든다
            status.write(path, {"updated": "x", "cpu_temp_c": 40.4})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"updated": "x", "cpu_temp_c": 40.4})
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)
            self.assertEqual(os.listdir(path.parent), ["status.json"])  # 임시 파일이 남지 않는다

    def test_덮어쓴다(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            status.write(path, {"updated": "1"})
            status.write(path, {"updated": "2"})
            self.assertEqual(json.loads(path.read_text())["updated"], "2")
            self.assertEqual(os.listdir(tmp), ["status.json"])


class LastCycleTest(unittest.TestCase):
    def write(self, tmp, *records):
        path = Path(tmp) / "cycles.jsonl"
        path.write_text("".join(json.dumps(r) + "\n" for r in records) + "깨진 줄\n")
        return path

    def test_기록이_없으면_필드를_뺀다(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(status.last_cycle(Path(tmp) / "cycles.jsonl"))
            self.assertNotIn("cycle", status.collect(NOW, **sources(tmp)))

    def test_성공이면_시각과_ok만(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, {"ts": "2026-10-16T14:20:00+09:00", "is_error": False, "result": "비공개"})
            self.assertEqual(status.last_cycle(path), {"at": "2026-10-16T14:20:00+09:00", "ok": True})

    def test_연속_실패는_횟수와_첫_실패_시각(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp,
                              {"ts": "2026-10-16T14:20:00+09:00", "is_error": False},
                              {"ts": "2026-10-17T14:00:00+09:00", "is_error": True, "result": "OAuth token revoked"},
                              {"ts": "2026-10-17T20:00:00+09:00", "is_error": False, "dry_run": True},  # 시험 실행은 세지 않는다
                              {"ts": "2026-10-18T14:00:00+09:00", "is_error": True, "stderr": "내부 경로"})
            cycle = status.last_cycle(path)
            self.assertEqual(cycle, {"at": "2026-10-18T14:00:00+09:00", "ok": False, "fail_streak": 2,
                                     "failing_since": "2026-10-17T14:00:00+09:00"})
            s = status.collect(NOW, **{**sources(tmp), "cycles": path})
            self.assertEqual(s["cycle"], cycle)
            self.assertNotIn("revoked", json.dumps(s))  # 오류 문장은 공개하지 않는다


class MainTest(unittest.TestCase):
    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = status.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_out으로_쓴다(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            code, out, err = self.run_main("--out", str(path))
            self.assertEqual((code, out, err), (0, "", ""))  # 성공하면 조용하다 (5분마다 돈다)
            self.assertTrue(set(json.loads(path.read_text())) <= OURS | {"cycle"})

    def test_환경변수_위치를_쓴다(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "env.json"
            with mock.patch.dict(os.environ, {"HUNINN_STATUS_PATH": str(path)}):
                code, _, _ = self.run_main()
            self.assertEqual(code, 0)
            self.assertTrue(path.exists())

    def test_print는_쓰지_않고_보여_준다(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "status.json"
            code, out, _ = self.run_main("--print", "--out", str(path))
            self.assertEqual(code, 0)
            self.assertIn("updated", json.loads(out))
            self.assertFalse(path.exists())

    def test_쓰지_못하면_1과_이유(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "파일"
            blocker.write_text("x")
            code, out, err = self.run_main("--out", str(blocker / "status.json"))  # 부모가 폴더가 아니다
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("status.json을 쓰지 못했다", err)


if __name__ == "__main__":
    unittest.main()
