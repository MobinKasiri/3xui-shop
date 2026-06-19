"""Parse and verify mandatory Telegram channel membership."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger(__name__)

_MEMBER_STATUSES = frozenset({"creator", "administrator", "member", "restricted"})


@dataclass(frozen=True)
class RequiredChannel:
    chat_id: str
    label: str
    url: str


def parse_required_channels(raw: str) -> tuple[RequiredChannel, ...]:
    """Parse REQUIRED_CHANNELS env value.

    Formats:
      @channel1,@channel2
      Nexora News|@nexoranode,VIP|https://t.me/nexora_vip
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
    builder = InlineKeyboardBuilder()
    for channel in channels:
        builder.button(text=channel.label, url=channel.url)
    builder.button(text="✅ عضو شدم", callback_data="channel:joined")
    builder.adjust(1)
    return builder.as_markup()


async def missing_channels(
    bot: Bot, user_id: int, channels: tuple[RequiredChannel, ...]
) -> list[RequiredChannel]:
    """Return channels the user has not joined yet."""
    missing: list[RequiredChannel] = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(channel.chat_id, user_id)
            if member.status not in _MEMBER_STATUSES:
                missing.append(channel)
        except TelegramBadRequest as exc:
            # Bot cannot verify (not admin in channel, wrong @name, etc.) —
            # do not block all users because of a config mistake.
            logger.warning(
                "Skipping channel %s — bot cannot verify membership: %s. "
                "Add the bot as admin in the channel or fix REQUIRED_CHANNELS.",
                channel.chat_id,
                exc,
            )
        except Exception as exc:
            logger.warning("Channel check failed for %s: %s", channel.chat_id, exc)
    return missing


async def user_joined_all(
    bot: Bot, user_id: int, channels: tuple[RequiredChannel, ...]
) -> bool:
    if not channels:
        return True
    return not await missing_channels(bot, user_id, channels)
