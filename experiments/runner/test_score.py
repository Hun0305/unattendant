"""과제 세트 llm-tasks-v1 채점기 시험.

    python3 -m unittest discover -s experiments/runner -p 'test_*.py'
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

PROMPTSET = Path(__file__).resolve().parents[1] / "promptsets" / "llm-tasks-v1"
_spec = importlib.util.spec_from_file_location("score_v1", PROMPTSET / "score.py")
score = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score)

GOLD_T1 = {"actions": [{"device": "window", "op": "close", "target": "all", "value": None},
                       {"device": "ac", "op": "set_temp", "target": None, "value": 22}], "reject": None}


class ItemsTest(unittest.TestCase):
    def test_gold_answers_score_full(self):
        for task, (ok, n) in score.selfcheck().items():
            self.assertEqual(ok, n, task)

    def test_counts_and_unique_ids(self):
        counts = {task: len(score.load_items(task)) for task in score.TASKS}
        self.assertEqual(counts, {"t1": 30, "t2": 30, "t3": 20, "t4": 20})
        ids = [it["id"] for task in score.TASKS for it in score.load_items(task)]
        self.assertEqual(len(ids), len(set(ids)))

    def test_examples_are_not_test_items(self):
        import tomllib
        prompts = tomllib.loads((PROMPTSET / "prompts.toml").read_text(encoding="utf-8"))
        for task in score.TASKS:
            inputs = {it["input"] for it in score.load_items(task)}
            for example in prompts[task]["examples"]:
                self.assertNotIn(example["input"], inputs, task)
                gold_like = example["output"]
                if task in ("t1", "t3"):
                    json.loads(gold_like)  # 예시 출력도 JSON으로 읽혀야 한다


class T1Test(unittest.TestCase):
    def check(self, output: str) -> dict:
        return score.score_t1(output, GOLD_T1)

    def test_fenced_and_reordered_is_correct(self):
        swapped = {"actions": list(reversed(GOLD_T1["actions"])), "reject": None}
        self.assertTrue(self.check("```json\n" + json.dumps(swapped) + "\n```")["correct"])

    def test_numeric_string_value_is_accepted(self):
        loose = json.loads(json.dumps(GOLD_T1))
        loose["actions"][1]["value"] = "22"
        self.assertTrue(self.check(json.dumps(loose))["correct"])

    def test_schema_failures(self):
        no_target = json.loads(json.dumps(GOLD_T1))
        no_target["actions"][0]["target"] = None  # 창문은 위치가 있어야 한다
        result = self.check(json.dumps(no_target))
        self.assertTrue(result["parsed"])
        self.assertFalse(result["schema_ok"])
        self.assertFalse(self.check('{"actions": [{"device": "ac", "op": "on"}], "reject": "unsupported"}')["schema_ok"])
        self.assertFalse(self.check("에어컨을 켤게요")["parsed"])

    def test_extra_action_is_wrong(self):
        extra = json.loads(json.dumps(GOLD_T1))
        extra["actions"].append({"device": "media", "op": "play", "target": None, "value": None})
        result = self.check(json.dumps(extra))
        self.assertTrue(result["schema_ok"])
        self.assertFalse(result["correct"])


class T2T3T4Test(unittest.TestCase):
    def test_t2_label_matching(self):
        self.assertTrue(score.score_t2("라벨: 교환/반품", "교환·반품")["correct"])
        self.assertFalse(score.score_t2("배송 또는 결제", "배송")["correct"])  # 라벨이 둘이면 오답
        self.assertFalse(score.score_t2("반품", "교환·반품")["correct"])

    def test_t3_fields(self):
        gold = {"date": "2026-12-13", "time": "09:30", "place": ["인천공항 제1터미널 3층 A카운터 앞"], "people": 5}
        good = '{"date": "2026-12-13", "time": "9:30", "place": "인천공항 제1터미널 3층 A카운터 앞", "people": "5"}'
        self.assertTrue(score.score_t3(good, gold)["correct"])
        missing = '{"date": "2026-12-13", "time": "09:30", "place": "인천공항 제1터미널 3층 A카운터 앞"}'
        result = score.score_t3(missing, gold)
        self.assertEqual(result["fields_correct"], 3)
        self.assertFalse(result["correct"])

    def test_t4_keywords_forbid_and_drift(self):
        gold = {"keywords": [["토요일"]], "forbid": ["수요일"]}
        self.assertTrue(score.score_t4("스티로폼은 토요일에만 내놓을 수 있습니다.", gold)["correct"])
        self.assertFalse(score.score_t4("수요일과 토요일에 내놓습니다.", gold)["correct"])
        self.assertFalse(score.language_drift("주말에는 오후 6시까지 엽니다."))
        self.assertTrue(score.language_drift("周末开到下午6点。"))
        self.assertTrue(score.language_drift("It closes at 6 PM on weekends."))
        self.assertTrue(score.language_drift("주말에는 6時까지 엽니다."))


if __name__ == "__main__":
    unittest.main()
