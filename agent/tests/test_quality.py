import tempfile
import unittest

from blogops import quality
from blogops.config import find_tool
from helpers import fake_anthropic_key, good_body, make_env

SRC = [{"title": "pre-commit.md", "url": "https://github.com/Hun0305/unattendant/blob/main/docs/pre-commit.md"}]


def ko(body=None, title="Pi에서 gitleaks가 35초 걸린 이유", **extra):
    return {"title": title, "description": "규칙 222개를 24개로 줄인 기록", "tags": ["gitleaks"],
            "body": good_body() if body is None else body, **extra}


def no_tool(config, store, draft_id):
    return []


class QualityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config, self.store = make_env(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, draft_id, scan=no_tool, build=no_tool):
        return quality.check_quality(self.config, self.store, draft_id, scan=scan, build=build)

    def draft(self, slug="gitleaks-on-pi", series="ops-log", sources=None, **ko_kwargs):
        return self.store.create_draft(slug=slug, series=series, ko=ko(**ko_kwargs), sources=sources)

    def assertProblem(self, result, text):
        self.assertFalse(result["passed"])
        self.assertTrue(any(text in p for p in result["problems"]), result["problems"])

    def test_good_draft_passes(self):
        draft_id = self.draft(sources=SRC, body=good_body("기본 규칙 222개를 쓰면 34.9초가 걸렸다."))
        result = self.check(draft_id)
        self.assertTrue(result["passed"], result["problems"])
        self.assertEqual(self.store.status(draft_id), "ready")

    def test_length(self):
        self.assertProblem(self.check(self.draft(slug="short", body="짧다")), "짧다")
        self.assertProblem(self.check(self.draft(slug="long", body="가" * 7000)), "길다")

    def test_numbers_need_sources(self):
        self.assertProblem(self.check(self.draft(body=good_body("34.9초"))), "출처")
        bad = [{"title": "", "url": "ftp://x"}]
        self.assertProblem(self.check(self.draft(slug="bad-src", sources=bad)), "title과 http(s) url")

    def test_repo_links_must_exist(self):
        missing = [{"title": "없는 문서", "url": "https://github.com/Hun0305/unattendant/blob/main/docs/nope.md"}]
        self.assertProblem(self.check(self.draft(sources=missing)), "레포에 없다")
        body_link = good_body("[사이트 README](https://github.com/Hun0305/unattendant.dev/blob/main/README.md)")
        self.assertTrue(self.check(self.draft(slug="site-link", body=body_link))["passed"])
        escape = [{"title": "밖", "url": "https://github.com/Hun0305/unattendant/blob/main/../../etc/passwd"}]
        self.assertProblem(self.check(self.draft(slug="escape", sources=escape)), "레포에 없다")

    def test_privacy(self):
        for text, expect in (("공유기 192.168.0.50", "내부 IP"), ("tailnet 100.101.102.103", "내부 IP"),
                             ("MAC aa:bb:cc:dd:ee:ff", "MAC"), ("연락 someone@example.com", "이메일")):
            with self.subTest(text=text):
                slug = f"p{abs(hash(text)) % 100000}"
                self.assertProblem(self.check(self.draft(slug=slug, body=good_body(text))), expect)
        ok = good_body("Caddy는 127.0.0.1:8080에 붙는다. 커밋 공동 작성자 noreply@anthropic.com")
        result = self.check(self.draft(slug="ok-addr", body=ok, sources=SRC))
        self.assertTrue(result["passed"], result["problems"])

    def test_series_rules(self):
        self.assertProblem(self.check(self.draft(slug="llm", series="pi-llm")), "시리즈가 아니다")
        self.assertProblem(self.check(self.draft(slug="weekly", series="weekly-report")), "영어판")

    def test_forbidden_fields(self):
        draft_id = self.draft()
        path = self.store.draft_paths(draft_id)["ko"]
        path.write_text(path.read_text(encoding="utf-8").replace("---\n", '---\nauthor: "human"\n', 1), encoding="utf-8")
        self.assertProblem(self.check(draft_id), "author")

    def test_no_h1_in_body(self):
        self.assertProblem(self.check(self.draft(slug="h1", body="# 제목\n\n" + good_body())), "h1")
        fenced = good_body("\n\n```bash\n# 코드 블록 안의 주석은 제목이 아니다\n```\n\n## 소제목\n")
        result = self.check(self.draft(slug="fenced", body=fenced))
        self.assertTrue(result["passed"], result["problems"])

    def test_duplicates(self):
        self.assertProblem(self.check(self.draft(slug="starting-unattendant")), "같은 슬러그")
        self.assertProblem(self.check(self.draft(slug="other", title="AI가 혼자 운영하는 블로그를 만들기로 했다!")), "거의 같다")

    def test_held_after_three_different_failures(self):
        draft_id = self.draft(body="짧다")
        self.check(draft_id)
        self.check(draft_id)  # 같은 내용을 다시 검사해도 한 번으로 센다
        self.assertEqual(self.store.consecutive_quality_failures(draft_id), 1)
        self.store.update_draft(draft_id, note="고침 1", ko={"body": "조금 길다"})
        self.check(draft_id)
        self.store.update_draft(draft_id, note="고침 2", ko={"body": "아직 짧다"})
        result = self.check(draft_id)
        self.assertTrue(result["held"])
        self.assertEqual(self.store.status(draft_id), "held")

    def test_build_runs_only_when_clean(self):
        calls = []

        def build(config, store, draft_id):
            calls.append(draft_id)
            return ["빌드 실패(가짜)"]
        self.check(self.draft(slug="dirty", body="짧다"), build=build)
        self.assertEqual(calls, [])
        result = self.check(self.draft(slug="clean"), build=build)
        self.assertEqual(calls, ["20261008-clean"])
        self.assertProblem(result, "빌드 실패")


@unittest.skipUnless(find_tool("gitleaks") and find_tool("hugo"), "gitleaks·hugo가 있어야 한다")
class ToolIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config, self.store = make_env(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_gitleaks_finds_secret(self):
        draft_id = self.store.create_draft(slug="leak", series="ops-log", ko=ko(body=good_body(f"키 {fake_anthropic_key()}")))
        problems = quality.gitleaks_scan(self.config, self.store, draft_id)
        self.assertTrue(any("비밀값" in p for p in problems), problems)
        clean = self.store.create_draft(slug="clean", series="ops-log", ko=ko())
        self.assertEqual(quality.gitleaks_scan(self.config, self.store, clean), [])

    def test_hugo_build(self):
        draft_id = self.store.create_draft(slug="build-ok", series="ops-log", ko=ko(),
                                           en={"title": "Build", "description": "d", "tags": ["t"], "body": "body"})
        self.assertEqual(quality.hugo_build(self.config, self.store, draft_id), [])
        broken = self.store.create_draft(slug="build-broken", series="ops-log", ko=ko(body=good_body("{{< 없는단축코드 >}}")))
        problems = quality.hugo_build(self.config, self.store, broken)
        self.assertTrue(any("빌드가 실패" in p for p in problems), problems)
        self.assertFalse((self.config.site_dir / "content" / "posts" / "build-ok").exists())  # 실제 사이트는 건드리지 않는다


if __name__ == "__main__":
    unittest.main()
