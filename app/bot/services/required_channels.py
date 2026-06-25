"""Parse and verify mandatory Telegram channel membership."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup

from app.bot.i18n import fa
from app.bot.utils.keyboards import K

logger = logging.getLogger(__name__)

_MEMBER_STATUSES = frozenset({"creator", "administrator", "member", "restricted"})


class VerifyResult(Enum):
    JOINED = "joined"
    NOT_JOINED = "not_joined"
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True)
class RequiredChannel:
    chat_id: str
    label: str
    url: str


@dataclass(frozen=True)
class ChannelAudit:
    channel: RequiredChannel
    result: VerifyResult


def parse_required_channels(raw: str) -> tuple[RequiredChannel, ...]:
    """Parse REQUIRED_CHANNELS env value.

    Formats:
      @channel1,@channel2
      Nexora|@nexoranode,Movies|https://t.me/nexora_movies
    """
    if not raw.strip():
        return ()

    channels: list[RequiredChannel] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue

        if "|" in part:
            label, ident = part.split("|", 1)
            label = label.strip()
            ident = ident.strip()
        else:
            ident = part
            label = ident.lstrip("@")

        ident = ident.replace("https://t.me/", "").replace("http://t.me/", "")
        ident = ident.strip("/")
        if not ident.startswith("@"):
            ident = f"@{ident}"

        channels.append(
            RequiredChannel(
                chat_id=ident,
                label=label or ident.lstrip("@"),
                url=f"https://t.me/{ident.lstrip('@')}",
            )
        )
    return tuple(channels)


def channel_gate_keyboard(channels: tuple[RequiredChannel, ...]) -> InlineKeyboardMarkup:
    kb = K()
    for channel in channels:
        kb.primary(channel.label, url=channel.url)
    return kb.success(fa.CHANNEL_GATE_VERIFY_BTN, callback_data="channel:joined", icon="confirm").adjust(1).as_markup()


async def audit_channels(
    bot: Bot, user_id: int, channels: tuple[RequiredChannel, ...]
) -> list[ChannelAudit]:
    audits: list[ChannelAudit] = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(channel.chat_id, user_id)
            result = (
                VerifyResult.JOINED
                if member.status in _MEMBER_STATUSES
                else VerifyResult.NOT_JOINED
            )
        except TelegramBadRequest as exc:
            logger.warning(
                "Cannot verify %s for user %s: %s — add bot as channel admin.",
                channel.chat_id,
                user_id,
                exc,
            )
            result = VerifyResult.UNVERIFIABLE
        except Exception as exc:
            logger.warning("Channel check error for %s: %s", channel.chat_id, exc)
            result = VerifyResult.UNVERIFIABLE
        audits.append(ChannelAudit(channel=channel, result=result))
    return audits


def missing_joined_channels(audits: list[ChannelAudit]) -> list[RequiredChannel]:
    """Channels the user has definitely not joined (bot could verify)."""
    return [
        item.channel
        for item in audits
        if item.result == VerifyResult.NOT_JOINED
    ]


def is_membership_confirmed(audits: list[ChannelAudit]) -> bool:
    """True only when every required channel is verified JOINED."""
    return bool(audits) and all(item.result == VerifyResult.JOINED for item in audits)


async def should_block_for_channels(
    bot: Bot,
    user_id: int,
    channels: tuple[RequiredChannel, ...],
) -> tuple[bool, list[RequiredChannel]]:
    """Return (show_gate, missing_verified_channels).

    Always verifies live membership — ignores any stored gate flag.
    Users pass only when the bot confirms JOINED on every required channel.
    """
    if not channels:
        return False, []

    audits = await audit_channels(bot, user_id, channels)
    if is_membership_confirmed(audits):
        return False, []

    return True, missing_joined_channels(audits)
