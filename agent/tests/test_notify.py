import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from blogops import env, indexnow, log, notify
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

    def test_request_approval(self):
        draft_id = self.store.create_draft(slug="naming", series="ops-log",
                                           ko={"title": "이름 짓기", "description": "요약", "tags": ["meta"], "body": good_body()})
        self.store.record_quality(draft_id, True, [])
        t = FakeTransport()
        result = notify.request_approval(self.config, self.store, draft_id, transport=t)
        self.assertEqual(result["warnings"], [])
        self.assertEqual(self.store.status(draft_id), "awaiting_approval")
        url, _, payload = t.calls[0]
        self.assertTrue(url.endswith("/channels/102/messages"))
        self.assertIn(f"approve {draft_id}", payload["content"])
        self.assertIn(f'reject {draft_id} "사유"', payload["content"])
        self.assertTrue(payload["content"].startswith("<@222>"))

    def test_request_approval_records_even_if_discord_fails(self):
        draft_id = self.store.create_draft(slug="naming", series="ops-log",
                                           ko={"title": "이름 짓기", "description": "요약", "tags": ["meta"], "body": good_body()})
        self.store.record_quality(draft_id, True, [])
        result = notify.request_approval(self.config, self.store, draft_id, transport=FakeTransport((500, {})))
        self.assertEqual(self.store.status(draft_id), "awaiting_approval")
        self.assertIn("보내지 못했다", result["warnings"][0])

    def test_request_approval_needs_ready(self):
        draft_id = self.store.create_draft(slug="naming", series="ops-log",
                                           ko={"title": "이름 짓기", "description": "요약", "tags": ["meta"], "body": good_body()})
        t = FakeTransport()
        with self.assertRaises(Exception):
            notify.request_approval(self.config, self.store, draft_id, transport=t)
        self.assertEqual(t.calls, [])  # 상태가 안 맞으면 디스코드로 보내지 않는다


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
