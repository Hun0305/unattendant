"""디스코드 봇 (docs/blogops.md 11절). #승인 메시지의 승인·반려·접기 버튼을 받는다.

    python -m blogops.bot            상주 (systemd huninn-bot.service)
    python -m blogops.bot --check    디스코드에 접속만 해 보고 끝낸다 (설치 확인)

- 디스코드로 먼저 연결을 여는 방식(게이트웨이)이라 포트포워딩이 필요 없다. 권한 인텐트도 쓰지 않는다
- 하는 일은 운영자의 버튼 클릭을 blogops.decisions에 넘기는 것뿐이다. 글을 쓰거나 발행하지 않는다
- 지키는 것
    · 운영자(DISCORD_OWNER_ID)가 아니면 거부한다 (버튼, 확인, 사유 입력창 모두)
    · 버튼에 든 해시가 초안의 지금 해시와 다르면 거부한다. 오래된 메시지로 새 내용을 승인하지 못한다
    · 승인은 한 번 더 확인한다 (폰에서 잘못 누르는 것을 막는다)
    · 승인·반려 기록은 review 명령과 같다 (decisions.py). 어디서 했는지만 via=discord로 남는다
- 봇이 멈추면 버튼이 안 먹을 뿐이다. 알림은 계속 가고 review 명령으로 승인할 수 있다
- discord.py는 선택 의존성이다 (pip install -e ".[bot]"). 이 파일 밖의 코드는 discord.py가 없어도 돈다
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Optional

import discord
from discord import ui

from . import buttons, decisions, env, log, preview
from .config import Config
from .env import EnvError
from .store import Store, StoreError

# 음성 기능은 쓰지 않는다. 시작할 때마다 나오는 PyNaCl·davey 경고를 끈다
discord.VoiceClient.warn_nacl = False
discord.VoiceClient.warn_dave = False

_log = logging.getLogger("blogops.bot")
SWEEP_SECONDS = 600
REASON_MAX = 500


class ApprovalButton(ui.DynamicItem[ui.Button], template=buttons.CUSTOM_ID_TEMPLATE):
    """custom_id에 동작·초안·해시가 들어 있어서, 봇이 다시 떠도 이전 메시지의 버튼이 그대로 동작한다."""

    def __init__(self, action: str, draft_id: str, hash12: str):
        super().__init__(ui.Button(label=buttons.LABELS[action], style=discord.ButtonStyle(buttons.STYLES[action]),
                                   custom_id=buttons.custom_id(action, draft_id, hash12)))
        self.action, self.draft_id, self.hash12 = action, draft_id, hash12

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: ui.Button, match, /):
        return cls(match["action"], match["draft"], match["hash"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.client.on_button(interaction, self.action, self.draft_id, self.hash12)


class ReasonModal(ui.Modal):
    """반려·접기 사유 입력창. Huninn이 이 사유를 읽고 고치거나, 글감을 접는 이유로 남는다."""

    reason = ui.Label(text="사유", component=ui.TextInput(style=discord.TextStyle.paragraph, min_length=2,
                                                          max_length=REASON_MAX, required=True))

    def __init__(self, bot: "HuninnBot", action: str, draft_id: str, hash12: str):
        super().__init__(title="반려 사유" if action == "reject" else "글감 접기", timeout=900)
        self.bot, self.action, self.draft_id, self.hash12 = bot, action, draft_id, hash12
        self.reason.text = "Huninn이 읽고 고칠 사유" if action == "reject" else "이 글감을 접는 이유"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.bot.on_reason(interaction, self.action, self.draft_id, self.hash12, self.reason.component.value)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await self.bot.report_error(interaction, error)


class HuninnBot(discord.Client):
    def __init__(self, config: Config, check_only: bool = False):
        super().__init__(intents=discord.Intents(guilds=True))  # 권한 인텐트 없이 버튼 클릭(interaction)만 받는다
        self.config = config
        self.store = Store(config)
        self.owner_id = env.get(config, "DISCORD_OWNER_ID")
        self.check_only = check_only
        self._sweeper: Optional[asyncio.Task] = None

    async def setup_hook(self) -> None:
        self.add_dynamic_items(ApprovalButton)
        if not self.check_only:
            self._sweeper = asyncio.create_task(self._sweep_previews())

    async def on_ready(self) -> None:
        _log.info("접속했다: %s", self.user)
        if self.check_only:
            print(f"접속 성공: {self.user}")
            await self.close()
            return
        await asyncio.to_thread(log.append, self.config, "bot_ready", "bot")

    async def _sweep_previews(self) -> None:
        # 결정이 나면 바로 지우지만, 재시작 등으로 남은 폴더를 가끔 훑는다
        while True:
            try:
                removed = await asyncio.to_thread(preview.cleanup, self.config, self.store)
                if removed:
                    _log.info("미리보기 %d개를 지웠다", len(removed))
            except Exception:
                _log.exception("미리보기 정리 실패")
            await asyncio.sleep(SWEEP_SECONDS)

    # ── 공통 ──────────────────────────────────────────────

    async def _owner_only(self, interaction: discord.Interaction, what: str) -> bool:
        if str(interaction.user.id) == self.owner_id:
            return True
        await asyncio.to_thread(log.append, self.config, "approval_denied", "bot", what=what)
        await interaction.response.send_message("운영자만 누를 수 있다.", ephemeral=True)
        return False

    async def report_error(self, interaction: discord.Interaction, error: Exception) -> None:
        _log.error("버튼 처리 중 오류", exc_info=error)
        text = f"처리하지 못했다: {type(error).__name__}. Pi에서 `review` 명령으로 처리해라."
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)

    # ── 버튼 ──────────────────────────────────────────────

    async def on_button(self, interaction: discord.Interaction, action: str, draft_id: str, hash12: str) -> None:
        try:
            if not await self._owner_only(interaction, action):
                return
            if action == "no":
                await interaction.response.edit_message(content="취소했다.", view=None)
                return
            try:
                summary = await asyncio.to_thread(decisions.preflight, self.store, draft_id, hash12)
            except StoreError as e:
                await interaction.response.send_message(f"처리할 수 없다: {e}", ephemeral=True)
                return
            if action == "approve":
                view = ui.View(timeout=None)
                view.add_item(ApprovalButton("yes", draft_id, hash12))
                view.add_item(ApprovalButton("no", draft_id, hash12))
                await interaction.response.send_message(
                    f"**{summary['title']}**\n해시 `{hash12}`을(를) 승인할까? 미리보기에서 읽은 그 버전이다. "
                    f"승인하면 다음 사이클(매일 14:00)에서 발행된다.", view=view, ephemeral=True)
            elif action in ("reject", "drop"):
                await interaction.response.send_modal(ReasonModal(self, action, draft_id, hash12))
            elif action == "yes":
                decision = await asyncio.to_thread(decisions.approve, self.config, self.store, draft_id,
                                                   expect_hash=hash12, via="discord")
                await interaction.response.edit_message(content=f"승인했다: {summary['title']}", view=None)
                await self._finish(interaction, decision)
        except StoreError as e:  # preflight 뒤에 상태가 바뀐 경우 (확인 창을 오래 둔 뒤 등)
            await self._reply(interaction, f"처리할 수 없다: {e}")
        except Exception as e:
            await self.report_error(interaction, e)

    async def on_reason(self, interaction: discord.Interaction, action: str, draft_id: str, hash12: str,
                        reason: str) -> None:
        if not await self._owner_only(interaction, action):
            return
        try:
            decision = await asyncio.to_thread(decisions.reject, self.config, self.store, draft_id, reason,
                                               drop=(action == "drop"), expect_hash=hash12, via="discord")
        except StoreError as e:
            await interaction.response.send_message(f"처리할 수 없다: {e}", ephemeral=True)
            return
        next_step = decisions.NEXT_STEP[decision.kind]
        await interaction.response.send_message(f"{decisions.HEADS[decision.kind]}\n{next_step}", ephemeral=True)
        await self._finish(interaction, decision)

    async def _finish(self, interaction: discord.Interaction, decision: decisions.Decision) -> None:
        # 응답을 먼저 했으니 여기서 걸리는 시간은 3초 제한과 상관없다
        warnings = await asyncio.to_thread(decisions.finish, self.config, self.store, decision)
        if warnings:
            await interaction.followup.send("\n".join(f"주의: {w}" for w in warnings), ephemeral=True)

    @staticmethod
    async def _reply(interaction: discord.Interaction, text: str) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="blogops.bot", description="Huninn 디스코드 승인 버튼 봇")
    parser.add_argument("--check", action="store_true", help="접속만 해 보고 끝낸다")
    args = parser.parse_args(argv)
    config = Config.from_env()
    try:
        token = env.get(config, "DISCORD_BOT_TOKEN")
        bot = HuninnBot(config, check_only=args.check)
    except EnvError as e:
        print(f"bot: {e}", file=sys.stderr)
        return 2
    # root_logger=True: blogops.* 로거도 같은 형식으로 journal에 나온다 (기본은 discord 로거만 설정한다)
    bot.run(token, log_level=logging.INFO, root_logger=True)  # 토큰은 출력하지 않는다
    return 0


if __name__ == "__main__":
    sys.exit(main())
