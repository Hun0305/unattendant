import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from blogops import backlog, decisions, ondemand, preview
from blogops.store import StoreError
from helpers import good_body, make_env

FAKE_ENV = "DISCORD_BOT_TOKEN=test-bot-token\nDISCORD_CH_APPROVAL=102\nDISCORD_OWNER_ID=222\n"


class FakeTransport:
    def __init__(self, status=200, body=None):
        self.calls = []
        self.result = (status, body or {})

    def __call__(self, url, headers, payload):
        self.calls.append((url, headers, payload))
        return self.result


def logged(config):
    lines = [line for f in sorted(config.logs_dir.glob("*.jsonl")) for line in f.read_text(encoding="utf-8").splitlines()]
    return [r for r in map(json.loads, lines) if "event" in r]  # make_env가 만든 x.jsonl({})은 거른다


class DecisionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config, self.store = make_env(self.tmp.name, real_clock=True)
        env_file = Path(self.tmp.name) / "huninn.env"
        env_file.write_text(FAKE_ENV, encoding="utf-8")
        self.patch = mock.patch.dict(os.environ, {"BLOGOPS_ENV_FILE": str(env_file)})
        self.patch.start()
        # 기본은 즉시 실행 유닛이 없는 환경. 실제 systemctl을 부르지 않는다
        self.watch = mock.patch.object(ondemand, "watcher_active", return_value=False)
        self.watcher = self.watch.start()

    def tearDown(self):
        self.watch.stop()
        self.patch.stop()
        self.tmp.cleanup()

    def awaiting(self, backlog_id="naming"):
        draft_id = self.store.create_draft(slug="naming", series="ops-log", backlog_id=backlog_id,
                                           ko={"title": "이름 짓기", "description": "요약", "tags": ["meta"], "body": good_body()})
        self.store.record_quality(draft_id, True, [])
        self.store.record_approval_request(draft_id)
        return draft_id

    def decisions_in_log(self):
        return [r for r in logged(self.config) if r["event"] == "approval_decision"]

    def test_approve_records_via_and_logs(self):
        draft_id = self.awaiting()
        h = self.store.content_hash(draft_id)
        decision = decisions.approve(self.config, self.store, draft_id, expect_hash=h[:12], via="discord")
        self.assertEqual((decision.kind, decision.hash, decision.via), ("approved", h, "discord"))
        self.assertEqual(self.store.status(draft_id), "approved")
        self.assertEqual(self.store.decisions(draft_id)[-1]["via"], "discord")
        (entry,) = self.decisions_in_log()
        self.assertEqual((entry["actor"], entry["decision"], entry["via"]), ("operator", "approved", "discord"))

    def test_reject_keeps_reason_for_huninn(self):
        draft_id = self.awaiting()
        decision = decisions.reject(self.config, self.store, draft_id, "  출처가 없다  ", via="discord")
        self.assertEqual((decision.kind, decision.reason), ("rejected", "출처가 없다"))
        self.assertEqual(self.store.status(draft_id), "rejected")  # 보류가 아니다: Huninn이 다음 사이클에 고친다
        self.assertEqual(backlog.items(self.config, "idea")[0]["id"], "naming")  # 글감도 그대로
        self.assertFalse(self.decisions_in_log()[0]["dropped"])

    def test_drop_holds_draft_and_blocks_backlog_item(self):
        draft_id = self.awaiting()
        decision = decisions.reject(self.config, self.store, draft_id, "이 주제는 그만", drop=True, via="discord")
        self.assertEqual((decision.kind, decision.warnings), ("dropped", ()))
        self.assertEqual(self.store.status(draft_id), "held")
        self.assertIn("이 주제는 그만", self.store.summary(draft_id)["held"]["reason"])
        item = backlog.items(self.config, "blocked")[0]
        self.assertEqual(item["id"], "naming")
        self.assertIn("이 주제는 그만", item["notes"])
        self.assertTrue(self.decisions_in_log()[0]["dropped"])
        self.assertEqual(self.store.decisions(draft_id)[-1]["decision"], "rejected")  # 반려 기록도 남는다

    def test_drop_warns_when_backlog_cannot_change(self):
        draft_id = self.awaiting(backlog_id=None)
        decision = decisions.reject(self.config, self.store, draft_id, "그만", drop=True)
        self.assertEqual(self.store.status(draft_id), "held")
        self.assertIn("글감 ID가 없어", decision.warnings[0])
        # 보류된 초안과 글감이 없는 경우는 따로 새 초안으로 확인한다
        other = self.store.create_draft(slug="other", series="ops-log", backlog_id="nope",
                                        ko={"title": "다른 글", "description": "요약", "tags": [], "body": good_body()})
        self.store.record_quality(other, True, [])
        self.store.record_approval_request(other)
        decision = decisions.reject(self.config, self.store, other, "그만", drop=True)
        self.assertIn("blocked로 바꾸지 못했다", decision.warnings[0])

    def test_stale_hash_changes_nothing(self):
        draft_id = self.awaiting()
        for call in (lambda: decisions.approve(self.config, self.store, draft_id, expect_hash="0" * 12),
                     lambda: decisions.reject(self.config, self.store, draft_id, "x", drop=True, expect_hash="0" * 12)):
            with self.assertRaises(StoreError):
                call()
        self.assertEqual(self.store.status(draft_id), "awaiting_approval")
        self.assertEqual(self.decisions_in_log(), [])
        self.assertEqual(backlog.items(self.config, "blocked"), [])

    def test_preflight(self):
        draft_id = self.awaiting()
        h = self.store.content_hash(draft_id)[:12]
        self.assertEqual(decisions.preflight(self.store, draft_id, h)["title"], "이름 짓기")
        with self.assertRaises(StoreError) as cm:
            decisions.preflight(self.store, draft_id, "0" * 12)
        self.assertIn("초안이 바뀌었다", str(cm.exception))
        decisions.approve(self.config, self.store, draft_id)
        with self.assertRaises(StoreError) as cm:
            decisions.preflight(self.store, draft_id, h)
        self.assertIn("승인됨", str(cm.exception))
        with self.assertRaises(StoreError):
            decisions.preflight(self.store, "20990101-none", h)

    def test_result_text(self):
        draft_id = self.awaiting()
        approved = decisions.Decision(draft_id, "approved", "a" * 64, "2026-10-13T21:03:11+09:00", "discord")
        text = decisions.result_text("이름 짓기", approved)
        self.assertIn("승인함", text)
        self.assertIn("이름 짓기", text)
        self.assertIn("2026-10-13 21:03 (디스코드)", text)
        self.assertIn("다음 사이클", text)
        self.assertNotIn("사유", text)
        self.assertNotIn("임시 실행", text)  # 승인은 사이클을 돌리지 않는다. 다음 14:00에 발행된다
        dropped = decisions.Decision(draft_id, "dropped", "a" * 64, "2026-10-13T21:03:11+09:00", "cli", reason="그만")
        text = decisions.result_text("이름 짓기", dropped)
        self.assertIn("접음", text)
        self.assertIn("사유: 그만", text)
        self.assertIn("(Pi 명령)", text)
        self.assertIn("다음 14:00 사이클에서 Huninn이 다른 글감으로 새 초안을 쓴다", text)

    def test_next_step_wording(self):
        def decision(kind, cycle):
            return decisions.Decision("20261013-a", kind, "a" * 64, "2026-10-13T21:03:11+09:00", "cli", cycle=cycle)

        now = {"status": "requested", "count": 2, "limit": 5}
        self.assertIn("사이클을 바로 돌린다", decisions.next_step(decision("rejected", now)))
        self.assertIn("임시 실행 2/5회", decisions.next_step(decision("rejected", now)))
        self.assertIn("다시 승인을 요청한다", decisions.next_step(decision("rejected", now)))
        self.assertIn("다른 글감으로 새 초안을 쓴다", decisions.next_step(decision("dropped", now)))
        self.assertIn("글감은 blocked로 바꿨다", decisions.next_step(decision("dropped", now)))
        capped = {"status": "capped", "count": 5, "limit": 5}
        self.assertIn("5회를 다 썼다. 다음 14:00 사이클에서", decisions.next_step(decision("rejected", capped)))
        for cycle in (None, {"status": "unwatched", "count": 0, "limit": 5}):
            text = decisions.next_step(decision("rejected", cycle))
            self.assertIn("다음 14:00 사이클에서", text)
            self.assertNotIn("바로", text)
        self.assertIn("14:00", decisions.next_step(decision("approved", now)))
        self.assertNotIn("임시 실행", decisions.next_step(decision("approved", now)))

    def test_reject_and_drop_ask_for_an_immediate_cycle(self):
        self.watcher.return_value = True
        draft_id = self.awaiting()
        decision = decisions.reject(self.config, self.store, draft_id, "출처가 없다", via="discord")
        self.assertEqual(decision.cycle, {"status": "requested", "count": 1, "limit": 5})
        self.assertTrue(self.config.cycle_request_path.exists())
        self.assertIn("사이클을 바로 돌린다", decisions.result_text("이름 짓기", decision))
        self.config.cycle_request_path.unlink()  # 서비스가 시작하며 지운다
        other = self.store.create_draft(slug="other", series="ops-log", backlog_id="nope",
                                        ko={"title": "다른 글", "description": "요약", "tags": [], "body": good_body()})
        self.store.record_quality(other, True, [])
        self.store.record_approval_request(other)
        dropped = decisions.reject(self.config, self.store, other, "그만", drop=True)
        self.assertEqual(dropped.cycle["count"], 2)
        self.assertTrue(self.config.cycle_request_path.exists())

    def test_the_request_comes_after_the_state_is_final(self):
        # 사이클이 바로 시작해도 접은 글감을 다시 고르지 않으려면, 요청 시점에 글감이 이미 blocked여야 한다
        self.watcher.return_value = True
        seen = {}
        real = ondemand.request

        def spy(config, kind, draft_id):
            seen["status"] = self.store.status(draft_id)
            seen["backlog"] = [i["status"] for i in backlog.items(config) if i["id"] == "naming"]
            return real(config, kind, draft_id)

        draft_id = self.awaiting()
        with mock.patch.object(ondemand, "request", side_effect=spy):
            decisions.reject(self.config, self.store, draft_id, "이 주제는 그만", drop=True)
        self.assertEqual(seen, {"status": "held", "backlog": ["blocked"]})

    def test_approval_never_asks_for_a_cycle(self):
        self.watcher.return_value = True
        decision = decisions.approve(self.config, self.store, self.awaiting())
        self.assertIsNone(decision.cycle)
        self.assertFalse(self.config.cycle_request_path.exists())
        self.assertEqual(self.decisions_in_log()[0]["decision"], "approved")
        self.watcher.assert_not_called()

    def test_stale_decision_does_not_ask_for_a_cycle(self):
        self.watcher.return_value = True
        draft_id = self.awaiting()
        with self.assertRaises(StoreError):
            decisions.reject(self.config, self.store, draft_id, "x", expect_hash="0" * 12)
        self.assertFalse(self.config.cycle_request_path.exists())

    def test_cycle_request_failure_is_a_warning(self):
        draft_id = self.awaiting()
        with mock.patch.object(ondemand, "request", side_effect=OSError("디스크가 가득 찼다")):
            decision = decisions.reject(self.config, self.store, draft_id, "그만")
        self.assertEqual(self.store.status(draft_id), "rejected")  # 결정은 기록됐다
        self.assertIsNone(decision.cycle)
        self.assertIn("바로 돌리도록 요청하지 못했다", decision.warnings[0])

    def test_finish_closes_discord_message_and_removes_preview(self):
        draft_id = self.awaiting()
        h = self.store.content_hash(draft_id)
        self.store.record_approval_message(draft_id, h, 102, 999)
        token = preview.ensure(self.config, self.store, draft_id)["token"]
        decision = decisions.approve(self.config, self.store, draft_id, via="discord")
        transport = FakeTransport()
        self.assertEqual(decisions.finish(self.config, self.store, decision, transport=transport), [])
        ((url, headers, payload),) = transport.calls
        self.assertTrue(url.endswith("/channels/102/messages/999"))
        self.assertEqual(headers["Authorization"], "Bot test-bot-token")
        self.assertEqual(payload["components"], [])  # 버튼과 링크를 걷어낸다
        self.assertEqual(payload["allowed_mentions"], {"parse": []})
        self.assertIn("승인함", payload["content"])
        self.assertIn("이름 짓기", payload["content"])
        self.assertFalse((self.config.previews_dir / token).exists())
        self.assertEqual([r["event"] for r in logged(self.config)].count("close_approval_message"), 1)

    def test_finish_without_discord_message_calls_nothing(self):
        draft_id = self.awaiting()
        decision = decisions.approve(self.config, self.store, draft_id)
        transport = FakeTransport()
        self.assertEqual(decisions.finish(self.config, self.store, decision, transport=transport), [])
        self.assertEqual(transport.calls, [])

    def test_finish_failures_are_warnings_not_errors(self):
        draft_id = self.awaiting()
        self.store.record_approval_message(draft_id, self.store.content_hash(draft_id), 102, 999)
        decision = decisions.approve(self.config, self.store, draft_id)
        warnings = decisions.finish(self.config, self.store, decision, transport=FakeTransport(404, {"message": "Unknown Message"}))
        self.assertEqual(len(warnings), 1)
        self.assertIn("404", warnings[0])
        self.assertNotIn("test-bot-token", warnings[0])
        self.assertEqual(self.store.status(draft_id), "approved")  # 결정은 이미 기록됐다
        with mock.patch.dict(os.environ, {"BLOGOPS_ENV_FILE": str(Path(self.tmp.name) / "none.env")}):
            warnings = decisions.finish(self.config, self.store, decision)  # 매장 파일로 넘어가지 않는다
        self.assertEqual(len(warnings), 1)
        self.assertIn("DISCORD_BOT_TOKEN", warnings[0])

    def test_finish_passes_on_drop_warnings(self):
        draft_id = self.awaiting(backlog_id=None)
        decision = decisions.reject(self.config, self.store, draft_id, "그만", drop=True)
        warnings = decisions.finish(self.config, self.store, decision, transport=FakeTransport())
        self.assertEqual(warnings, list(decision.warnings))


if __name__ == "__main__":
    unittest.main()
