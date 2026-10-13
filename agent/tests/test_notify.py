import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from blogops import buttons, env, indexnow, log, notify, preview
from blogops.indexnow import IndexNowError
from blogops.notify import NotifyError
from helpers import good_body, make_env

FAKE_ENV = ("# 시험용 가짜 값\nDISCORD_BOT_TOKEN=test-bot-token\nDISCORD_CH_URGENT=101\n"
            "DISCORD_CH_APPROVAL=102\nexport DISCORD_CH_DAILY='103'\nDISCORD_OWNER_ID=222\n")


class FakeTransport:
    def __init__(self, *responses):
        self.calls = []
        self.responses = list(responses) or [(200, {"id": "999"})]

    def __call__(self, url, headers, payload):
        self.calls.append((url, headers, payload))
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]


class NotifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config, self.store = make_env(self.tmp.name)
        env_file = Path(self.tmp.name) / "huninn.env"
        env_file.write_text(FAKE_ENV, encoding="utf-8")
        self.patch = mock.patch.dict(os.environ, {"BLOGOPS_ENV_FILE": str(env_file)})
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_env(self):
        self.assertEqual(env.get(self.config, "DISCORD_CH_DAILY"), "103")  # export·따옴표 처리
        with self.assertRaises(env.EnvError) as cm:
            env.get(self.config, "NOT_SET_KEY")
        self.assertIn("NOT_SET_KEY", str(cm.exception))

    def test_levels(self):
        t = FakeTransport()
        notify.notify_human(self.config, "info", "오늘 한 일", transport=t)
        notify.notify_human(self.config, "warn", "push 실패", transport=t)
        notify.notify_human(self.config, "critical", "사이트 응답 없음", transport=t)
        (u1, h1, p1), (u2, _, p2), (u3, _, p3) = t.calls
        self.assertTrue(u1.endswith("/channels/103/messages"))
        self.assertEqual(h1["Authorization"], "Bot test-bot-token")
        self.assertTrue(h1["User-Agent"].startswith("DiscordBot ("))
        self.assertTrue(u2.endswith("/channels/101/messages"))
        self.assertTrue(p2["content"].startswith("**주의**"))
        self.assertEqual(p2["allowed_mentions"]["users"], [])
        self.assertTrue(p3["content"].startswith("<@222> **긴급**"))
        self.assertEqual(p3["allowed_mentions"], {"parse": [], "users": ["222"]})
        with self.assertRaises(NotifyError):
            notify.notify_human(self.config, "loud", "x", transport=t)

    def test_truncate_retry_and_errors(self):
        t = FakeTransport((429, {"retry_after": 0.01}), (200, {"id": "1"}))
        notify.send(self.config, "daily", "가" * 3000, transport=t)
        self.assertEqual(len(t.calls), 2)
        self.assertEqual(len(t.calls[-1][2]["content"]), notify.MAX_LEN)
        with self.assertRaises(NotifyError) as cm:
            notify.send(self.config, "daily", "x", transport=FakeTransport((401, {"message": "401: Unauthorized"})))
        self.assertNotIn("test-bot-token", str(cm.exception))

    def draft(self, **kwargs):
        draft_id = self.store.create_draft(slug="naming", series="ops-log",
                                           ko={"title": "이름 짓기", "description": "요약", "tags": ["meta"], "body": good_body()},
                                           **kwargs)
        self.store.record_quality(draft_id, True, [])
        return draft_id

    @staticmethod
    def fake_previewer(config, store, draft_id):
        return {"draft_id": draft_id, "token": "t" * 40, "hash": store.content_hash(draft_id), "reused": False,
                "urls": {"ko": "https://preview.example/ttt/posts/naming/", "en": "https://preview.example/ttt/en/posts/naming/"}}

    def test_request_approval_sends_buttons_and_commands(self):
        draft_id = self.draft()
        t = FakeTransport()
        result = notify.request_approval(self.config, self.store, draft_id, transport=t, previewer=self.fake_previewer)
        self.assertEqual(result["warnings"], [])
        self.assertTrue(result["preview"])
        self.assertNotIn("preview.example", str(result))  # 미리보기 주소(열쇠)는 Huninn에게 돌려주지 않는다
        self.assertEqual(self.store.status(draft_id), "awaiting_approval")
        url, _, payload = t.calls[0]
        self.assertTrue(url.endswith("/channels/102/messages"))
        self.assertIn(f"approve {draft_id}", payload["content"])  # 버튼이 안 될 때의 길
        self.assertIn(f'reject {draft_id} "사유"', payload["content"])
        self.assertTrue(payload["content"].startswith("<@222>"))
        (row,) = payload["components"]
        self.assertEqual([b["label"] for b in row["components"]], ["미리보기", "영어판", "승인", "반려", "접기"])
        self.assertEqual(row["components"][0]["url"], "https://preview.example/ttt/posts/naming/")
        h = self.store.content_hash(draft_id)
        self.assertEqual(buttons.parse(row["components"][2]["custom_id"]), ("approve", draft_id, h[:12]))
        # 결정이 나면 이 메시지를 고칠 수 있게 위치를 적어 둔다
        self.assertEqual(self.store.approval_message_ref(draft_id, h), {"channel_id": "102", "message_id": "999"})

    def test_request_approval_builds_real_preview(self):
        draft_id = self.draft()
        t = FakeTransport()
        notify.request_approval(self.config, self.store, draft_id, transport=t)
        record = self.store.preview_record(draft_id)
        (row,) = t.calls[0][2]["components"]
        self.assertEqual(row["components"][0]["url"], f"https://preview.unattendant.dev/{record['token']}/posts/naming/")
        self.assertTrue((self.config.previews_dir / record["token"] / "posts" / "naming" / "index.html").exists())

    def test_request_approval_without_preview_still_asks(self):
        draft_id = self.draft()

        def broken(config, store, draft_id):
            raise preview.PreviewError("hugo가 없다")

        t = FakeTransport()
        result = notify.request_approval(self.config, self.store, draft_id, transport=t, previewer=broken)
        self.assertFalse(result["preview"])
        self.assertIn("미리보기를 만들지 못했다", result["warnings"][0])
        payload = t.calls[0][2]
        self.assertIn("미리보기를 만들지 못했다", payload["content"])
        self.assertIn(f"preview {draft_id}", payload["content"])  # 다시 만드는 방법을 알려 준다
        (row,) = payload["components"]
        self.assertEqual([b["label"] for b in row["components"]], ["승인", "반려", "접기"])

    def test_request_approval_records_even_if_discord_fails(self):
        draft_id = self.draft()
        result = notify.request_approval(self.config, self.store, draft_id, transport=FakeTransport((500, {})),
                                         previewer=self.fake_previewer)
        self.assertEqual(self.store.status(draft_id), "awaiting_approval")
        self.assertIn("보내지 못했다", result["warnings"][0])
        self.assertIsNone(self.store.approval_message_ref(draft_id, self.store.content_hash(draft_id)))

    def test_request_approval_needs_ready(self):
        draft_id = self.store.create_draft(slug="naming", series="ops-log",
                                           ko={"title": "이름 짓기", "description": "요약", "tags": ["meta"], "body": good_body()})
        t = FakeTransport()
        with self.assertRaises(Exception):
            notify.request_approval(self.config, self.store, draft_id, transport=t)
        self.assertEqual(t.calls, [])  # 상태가 안 맞으면 디스코드로 보내지 않는다

    def test_close_approval_message(self):
        draft_id = self.draft()
        h = self.store.content_hash(draft_id)
        t = FakeTransport()
        self.assertFalse(notify.close_approval_message(self.config, self.store, draft_id, h, "x", transport=t))
        self.assertEqual(t.calls, [])  # 보낸 적 없는 메시지는 건드리지 않는다
        self.store.record_approval_request(draft_id)
        self.store.record_approval_message(draft_id, h, 102, 999)
        self.assertTrue(notify.close_approval_message(self.config, self.store, draft_id, h, "가" * 3000, transport=t))
        url, headers, payload = t.calls[0]
        self.assertTrue(url.endswith("/channels/102/messages/999"))
        self.assertEqual(len(payload["content"]), notify.MAX_LEN)
        self.assertEqual(payload["components"], [])
        with self.assertRaises(NotifyError) as cm:
            notify.close_approval_message(self.config, self.store, draft_id, h, "x",
                                          transport=FakeTransport((403, {"message": "Missing Access"})))
        self.assertIn("Missing Access", str(cm.exception))
        self.assertNotIn("test-bot-token", str(cm.exception))


class IndexNowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config, _ = make_env(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_key_and_request(self):
        with self.assertRaises(IndexNowError):
            indexnow.request_indexing(self.config, ["https://example.org/posts/a/"], transport=FakeTransport())
        static = self.config.site_dir / "static"
        static.mkdir()
        (static / "naver1234.html").write_text("인증 파일")  # 다른 파일은 무시한다
        (static / ("a" * 32 + ".txt")).write_text("다른 내용\n")  # 이름과 내용이 다르면 키가 아니다
        self.assertIsNone(indexnow.find_key(self.config))
        key = indexnow.create_key(self.config)
        self.assertEqual(indexnow.find_key(self.config), key)
        self.assertEqual(indexnow.create_key(self.config), key)  # 이미 있으면 그대로
        t = FakeTransport((202, {}))
        result = indexnow.request_indexing(self.config, ["https://example.org/posts/a/", "https://example.org/posts/a/"],
                                           transport=t)
        self.assertEqual(result["urls"], ["https://example.org/posts/a/"])
        _, _, payload = t.calls[0]
        self.assertEqual(payload, {"host": "example.org", "key": key, "keyLocation": f"https://example.org/{key}.txt",
                                   "urlList": ["https://example.org/posts/a/"]})
        with self.assertRaises(IndexNowError):
            indexnow.request_indexing(self.config, ["https://evil.example/x"], transport=t)
        with self.assertRaises(IndexNowError):
            indexnow.request_indexing(self.config, ["https://example.org/x"], transport=FakeTransport((403, {})))


class CycleGuardTest(unittest.TestCase):
    def test_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _ = make_env(tmp)
            guard = log.CycleGuard(config, cycle_id="c1")
            for _ in range(config.max_tool_calls_per_cycle):
                guard.check("list_drafts")
            with self.assertRaises(log.ToolLimitError):
                guard.check("list_drafts")


if __name__ == "__main__":
    unittest.main()
