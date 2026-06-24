"""
Referral / "Free Config" landing (screenshots 12–13).

- With stats: full referral page including bonuses and counts.
- Without stats (no purchases yet): conversion-oriented landing with just the link.
- Share button (t.me/share/url) + "Ready post" button.
"""
from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import quote

from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup
from app.bot.utils.keyboards import K
from app.bot.utils.referral_post import resolve_referral_image
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import fa
from app.bot.services.referral_settings import referral_settings_for_config
from app.bot.utils.emoji import plain_share_text
from app.bot.utils.persian import format_toman, to_persian_digits
from app.db.models import Referral, User

logger = logging.getLogger(__name__)

router = Router(name="referral")


def _ref_link(bot_username: str, ref_code: str) -> str:
    return f"https://t.me/{bot_username}?start=ref_{ref_code}"


def _referral_keyboard(ref_link: str, share_text: str) -> InlineKeyboardMarkup:
    return (
        K()
        .success(
            fa.REFERRAL_SHARE_BTN,
            url=f"https://t.me/share/url?url={quote(ref_link, safe='')}&text={quote(share_text, safe='')}",
            icon="share",
        )
        .btn(fa.REFERRAL_POST_BTN, callback_data="ref:post", icon="note")
        .back_to_menu()
        .adjust(1)
        .as_markup()
    )


def _data_dir(config) -> Path | None:
    if config and getattr(config, "pricing", None):
        pf = getattr(config.pricing, "plans_file", None)
        if pf is not None:
            return Path(pf).parent
    return None


async def show_referral_landing(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    config = kwargs.get("config")
    settings = referral_settings_for_config(config)
    bot_username = config.bot.USERNAME if config else (
        (await callback.bot.get_me()).username or "nc_vpn_bot"
    )
    ref_link = _ref_link(bot_username, user.referral_code)
    friend_gift = settings.friend_gift_label()
    ref_bonus = format_toman(settings.referrer_bonus_toman)

    count, purchases, total_bonus = await Referral.stats_for_referrer(
        session, user.tg_id
    )

    if purchases > 0:
        text = settings.text(
            "landing_with_stats",
            ref_bonus=ref_bonus,
            friend_gift=friend_gift,
            count=to_persian_digits(count),
            purchases=to_persian_digits(purchases),
            total_revenue=format_toman(total_bonus),
            ref_link=ref_link,
        )
    else:
        text = settings.text(
            "landing_no_stats",
            ref_bonus=ref_bonus,
            friend_gift=friend_gift,
            ref_link=ref_link,
        )

    markup = _referral_keyboard(ref_link, plain_share_text(settings.text("share_dialog")))
    data_dir = _data_dir(config)
    landing_image = resolve_referral_image(
        settings.image_name("landing"),
        data_dir=data_dir,
        explicit=config.bot.REFERRAL_POST_IMAGE if config else None,
    )

    if landing_image:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(
            photo=FSInputFile(landing_image),
            caption=text,
            reply_markup=markup,
            parse_mode="HTML",
        )
    else:
        await callback.message.edit_text(
            text,
            reply_markup=markup,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    await callback.answer()


@router.callback_query(F.data == "ref:post")
async def cb_ready_post(
    callback: CallbackQuery, user: User, session: AsyncSession, **kwargs
) -> None:
    config = kwargs.get("config")
    settings = referral_settings_for_config(config)
    bot_username = config.bot.USERNAME if config else (
        (await callback.bot.get_me()).username or "nc_vpn_bot"
    )
    ref_link = _ref_link(bot_username, user.referral_code)
    post = settings.text(
        "ready_post",
        ref_link=ref_link,
        friend_gift=settings.friend_gift_label(),
    )

    data_dir = _data_dir(config)
    image_path = resolve_referral_image(
        settings.image_name("ready_post"),
        data_dir=data_dir,
        explicit=config.bot.REFERRAL_POST_IMAGE if config else None,
    )

    if image_path:
        await callback.message.answer_photo(
            photo=FSInputFile(image_path),
            caption=post,
            parse_mode="HTML",
        )
        hint = fa.REFERRAL_READY_POST_HINT_WITH_IMAGE
    else:
        await callback.message.answer(
            post, parse_mode="HTML", disable_web_page_preview=True
        )
        hint = fa.REFERRAL_READY_POST_HINT

    await callback.message.answer(
        hint,
        reply_markup=K().nav("menu:free").adjust(2).as_markup(),
    )
    await callback.answer()
