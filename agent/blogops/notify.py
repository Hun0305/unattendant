"""디스코드 알림 (docs/blogops.md 1·2절, architecture.md 알림).

봇 토큰으로 REST API에 메시지만 보낸다. Phase 1에는 상주하는 봇 프로세스가 없다.
    #일일요약  info   그날 한 일
    #긴급      warn·critical (critical은 운영자 멘션)
    #승인      승인 요청 (운영자 멘션, 승인·반려 명령 안내)
"""
from __future__ import annotations

import time
from pathlib import Path

from . import env, log
from .config import Config
from .httpjson import Transport, post_json
from .store import Store

API = "https://discord.com/api/v10"
CHANNEL_KEYS = {"urgent": "DISCORD_CH_URGENT", "approval": "DISCORD_CH_APPROVAL", "daily": "DISCORD_CH_DAILY"}
LEVELS = {"info": ("daily", ""), "warn": ("urgent", "**주의** "), "critical": ("urgent", "**긴급** ")}
MAX_LEN = 2000  # 디스코드 메시지 한도
# 디스코드는 봇 요청에 이 형식의 User-Agent를 요구한다 (없으면 Cloudflare가 막는다)
USER_AGENT = "DiscordBot (https://unattendant.dev, 0.1) Huninn-blogops"


class NotifyError(Exception):
    pass


def send(config: Config, channel: str, content: str, mention_owner: bool = False,
         transport: Transport | None = None) -> dict:
    if channel not in CHANNEL_KEYS:
        raise NotifyError(f"채널은 {', '.join(CHANNEL_KEYS)} 중 하나다: {channel!r}")
    token = env.get(config, "DISCORD_BOT_TOKEN")
    channel_id = env.get(config, CHANNEL_KEYS[channel])
    owner = env.get(config, "DISCORD_OWNER_ID") if mention_owner else None
    text = (f"<@{owner}> " if owner else "") + content
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN - 1] + "…"
    payload = {"content": text, "allowed_mentions": {"parse": [], "users": [owner] if owner else []}}
    headers = {"Authorization": f"Bot {token}", "User-Agent": USER_AGENT}
    url = f"{API}/channels/{channel_id}/messages"
    for attempt in range(2):
        status, body = (transport or post_json)(url, headers, payload)
        if status == 429 and attempt == 0:  # 속도 제한이면 알려준 시간만큼 기다렸다 한 번 더
            time.sleep(min(float(body.get("retry_after", 1)), 10))
            continue
        break
    if status not in (200, 201):
        raise NotifyError(f"디스코드로 보내지 못했다: HTTP {status} {body.get('message', '')}".strip())
    log.append(config, "notify", "huninn", channel=channel, chars=len(text), message_id=body.get("id"))
    return {"channel": channel, "message_id": body.get("id")}


def notify_human(config: Config, level: str, message: str, transport: Transport | None = None) -> dict:
    if level not in LEVELS:
        raise NotifyError(f"수준은 {', '.join(LEVELS)} 중 하나다: {level!r}")
    channel, prefix = LEVELS[level]
    return send(config, channel, prefix + message.strip(), mention_owner=(level == "critical"), transport=transport)


def approval_message(config: Config, store: Store, draft_id: str) -> str:
    s = store.summary(draft_id)
    review = str(config.root / "ops" / "huninn" / "review").replace(str(Path.home()), "~", 1)
    rejected = f"\n지난 반려 사유: {s['last_rejection']['reason']}" if s["last_rejection"] else ""
    return (f"**승인 요청: {s['title']}**\n"
            f"{s['description']}\n"
            f"시리즈 `{s['series']}` · 언어 {', '.join(s['langs'])} · 초안 `{draft_id}` · 해시 `{s['hash'][:12]}` · 품질 검사 통과"
            f"{rejected}\n"
            f"읽기 `{review} show {draft_id} --body`\n"
            f"승인 `{review} approve {draft_id}`\n"
            f"반려 `{review} reject {draft_id} \"사유\"`\n"
            f"승인하면 다음 사이클(매일 14:00)에서 발행된다.")


def request_approval(config: Config, store: Store, draft_id: str, transport: Transport | None = None) -> dict:
    # 기록을 먼저 남긴다. 상태나 대기 한도에 걸리면 디스코드로 보내지 않는다
    record = store.record_approval_request(draft_id)
    warnings = []
    message_id = None
    try:
        message_id = send(config, "approval", approval_message(config, store, draft_id),
                          mention_owner=True, transport=transport)["message_id"]
    except (NotifyError, env.EnvError) as e:
        warnings.append(f"승인 요청을 디스코드로 보내지 못했다: {e}")
    log.append(config, "request_approval", "huninn", draft_id=draft_id, hash=record["hash"],
               sent=message_id is not None)
    return {"draft_id": draft_id, "hash": record["hash"], "message_id": message_id, "warnings": warnings}
