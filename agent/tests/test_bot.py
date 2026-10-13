import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

try:
    import discord
    from blogops import bot as bot_module
except ImportError:  # discord.py는 선택 의존성이다 (pip install -e ".[bot]")
    discord = None

from blogops import backlog, buttons
from helpers import good_body, make_env

FAKE_ENV = "DISCORD_BOT_TOKEN=test-bot-token\nDISCORD_CH_APPROVAL=102\nDISCORD_OWNER_ID=222\n"
OWNER, STRANGER = 222, 333


class FakeResponse:
    def __init__(self):
        self.done = False
        self.sent, self.edited, self.modal = [], [], None

    def is_done(self):
        return self.done

    async def send_message(self, content=None, *, view=None, ephemeral=False):
        self.done = True
        self.sent.append({"content": content, "view": view, "ephemeral": ephemeral})

    async def edit_message(self, *, content=None, view=None):
        self.done = True
        self.edited.append({"content": content, "view": view})

    async def send_modal(self, modal):
        self.done = True
        self.modal = modal


class FakeFollowup:
    def __init__(self):
        self.sent = []

    async def send(self, content, *, ephemeral=False):
        self.sent.append({"content": content, "ephemeral": ephemeral})


def interaction(user_id):
    return SimpleNamespace(user=SimpleNamespace(id=user_id), response=FakeResponse(), followup=FakeFollowup())


@unittest.skipIf(discord is None, "discord.py가 없다")
class BotTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config, self.store = make_env(self.tmp.name, real_clock=True)
        env_file = Path(self.tmp.name) / "huninn.env"
        env_file.write_text(FAKE_ENV, encoding="utf-8")
        self.patch = mock.patch.dict(os.environ, {"BLOGOPS_ENV_FILE": str(env_file)})
        self.patch.start()
        self.patch_http = mock.patch("blogops.notify.patch_json", return_value=(200, {}))
        self.http = self.patch_http.start()
        # 기본은 즉시 실행 유닛이 없는 환경. 실제 systemctl을 부르지 않는다
        self.patch_watch = mock.patch("blogops.ondemand.watcher_active", return_value=False)
        self.watcher = self.patch_watch.start()
        self.bot = bot_module.HuninnBot(self.config)
        self.draft_id = self.store.create_draft(
            slug="naming", series="ops-log", backlog_id="naming",
            ko={"title": "이름 짓기", "description": "요약", "tags": ["meta"], "body": good_body()})
        self.store.record_quality(self.draft_id, True, [])
        self.store.record_approval_request(self.draft_id)
        self.hash = self.store.content_hash(self.draft_id)
        self.h12 = self.hash[:12]
        self.store.record_approval_message(self.draft_id, self.hash, 102, 999)

    async def asyncTearDown(self):
        self.patch_watch.stop()
        self.patch_http.stop()
        self.patch.stop()
        self.tmp.cleanup()

    def logged_events(self):
        lines = [line for f in self.config.logs_dir.glob("*.jsonl") for line in f.read_text(encoding="utf-8").splitlines()]
        return [r["event"] for r in map(json.loads, lines) if "event" in r]

    # ── 권한 ──────────────────────────────────────────────

    async def test_only_the_owner_can_press(self):
        for action in ("approve", "reject", "drop", "yes", "no"):
            ia = interaction(STRANGER)
            await self.bot.on_button(ia, action, self.draft_id, self.h12)
            self.assertEqual(ia.response.sent[0]["content"], "운영자만 누를 수 있다.", action)
            self.assertTrue(ia.response.sent[0]["ephemeral"])
            self.assertIsNone(ia.response.modal)
        ia = interaction(STRANGER)
        await self.bot.on_reason(ia, "reject", self.draft_id, self.h12, "사유")  # 사유 입력창도 다시 확인한다
        self.assertEqual(ia.response.sent[0]["content"], "운영자만 누를 수 있다.")
        self.assertEqual(self.store.status(self.draft_id), "awaiting_approval")
        self.assertEqual(self.logged_events().count("approval_denied"), 6)
        self.http.assert_not_called()

    # ── 승인 (확인 한 번 더) ──────────────────────────────

    async def test_approve_asks_for_confirmation_first(self):
        ia = interaction(OWNER)
        await self.bot.on_button(ia, "approve", self.draft_id, self.h12)
        (sent,) = ia.response.sent
        self.assertTrue(sent["ephemeral"])
        self.assertIn("이름 짓기", sent["content"])
        ids = [buttons.parse(item.custom_id)[0] for item in sent["view"].children]
        self.assertEqual(ids, ["yes", "no"])
        self.assertEqual(self.store.status(self.draft_id), "awaiting_approval")  # 아직 승인되지 않았다

    async def test_confirm_approves_and_closes_the_message(self):
        ia = interaction(OWNER)
        await self.bot.on_button(ia, "yes", self.draft_id, self.h12)
        self.assertEqual(self.store.status(self.draft_id), "approved")
        self.assertEqual(self.store.decisions(self.draft_id)[-1]["via"], "discord")
        self.assertIn("승인했다", ia.response.edited[0]["content"])
        self.assertIsNone(ia.response.edited[0]["view"])
        self.assertTrue(self.http.call_args.args[0].endswith("/channels/102/messages/999"))
        self.assertEqual(self.http.call_args.args[2]["components"], [])
        self.assertIn("승인함", self.http.call_args.args[2]["content"])
        self.assertEqual(ia.followup.sent, [])  # 경고 없음

    async def test_cancel_changes_nothing(self):
        ia = interaction(OWNER)
        await self.bot.on_button(ia, "no", self.draft_id, self.h12)
        self.assertEqual(ia.response.edited[0]["content"], "취소했다.")
        self.assertEqual(self.store.status(self.draft_id), "awaiting_approval")
        self.http.assert_not_called()

    async def test_stale_message_is_refused(self):
        self.store.update_draft(self.draft_id, note="고침", ko={"body": good_body("덧붙임.")})
        for action in ("approve", "reject", "drop", "yes"):
            ia = interaction(OWNER)
            await self.bot.on_button(ia, action, self.draft_id, self.h12)
            self.assertIn("초안이 바뀌었다", ia.response.sent[0]["content"], action)
            self.assertIsNone(ia.response.modal)
        self.assertEqual(self.store.status(self.draft_id), "writing")
        self.assertEqual(self.store.decisions(self.draft_id), [])

    async def test_already_decided_on_the_pi(self):
        self.store.record_decision(self.draft_id, "approved")  # Pi에서 먼저 승인했다
        for action in ("approve", "reject"):
            ia = interaction(OWNER)
            await self.bot.on_button(ia, action, self.draft_id, self.h12)
            self.assertIn("승인됨", ia.response.sent[0]["content"])
        ia = interaction(OWNER)  # 확인 창을 오래 둔 뒤 확정을 눌렀다
        self.store.record_decision(self.draft_id, "rejected", reason="다시 보니 아니다")
        await self.bot.on_button(ia, "yes", self.draft_id, self.h12)
        self.assertIn("처리할 수 없다", ia.response.sent[0]["content"])
        self.assertEqual(self.store.status(self.draft_id), "rejected")

    # ── 반려·접기 (사유 입력창) ───────────────────────────

    async def test_reject_opens_modal_then_records_reason(self):
        ia = interaction(OWNER)
        await self.bot.on_button(ia, "reject", self.draft_id, self.h12)
        modal = ia.response.modal
        self.assertIsInstance(modal, bot_module.ReasonModal)
        self.assertEqual(modal.title, "반려 사유")
        self.assertEqual(self.store.status(self.draft_id), "awaiting_approval")  # 사유를 내야 반려된다
        modal.reason.component._refresh_state(None, {"value": "  출처가 없다  "})
        sub = interaction(OWNER)
        await modal.on_submit(sub)
        self.assertEqual(self.store.status(self.draft_id), "rejected")
        record = self.store.decisions(self.draft_id)[-1]
        self.assertEqual((record["reason"], record["via"]), ("출처가 없다", "discord"))
        self.assertIn("반려함", sub.response.sent[0]["content"])
        self.assertTrue(sub.response.sent[0]["ephemeral"])
        self.assertIn("반려함", self.http.call_args.args[2]["content"])
        self.assertEqual(backlog.items(self.config, "blocked"), [])  # 반려만으로는 글감을 접지 않는다

    async def test_drop_holds_the_draft_and_blocks_the_backlog_item(self):
        ia = interaction(OWNER)
        await self.bot.on_button(ia, "drop", self.draft_id, self.h12)
        self.assertEqual(ia.response.modal.title, "글감 접기")
        sub = interaction(OWNER)
        await self.bot.on_reason(sub, "drop", self.draft_id, self.h12, "이 주제는 그만")
        self.assertEqual(self.store.status(self.draft_id), "held")
        self.assertEqual(backlog.items(self.config, "blocked")[0]["id"], "naming")
        self.assertIn("접음", sub.response.sent[0]["content"])
        self.assertIn("접음", self.http.call_args.args[2]["content"])

    async def test_reject_and_drop_run_the_cycle_right_away(self):
        self.watcher.return_value = True
        sub = interaction(OWNER)
        await self.bot.on_reason(sub, "reject", self.draft_id, self.h12, "출처가 없다")
        reply = sub.response.sent[0]["content"]
        self.assertIn("사이클을 바로 돌린다", reply)
        self.assertIn("임시 실행 1/5회", reply)
        self.assertIn("사이클을 바로 돌린다", self.http.call_args.args[2]["content"])  # #승인 메시지도 같은 말을 한다
        self.assertTrue(self.config.cycle_request_path.exists())

    async def test_confirmed_approval_does_not_run_the_cycle(self):
        self.watcher.return_value = True
        ia = interaction(OWNER)
        await self.bot.on_button(ia, "yes", self.draft_id, self.h12)
        self.assertFalse(self.config.cycle_request_path.exists())
        self.assertNotIn("임시 실행", self.http.call_args.args[2]["content"])
        self.assertIn("14:00", self.http.call_args.args[2]["content"])  # 승인한 글은 다음 14:00에 발행된다

    async def test_daily_limit_message(self):
        self.watcher.return_value = True
        with mock.patch("blogops.ondemand.count_today", return_value=5):
            sub = interaction(OWNER)
            await self.bot.on_reason(sub, "drop", self.draft_id, self.h12, "그만")
        self.assertIn("5회를 다 썼다", sub.response.sent[0]["content"])
        self.assertIn("다음 14:00 사이클에서", sub.response.sent[0]["content"])
        self.assertFalse(self.config.cycle_request_path.exists())

    async def test_without_the_path_unit_the_reply_does_not_promise_an_immediate_run(self):
        sub = interaction(OWNER)  # watcher=False: huninn-cycle-now.path를 설치하기 전
        await self.bot.on_reason(sub, "reject", self.draft_id, self.h12, "출처가 없다")
        self.assertIn("다음 14:00 사이클에서", sub.response.sent[0]["content"])
        self.assertNotIn("바로", sub.response.sent[0]["content"])
        self.assertFalse(self.config.cycle_request_path.exists())

    async def test_modal_submit_reads_the_text_input(self):
        modal = bot_module.ReasonModal(self.bot, "reject", self.draft_id, self.h12)
        modal.reason.component._refresh_state(None, {"value": "문장이 어색하다"})
        sub = interaction(OWNER)
        await modal.on_submit(sub)
        self.assertEqual(self.store.decisions(self.draft_id)[-1]["reason"], "문장이 어색하다")

    async def test_reason_for_stale_draft_is_refused(self):
        self.store.update_draft(self.draft_id, note="고침", ko={"body": good_body("덧붙임.")})
        sub = interaction(OWNER)
        await self.bot.on_reason(sub, "reject", self.draft_id, self.h12, "사유")
        self.assertIn("초안이 바뀌었다", sub.response.sent[0]["content"])
        self.assertEqual(self.store.decisions(self.draft_id), [])

    # ── 오류 ──────────────────────────────────────────────

    async def test_unexpected_error_is_reported_not_swallowed(self):
        ia = interaction(OWNER)
        with mock.patch("blogops.bot.decisions.preflight", side_effect=RuntimeError("boom")):
            with self.assertLogs("blogops.bot", level="ERROR"):  # 서버 로그에는 원인이 남는다
                await self.bot.on_button(ia, "approve", self.draft_id, self.h12)
        self.assertIn("review", ia.response.sent[0]["content"])  # 명령으로 하라고 알려 준다
        self.assertNotIn("boom", ia.response.sent[0]["content"])

    async def test_discord_edit_failure_is_a_followup_warning(self):
        self.http.return_value = (403, {"message": "Missing Access"})
        ia = interaction(OWNER)
        await self.bot.on_button(ia, "yes", self.draft_id, self.h12)
        self.assertEqual(self.store.status(self.draft_id), "approved")  # 결정은 이미 기록됐다
        self.assertIn("Missing Access", ia.followup.sent[0]["content"])
        self.assertNotIn("test-bot-token", ia.followup.sent[0]["content"])

    # ── 버튼 형식 ─────────────────────────────────────────

    async def test_dynamic_item_matches_what_notify_sends(self):
        import re
        for action in buttons.ACTIONS:
            value = buttons.custom_id(action, self.draft_id, self.hash)
            match = bot_module.ApprovalButton.__discord_ui_compiled_template__.fullmatch(value)
            self.assertIsNotNone(match, action)
            item = await bot_module.ApprovalButton.from_custom_id(None, None, match)
            self.assertEqual((item.action, item.draft_id, item.hash12), (action, self.draft_id, self.h12))
            self.assertEqual(item.custom_id, value)
        self.assertTrue(re.compile(buttons.CUSTOM_ID_TEMPLATE))

    async def test_bot_registers_dynamic_items(self):
        await self.bot.setup_hook()
        self.addCleanup(self.bot._sweeper.cancel)
        self.assertIn(bot_module.ApprovalButton.__discord_ui_compiled_template__,
                      self.bot._connection._view_store._dynamic_items)


if __name__ == "__main__":
    unittest.main()
