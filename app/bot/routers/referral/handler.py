"""
Referral / "Free Config" landing (screenshots 12–13).

- With stats: full referral page including bonuses and counts.
- Without stats (no purchases yet): conversion-oriented landing with just the link.
- Share button (t.me/share/url) + "Ready post" button.
"""
from __future__ import annotations

import logging
from urllib.parse import quote

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from app.bot.utils.keyboards import K
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.bot.utils.persian import format_toman, to_persian_digits
from app.db.models import Referral, User

logger = logging.getLogger(__name__)

router = Router(name="referral")


def _ref_link(bot_username: str, ref_code: str) -> str:
    return f"https://t.me/{bot_username}?start=ref_{ref_code}"


def _referral_keyboard(ref_link: str) -> InlineKeyboardMarkup:
    share_text = quote(fa.REFERRAL_SHARE_DIALOG_TEXT, safe="")
    return (
        K()
        .success(
            fa.REFERRAL_SHARE_BTN,
            url=f"https://t.me/share/url?url={quote(ref_link, safe='')}&text={share_text}",
            icon="share",
        )
        .btn(fa.REFERRAL_POST_BTN, callback_data="ref:post", icon="note")
        .back_to_menu()
        .adjust(1)
        .as_markup()
    )


async def show_referral_landing(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    config = kwargs.get("config")
    bot_username = config.bot.USERNAME if config else (
        (await callback.bot.get_me()).username or "nc_vpn_bot"
    )
    ref_link = _ref_link(bot_username, user.referral_code)

    count, purchases, total_bonus = await Referral.stats_for_referrer(
        session, user.tg_id
    )

    if purchases > 0:
        ref_bonus = config.pricing.REFERRAL_BONUS_TOMAN if config else 0
        friend_bonus = config.pricing.REFERRAL_FRIEND_BONUS_TOMAN if config else 0
        text = fa.REFERRAL_WITH_STATS.format(
            ref_bonus=format_toman(ref_bonus),
            friend_bonus=format_toman(friend_bonus),
            count=to_persian_digits(count),
            purchases=to_persian_digits(purchases),
            total_revenue=format_toman(total_bonus),
            ref_link=ref_link,
        )
    else:
        text = fa.REFERRAL_NO_STATS.format(ref_link=ref_link)

    await callback.message.edit_text(
        text,
        reply_markup=_referral_keyboard(ref_link),
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data == "ref:post")
async def cb_ready_post(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    config = kwargs.get("config")
    bot_username = config.bot.USERNAME if config else (
        (await callback.bot.get_me()).username or "nc_vpn_bot"
    )
    ref_link = _ref_link(bot_username, user.referral_code)
    post = fa.REFERRAL_READY_POST.format(ref_link=ref_link)

    await callback.message.answer(
        post, parse_mode="HTML", disable_web_page_preview=True
    )
    await callback.message.answer(
        fa.REFERRAL_READY_POST_HINT,
        reply_markup=K().nav("menu:free").adjust(2).as_markup(),
    )
    await callback.answer()
