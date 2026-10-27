"""디스코드 알림 (docs/blogops.md 1·2·11절, architecture.md 알림).

봇 토큰으로 REST API에 메시지를 보낸다. 이 모듈은 상주하지 않는다.
    #일일요약  info   그날 한 일
    #긴급      warn·critical (critical은 운영자 멘션)
    #승인      승인 요청 (운영자 멘션, 미리보기 링크와 승인·반려·접기 버튼)
버튼을 받는 쪽은 상주하는 봇(bot.py)이다. 봇이 멈춰도 알림은 가고, review 명령으로 승인할 수 있다(메시지에는 적지 않는다).
"""
from __future__ import annotations

import difflib
import subprocess
import time
from pathlib import Path

from . import buttons, env, frontmatter, log, preview
from .config import Config
from .httpjson import Transport, patch_json, post_json
from .store import Store, StoreError

API = "https://discord.com/api/v10"
CHANNEL_KEYS = {"urgent": "DISCORD_CH_URGENT", "approval": "DISCORD_CH_APPROVAL", "daily": "DISCORD_CH_DAILY"}
LEVELS = {"info": ("daily", ""), "warn": ("urgent", "**주의** "), "critical": ("urgent", "**긴급** ")}
MAX_LEN = 2000  # 디스코드 메시지 한도
# 디스코드는 봇 요청에 이 형식의 User-Agent를 요구한다 (없으면 Cloudflare가 막는다)
USER_AGENT = "DiscordBot (https://unattendant.dev, 0.1) Huninn-blogops"


class NotifyError(Exception):
    pass


def _headers(config: Config) -> dict:
    return {"Authorization": f"Bot {env.get(config, 'DISCORD_BOT_TOKEN')}", "User-Agent": USER_AGENT}


def send(config: Config, channel: str, content: str, mention_owner: bool = False,
         transport: Transport | None = None, components: list[dict] | None = None) -> dict:
    if channel not in CHANNEL_KEYS:
        raise NotifyError(f"채널은 {', '.join(CHANNEL_KEYS)} 중 하나다: {channel!r}")
    headers = _headers(config)
    channel_id = env.get(config, CHANNEL_KEYS[channel])
    owner = env.get(config, "DISCORD_OWNER_ID") if mention_owner else None
    text = (f"<@{owner}> " if owner else "") + content
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN - 1] + "…"
    payload = {"content": text, "allowed_mentions": {"parse": [], "users": [owner] if owner else []}}
    if components:
        payload["components"] = components
    url = f"{API}/channels/{channel_id}/messages"
    for attempt in range(2):
        status, body = (transport or post_json)(url, headers, payload)
        if status == 429 and attempt == 0:  # 속도 제한이면 알려준 시간만큼 기다렸다 한 번 더
            time.sleep(min(float(body.get("retry_after", 1)), 10))
            continue
        break
    if status not in (200, 201):
        raise NotifyError(f"디스코드로 보내지 못했다: HTTP {status} {body.get('message', '')}".strip())
    log.append(config, "notify", "huninn", channel=channel, chars=len(text), message_id=body.get("id"),
               buttons=bool(components))
    return {"channel": channel, "channel_id": channel_id, "message_id": body.get("id")}


def notify_human(config: Config, level: str, message: str, transport: Transport | None = None) -> dict:
    if level not in LEVELS:
        raise NotifyError(f"수준은 {', '.join(LEVELS)} 중 하나다: {level!r}")
    channel, prefix = LEVELS[level]
    return send(config, channel, prefix + message.strip(), mention_owner=(level == "critical"), transport=transport)


def changes_since(store: Store, draft_id: str, base_hash: str) -> str | None:
    """base_hash 판(보통 지난 반려 판)에서 지금 판까지 한국어판이 무엇이 바뀌었는지 한 줄로.
    제목만 고치고 본문은 그대로 다시 올리는 일(2026-10-16 로그)을 승인 요청에서 바로 보이게 한다.
    이전 판이 남아 있지 않으면(보관은 2026-10-27부터) None."""
    old_text = store.version_text(draft_id, base_hash, "ko")
    new_text = store.version_text(draft_id, store.content_hash(draft_id), "ko")
    if old_text is None or new_text is None:
        return None
    try:
        (old_fields, old_body), (new_fields, new_body) = frontmatter.parse(old_text), frontmatter.parse(new_text)
    except ValueError:
        return None
    fields = [name for key, name in (("title", "제목"), ("description", "설명"), ("tags", "태그"), ("sources", "출처"))
              if old_fields.get(key) != new_fields.get(key)]
    added = removed = 0
    for line in difflib.ndiff(old_body.splitlines(), new_body.splitlines()):
        added += line.startswith("+ ")
        removed += line.startswith("- ")
    body = f"본문 +{added} −{removed}줄" if added or removed else "본문은 그대로"
    return ", ".join([*fields, body])


def approval_message(config: Config, store: Store, draft_id: str, preview_ok: bool = True) -> str:
    s = store.summary(draft_id)
    review = str(config.root / "ops" / "huninn" / "review").replace(str(Path.home()), "~", 1)
    rejected = ""
    if s["last_rejection"]:
        rejected = f"\n지난 반려 사유: {s['last_rejection']['reason']}"
        changed = changes_since(store, draft_id, s["last_rejection"]["hash"])
        if changed:
            rejected += f"\n반려 뒤 바뀐 것: {changed}"
    guide = ("[미리보기]로 발행된 모습 그대로 읽고, 버튼으로 승인·반려한다. 접기는 이 글감을 접는다(반려 + 보류)."
             if preview_ok else
             f"미리보기를 만들지 못했다. Pi에서 `{review} preview {draft_id}`로 다시 만들거나 "
             f"`{review} show {draft_id} --body`로 읽는다.")
    return (f"**승인 요청: {s['title']}**\n"
            f"{s['description']}\n"
            f"시리즈 `{s['series']}` · 언어 {', '.join(s['langs'])} · 초안 `{draft_id}` · 해시 `{s['hash'][:12]}` · 품질 검사 통과"
            f"{rejected}\n"
            f"{guide}\n"
            f"승인하면 다음 사이클(매일 14:00)에서 발행된다.")


def request_approval(config: Config, store: Store, draft_id: str, transport: Transport | None = None,
                     previewer=None) -> dict:
    # 기록을 먼저 남긴다. 상태나 대기 한도에 걸리면 디스코드로 보내지 않는다
    record = store.record_approval_request(draft_id)
    warnings = []
    made = None
    try:
        made = (previewer or preview.ensure)(config, store, draft_id)
    except (preview.PreviewError, StoreError, OSError, subprocess.SubprocessError) as e:
        # 미리보기가 안 돼도 승인 요청은 간다. 읽는 길은 review 명령이 남아 있다
        warnings.append(f"미리보기를 만들지 못했다: {e}")
    components = buttons.approval_components(draft_id, record["hash"], made["urls"] if made else None)
    message_id = None
    try:
        sent = send(config, "approval", approval_message(config, store, draft_id, preview_ok=made is not None),
                    mention_owner=True, transport=transport, components=components)
        message_id = sent["message_id"]
        if message_id:  # 결정이 나면 이 메시지의 버튼을 걷어내려고 위치를 적어 둔다
            store.record_approval_message(draft_id, record["hash"], sent["channel_id"], message_id)
    except (NotifyError, env.EnvError, StoreError, OSError) as e:
        warnings.append(f"승인 요청을 디스코드로 보내지 못했다: {e}")
    log.append(config, "request_approval", "huninn", draft_id=draft_id, hash=record["hash"],
               sent=message_id is not None, preview=made is not None)
    # 미리보기 주소(토큰이 든 열쇠)는 Huninn에게 돌려주지 않는다. 디스코드 #승인으로만 간다
    return {"draft_id": draft_id, "hash": record["hash"], "message_id": message_id,
            "preview": made is not None, "warnings": warnings}


def close_approval_message(config: Config, store: Store, draft_id: str, content_hash: str, text: str,
                           transport: Transport | None = None) -> bool:
    """결정이 난 승인 요청 메시지를 결과 한 덩이로 바꾸고 버튼과 링크를 걷어낸다.
    승인 요청을 디스코드로 보낸 적이 없으면 아무것도 하지 않고 False."""
    ref = store.approval_message_ref(draft_id, content_hash)
    if not ref:
        return False
    url = f"{API}/channels/{ref['channel_id']}/messages/{ref['message_id']}"
    payload = {"content": text[:MAX_LEN], "components": [], "allowed_mentions": {"parse": []}}
    status, body = (transport or patch_json)(url, _headers(config), payload)
    if status != 200:
        raise NotifyError(f"승인 요청 메시지를 고치지 못했다: HTTP {status} {body.get('message', '')}".strip())
    log.append(config, "close_approval_message", "bot", draft_id=draft_id, message_id=ref["message_id"])
    return True
