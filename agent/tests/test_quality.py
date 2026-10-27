import tempfile
import unittest

from blogops import quality
from blogops.config import find_tool
from helpers import fake_anthropic_key, good_body, make_env

SRC = [{"title": "pre-commit.md", "url": "https://github.com/Hun0305/unattendant/blob/main/docs/pre-commit.md"}]


def ko(body=None, title="Pi에서 gitleaks가 35초 걸린 이유", **extra):
    return {"title": title, "description": "규칙 222개를 24개로 줄인 기록", "tags": ["gitleaks"],
            "body": good_body() if body is None else body, **extra}


GOOD_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><title>x</title><rect width="10" height="10"/></svg>'


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

    def test_post_links_must_exist(self):
        ok = good_body("[첫 글](/posts/starting-unattendant/)과 [전체 주소](https://example.org/posts/starting-unattendant/#두뇌)")
        self.assertTrue(self.check(self.draft(slug="link-ok", body=ok))["passed"])
        for text, expect in (("[없는 글](/posts/no-such-post/)", "/posts/no-such-post/"),
                             ("[영어판 없음](https://example.org/en/posts/starting-unattendant/)", "/en/posts/starting-unattendant/")):
            with self.subTest(text=text):
                slug = f"l{abs(hash(text)) % 100000}"
                self.assertProblem(self.check(self.draft(slug=slug, body=good_body(text))), expect)

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
        # 영어판은 발행 뒤에 붙이므로 주간 보고서 초안에도 없어도 된다
        result = self.check(self.draft(slug="weekly", series="weekly-report"))
        self.assertFalse([p for p in result["problems"] if "영어" in p], result["problems"])

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

    # ── 그림 ─────────────────────────────────────────────
    def figure_draft(self, fig='{{< fig src="a.svg" by="ai" caption="Claude가 SVG로 그렸다" >}}', files=None):
        files = {"a.svg": GOOD_SVG} if files is None else files
        self.figures = getattr(self, "figures", 0) + 1  # 한 시험에서 여러 번 부를 수 있다
        draft_id = self.draft(slug=f"with-figure-{self.figures}", body=good_body() + "\n\n" + fig + "\n")
        for name, data in files.items():
            path = self.config.drafts_dir / draft_id / name
            path.write_bytes(data if isinstance(data, bytes) else data.encode())
        return draft_id

    def test_figure_ok(self):
        self.assertTrue(self.check(self.figure_draft())["passed"])

    def test_figure_file_must_exist_and_be_used(self):
        self.assertProblem(self.check(self.figure_draft(files={})), "초안 폴더에 없다")
        self.assertProblem(self.check(self.figure_draft(fig="", files={"a.svg": GOOD_SVG})), "쓰지 않는 그림 파일")

    def test_figure_needs_caption_and_alt(self):
        self.assertProblem(self.check(self.figure_draft(fig='{{< fig src="a.svg" by="ai" >}}')), "caption이 없다")
        png = {"a.png": b"\x89PNG"}
        self.assertProblem(self.check(self.figure_draft(fig='{{< fig src="a.png" by="pd" caption="출처: 위키미디어" >}}', files=png)),
                           "alt가 없다")
        ok = self.check(self.figure_draft(fig='{{< fig src="a.png" by="pd" alt="오딘" caption="출처: 위키미디어" >}}', files=png))
        self.assertTrue(ok["passed"], ok["problems"])

    def test_figure_needs_by(self):
        # 글 하단 "그림 출처"가 by로 만들어진다. AI가 그린 그림을 밝히지 않고 넘어가지 못하게 한다
        self.assertProblem(self.check(self.figure_draft(fig='{{< fig src="a.svg" caption="그림" >}}')), "by가 없거나 틀렸다")
        self.assertProblem(self.check(self.figure_draft(fig='{{< fig src="a.svg" by="me" caption="그림" >}}')), "by가 없거나 틀렸다")

    def test_figure_size_limit(self):
        big = {"a.svg": GOOD_SVG + " " * (self.config.asset_max_bytes + 1)}
        self.assertProblem(self.check(self.figure_draft(files=big)), "그림 파일이 크다")

    def test_svg_must_not_run_code_or_load_remote(self):
        for bad in ('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
                    '<svg xmlns="http://www.w3.org/2000/svg" onload="x()"></svg>',
                    '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://evil.example/x.png"/></svg>'):
            self.assertProblem(self.check(self.figure_draft(files={"a.svg": bad})), "스크립트나 외부 참조")

    def test_figure_changes_the_hash(self):
        draft_id = self.figure_draft()
        before = self.store.content_hash(draft_id)
        (self.config.drafts_dir / draft_id / "a.svg").write_text(GOOD_SVG.replace("rect", "circle"))
        self.assertNotEqual(before, self.store.content_hash(draft_id))


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
