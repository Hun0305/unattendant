"""과제 세트 llm-tasks-v1 채점 (docs/experiments.md 6절). 다른 LLM을 쓰지 않는 규칙 기반 채점이다.

T1 명령 → JSON  파싱(응답의 첫 JSON 객체), 스키마(장치·명령·위치·값 범위), 정답(동작 묶음과 reject가 같음, 순서 무관)
T2 의도 분류    응답에 라벨이 정확히 하나 나오면 그 라벨 (공백·가운뎃점·빗금·문장부호 무시)
T3 정보 추출    date, time, place, people을 하나씩 대조. 넷 다 맞으면 정답
T4 짧은 답      필수 키워드 묶음마다 하나 이상 포함(공백·쉼표 무시)하고 금지어가 없으면 정답.
                언어 이탈(한자·가나가 섞이거나, 글자 중 한글이 절반 미만)은 정답과 따로 센다

채점 규칙도 측정 방법이다. 바꾸면 과제 세트 버전을 올린다.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = {"t1": "t1_command.jsonl", "t2": "t2_intent.jsonl", "t3": "t3_extract.jsonl", "t4": "t4_answer.jsonl"}

# ── 공통 ─────────────────────────────────────────────

def load_items(task: str) -> list[dict]:
    return [json.loads(line) for line in (HERE / TASKS[task]).read_text(encoding="utf-8").splitlines() if line]


def extract_json(text: str) -> object | None:
    """응답에서 처음으로 읽히는 JSON 객체. 코드 블록이나 앞뒤 설명이 있어도 된다."""
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text, match.start())
        except ValueError:
            continue
        return value
    return None


def as_int(value: object) -> int | None | str:
    """정수로 읽히면 정수, null이면 None, 아니면 'invalid'."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "invalid"
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"\s*-?\d+\s*", value):
        return int(value)
    return "invalid"


# ── T1 명령 → JSON ───────────────────────────────────

DEVICES = {
    "window": {"ops": {"open", "close", "set"}, "targets": {"driver", "passenger", "rear_left", "rear_right", "all"},
               "values": {"set": (0, 100)}},
    "sunroof": {"ops": {"open", "close"}, "targets": None, "values": {}},
    "ac": {"ops": {"on", "off", "set_temp"}, "targets": None, "values": {"set_temp": (16, 30)}},
    "fan": {"ops": {"set_speed"}, "targets": None, "values": {"set_speed": (1, 5)}},
    "seat_heater": {"ops": {"on", "off", "set_level"}, "targets": {"driver", "passenger"}, "values": {"set_level": (1, 3)}},
    "wiper": {"ops": {"on", "off", "set_speed"}, "targets": None, "values": {"set_speed": (1, 3)}},
    "light": {"ops": {"on", "off"}, "targets": {"interior", "headlight"}, "values": {}},
    "media": {"ops": {"play", "pause", "next", "previous", "set_volume"}, "targets": None, "values": {"set_volume": (0, 30)}},
}


def t1_action(action: object) -> tuple | None:
    """스키마에 맞으면 비교용 튜플 (device, op, target, value), 아니면 None."""
    if not isinstance(action, dict):
        return None
    spec = DEVICES.get(action.get("device"))
    if spec is None or action.get("op") not in spec["ops"]:
        return None
    op, target, value = action["op"], action.get("target"), as_int(action.get("value"))
    if spec["targets"] is None:
        if target is not None:
            return None
    elif target not in spec["targets"]:
        return None
    if op in spec["values"]:
        low, high = spec["values"][op]
        if not isinstance(value, int) or not low <= value <= high:
            return None
    elif value is not None:
        return None
    return action["device"], op, target, value


def t1_parse(obj: object) -> tuple[Counter, object] | None:
    """스키마에 맞으면 (동작 묶음, reject), 아니면 None."""
    if not isinstance(obj, dict) or not isinstance(obj.get("actions"), list):
        return None
    reject = obj.get("reject")
    if reject not in (None, "unsupported") or (reject and obj["actions"]):
        return None
    actions = [t1_action(a) for a in obj["actions"]]
    if any(a is None for a in actions):
        return None
    return Counter(actions), reject


def score_t1(output: str, gold: dict) -> dict:
    obj = extract_json(output)
    parsed = t1_parse(obj) if obj is not None else None
    return {"parsed": obj is not None, "schema_ok": parsed is not None,
            "correct": parsed is not None and parsed == t1_parse(gold)}


# ── T2 의도 분류 ─────────────────────────────────────

LABELS = ["배송", "교환·반품", "결제", "회원정보", "상품문의"]
_STRIP = re.compile(r"[\s·・/\\.,:;'\"`*()\[\]{}<>\-_~!?]")


def norm_label(text: str) -> str:
    return _STRIP.sub("", text)


def score_t2(output: str, gold: str) -> dict:
    text = norm_label(output)
    found = [label for label in LABELS if norm_label(label) in text]
    label = found[0] if len(found) == 1 else None
    return {"label": label, "labels_found": found, "correct": label == gold}


# ── T3 정보 추출 ─────────────────────────────────────

_QUOTES = re.compile(r"[\s'\"‘’“”「」『』`]")


def norm_place(text: object) -> str | None:
    return _QUOTES.sub("", text) if isinstance(text, str) else None


def norm_time(text: object) -> str | None:
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", text) if isinstance(text, str) else None
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None


def score_t3(output: str, gold: dict) -> dict:
    obj = extract_json(output)
    fields = {"date": False, "time": False, "place": False, "people": False}
    if isinstance(obj, dict):
        fields["date"] = isinstance(obj.get("date"), str) and obj["date"].strip() == gold["date"]
        fields["time"] = norm_time(obj.get("time")) == gold["time"]
        fields["place"] = norm_place(obj.get("place")) in {norm_place(p) for p in gold["place"]}
        fields["people"] = "people" in obj and as_int(obj["people"]) == gold["people"]
    return {"parsed": isinstance(obj, dict), "fields": fields, "fields_correct": sum(fields.values()),
            "correct": all(fields.values())}


# ── T4 짧은 답 ───────────────────────────────────────

def norm_answer(text: str) -> str:
    return re.sub(r"[\s,]", "", text)


def language_drift(text: str) -> bool:
    """한자·가나가 섞였거나, 글자(숫자·기호 제외) 중 한글이 절반 미만이면 이탈."""
    letters = [c for c in text if c.isalpha()]
    hangul = sum(1 for c in letters if "가" <= c <= "힣" or "ㄱ" <= c <= "ㆎ")
    han_or_kana = sum(1 for c in letters if "㐀" <= c <= "鿿" or "぀" <= c <= "ヿ")
    return han_or_kana > 0 or (bool(letters) and hangul / len(letters) < 0.5)


def score_t4(output: str, gold: dict) -> dict:
    text = norm_answer(output)
    keywords_ok = all(any(norm_answer(alt) in text for alt in group) for group in gold["keywords"])
    forbidden = [w for w in gold.get("forbid", []) if norm_answer(w) in text]
    return {"keywords_ok": keywords_ok, "forbidden": forbidden, "drift": language_drift(output),
            "correct": keywords_ok and not forbidden}


# ── 묶음 ─────────────────────────────────────────────

SCORERS = {"t1": score_t1, "t2": score_t2, "t3": score_t3, "t4": score_t4}


def score(task: str, output: str, gold: object) -> dict:
    return SCORERS[task](output, gold)


def summarize(task: str, scores: list[dict]) -> dict:
    n = len(scores)
    out = {"items": n, "correct": sum(s["correct"] for s in scores)}
    if task == "t1":
        out["parsed"] = sum(s["parsed"] for s in scores)
        out["schema_ok"] = sum(s["schema_ok"] for s in scores)
    if task == "t3":
        out["fields_correct"] = sum(s["fields_correct"] for s in scores)
        out["fields_total"] = 4 * n
    if task == "t4":
        out["drift"] = sum(s["drift"] for s in scores)
    return out


def gold_as_output(task: str, item: dict) -> str:
    """정답을 모델 응답 모양으로 바꾼다 (채점기 자체 확인용)."""
    gold = item["gold"]
    if task in ("t1",):
        return json.dumps(gold, ensure_ascii=False)
    if task == "t2":
        return gold
    if task == "t3":
        return json.dumps({**gold, "place": gold["place"][0]}, ensure_ascii=False)
    return " ".join(group[0] for group in gold["keywords"]) + "입니다."


def selfcheck() -> dict[str, tuple[int, int]]:
    """정답을 그대로 넣으면 모두 맞아야 한다. 과제별 (맞음, 문항 수)."""
    out = {}
    for task in TASKS:
        items = load_items(task)
        out[task] = (sum(score(task, gold_as_output(task, it), it["gold"])["correct"] for it in items), len(items))
    return out


if __name__ == "__main__":
    for task, (ok, n) in selfcheck().items():
        print(f"{task}: {ok}/{n}")
