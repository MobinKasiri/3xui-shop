"""Parse and verify mandatory Telegram channel membership."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import (
    ChatMemberAdministrator,
    ChatMemberMember,
    ChatMemberOwner,
    ChatMemberRestricted,
    InlineKeyboardMarkup,
)
from cachetools import TTLCache

from app.bot.i18n import fa
from app.bot.utils.keyboards import K

logger = logging.getLogger(__name__)

_MEMBER_STATUSES = frozenset({"creator", "administrator", "member", "restricted"})
_NOT_PARTICIPANT_HINTS = (
    "user not found",
    "user_not_participant",
    "not a member of",
    "participant_id_invalid",
)
_INACCESSIBLE_HINTS = (
    "member list is inaccessible",
    "chat_admin_required",
)
_resolved_chat_ids: dict[str, int] = {}
_bot_gate_capable: bool = False
# Skip repeated Telegram membership checks for recently verified users.
_gate_pass_cache: TTLCache[int, bool] = TTLCache(maxsize=10_000, ttl=120)


def mark_gate_passed(user_id: int) -> None:
    _gate_pass_cache[user_id] = True


def invalidate_gate_passed(user_id: int) -> None:
    _gate_pass_cache.pop(user_id, None)


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


def bot_gate_capable() -> bool:
    """True when the bot is channel admin and can call getChatMember."""
    return _bot_gate_capable


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
        kb.primary(channel.label, url=channel.url, icon="link")
    return kb.success(fa.CHANNEL_GATE_VERIFY_BTN, callback_data="channel:joined", icon="confirm").adjust(1).as_markup()


def _is_joined_member(member: object) -> bool:
    if isinstance(member, (ChatMemberOwner, ChatMemberAdministrator, ChatMemberMember)):
        return True
    if isinstance(member, ChatMemberRestricted):
        return member.is_member
    status = getattr(member, "status", None)
    if status is None:
        return False
    value = status.value if hasattr(status, "value") else str(status)
    return value in _MEMBER_STATUSES and value != "left"


def _bad_request_means_not_joined(exc: TelegramBadRequest) -> bool:
    msg = str(exc).lower()
    if any(hint in msg for hint in _INACCESSIBLE_HINTS):
        return False
    return any(hint in msg for hint in _NOT_PARTICIPANT_HINTS)


async def _resolve_chat_id(bot: Bot, channel: RequiredChannel) -> int | str:
    cached = _resolved_chat_ids.get(channel.chat_id)
    if cached is not None:
        return cached

    try:
        chat = await bot.get_chat(channel.chat_id)
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.warning(
            "Cannot resolve channel %s: %s — check REQUIRED_CHANNELS username.",
            channel.chat_id,
            exc,
        )
        return channel.chat_id

    _resolved_chat_ids[channel.chat_id] = chat.id
    return chat.id


async def _bot_can_check_channel(bot: Bot, channel: RequiredChannel) -> bool:
    """Return True when getChatMember works for this channel (bot is admin)."""
    me = await bot.get_me()
    chat_ref = await _resolve_chat_id(bot, channel)
    try:
        bot_member = await bot.get_chat_member(chat_ref, me.id)
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.error(
            "Channel gate CANNOT verify %s (%s): %s — "
            "add @%s as channel admin.",
            channel.label,
            channel.chat_id,
            exc,
            me.username,
        )
        return False

    if not _is_joined_member(bot_member):
        logger.error(
            "Channel gate: bot @%s is not admin in %s (%s).",
            me.username,
            channel.label,
            channel.chat_id,
        )
        return False

    logger.info(
        "Channel gate ready: %s (%s → %s)",
        channel.label,
        channel.chat_id,
        chat_ref,
    )
    return True


async def refresh_bot_gate_capability(
    bot: Bot, channels: tuple[RequiredChannel, ...]
) -> bool:
    """Re-check whether the bot can verify membership in every required channel."""
    global _bot_gate_capable

    if not channels:
        _bot_gate_capable = False
        return False

    capable = True
    for channel in channels:
        if not await _bot_can_check_channel(bot, channel):
            capable = False
    _bot_gate_capable = capable
    return capable


async def verify_gate_channels_at_startup(
    bot: Bot, channels: tuple[RequiredChannel, ...]
) -> None:
    """Log whether the bot can resolve each channel and read membership."""
    await refresh_bot_gate_capability(bot, channels)


async def audit_channels(
    bot: Bot, user_id: int, channels: tuple[RequiredChannel, ...]
) -> list[ChannelAudit]:
    audits: list[ChannelAudit] = []
    for channel in channels:
        chat_ref = await _resolve_chat_id(bot, channel)
        try:
            member = await bot.get_chat_member(chat_ref, user_id)
            result = (
                VerifyResult.JOINED
                if _is_joined_member(member)
                else VerifyResult.NOT_JOINED
            )
        except TelegramBadRequest as exc:
            if _bad_request_means_not_joined(exc):
                result = VerifyResult.NOT_JOINED
            else:
                logger.warning(
                    "Cannot verify %s (chat %s) for user %s: %s",
                    channel.chat_id,
                    chat_ref,
                    user_id,
                    exc,
                )
                result = VerifyResult.UNVERIFIABLE
        except TelegramForbiddenError as exc:
            logger.warning(
                "Forbidden verifying %s (chat %s) for user %s: %s",
                channel.chat_id,
                chat_ref,
                user_id,
                exc,
            )
            result = VerifyResult.UNVERIFIABLE
        except Exception as exc:
            logger.warning(
                "Channel check error for %s (chat %s): %s",
                channel.chat_id,
                chat_ref,
                exc,
            )
            result = VerifyResult.UNVERIFIABLE
        audits.append(ChannelAudit(channel=channel, result=result))
    return audits


async def audit_channels_live(
    bot: Bot, user_id: int, channels: tuple[RequiredChannel, ...]
) -> list[ChannelAudit]:
    """Verify membership; refresh bot capability first when checks were failing."""
    audits = await audit_channels(bot, user_id, channels)
    if is_membership_confirmed(audits):
        return audits

    if any(item.result == VerifyResult.UNVERIFIABLE for item in audits):
        if await refresh_bot_gate_capability(bot, channels):
            return await audit_channels(bot, user_id, channels)
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
    *,
    channel_gate_passed: bool = False,
) -> tuple[bool, list[RequiredChannel]]:
    """Return (show_gate, missing_verified_channels)."""
    if not channels:
        return False, []

    if channel_gate_passed and user_id in _gate_pass_cache:
        return False, []

    audits = await audit_channels_live(bot, user_id, channels)
    if is_membership_confirmed(audits):
        mark_gate_passed(user_id)
        return False, []

    missing = missing_joined_channels(audits)
    if missing:
        invalidate_gate_passed(user_id)
        return True, missing

    if not bot_gate_capable() and channel_gate_passed:
        logger.debug(
            "Channel gate: trusting stored pass for user %s (bot cannot verify)",
            user_id,
        )
        return False, []

    return True, []
