import unittest

from blogops import buttons

H = "0123456789abcdef" * 4


class ButtonsTest(unittest.TestCase):
    def test_round_trip(self):
        value = buttons.custom_id("approve", "20261013-pi-blog", H)
        self.assertEqual(value, "bo:approve:20261013-pi-blog:0123456789ab")
        self.assertEqual(buttons.parse(value), ("approve", "20261013-pi-blog", "0123456789ab"))

    def test_longest_id_fits_discord_limit(self):
        draft_id = "20261013-" + "a" * 60  # 슬러그 최대 60자
        for action in buttons.ACTIONS:
            self.assertLessEqual(len(buttons.custom_id(action, draft_id, H)), 100)

    def test_parse_rejects_foreign_ids(self):
        for value in ("", "approve", "bo:approve:x:y", "bo:delete:20261013-a:0123456789ab",
                      "bo:approve:20261013-a:0123456789", "bo:approve:20261013-a:0123456789ABc",
                      "xbo:approve:20261013-a:0123456789ab", "bo:approve:20261013-a:0123456789ab:extra"):
            self.assertIsNone(buttons.parse(value), value)
        with self.assertRaises(ValueError):
            buttons.custom_id("delete", "20261013-a", H)
        with self.assertRaises(ValueError):
            buttons.custom_id("approve", "../../etc", H)

    def test_components(self):
        urls = {"ko": "https://p.example/t/posts/a/", "en": "https://p.example/t/en/posts/a/"}
        (row,) = buttons.approval_components("20261013-a", H, urls)
        self.assertEqual(row["type"], 1)
        labels = [b["label"] for b in row["components"]]
        self.assertEqual(labels, ["미리보기", "영어판", "승인", "반려", "접기"])
        link, en, approve, reject, drop = row["components"]
        self.assertEqual((link["style"], link["url"]), (buttons.LINK, urls["ko"]))
        self.assertNotIn("custom_id", link)  # 링크 버튼에는 custom_id가 없다
        self.assertEqual(en["url"], urls["en"])
        self.assertEqual([approve["style"], reject["style"], drop["style"]],
                         [buttons.SUCCESS, buttons.DANGER, buttons.SECONDARY])
        self.assertEqual(buttons.parse(approve["custom_id"])[0], "approve")
        self.assertEqual(buttons.parse(drop["custom_id"]), ("drop", "20261013-a", H[:12]))

    def test_components_without_preview(self):
        for urls in (None, {}, {"en": ""}):
            (row,) = buttons.approval_components("20261013-a", H, urls)
            self.assertEqual([b["label"] for b in row["components"]], ["승인", "반려", "접기"])


if __name__ == "__main__":
    unittest.main()
