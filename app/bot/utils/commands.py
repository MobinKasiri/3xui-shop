import logging

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats

from app.bot.i18n import fa
from app.bot.utils.emoji import plain_alert_text

logger = logging.getLogger(__name__)


async def setup(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description=fa.CMD_START),
        BotCommand(command="buy", description=fa.CMD_BUY),
        BotCommand(command="configs", description=fa.CMD_CONFIGS),
        BotCommand(command="topup", description=fa.CMD_TOPUP),
    ]

    await bot.set_my_commands(
        commands=commands,
        scope=BotCommandScopeAllPrivateChats(),
    )
    logger.info("Bot commands configured successfully.")

    try:
        await bot.set_my_description(description=plain_alert_text(fa.BOT_DESCRIPTION))
        await bot.set_my_short_description(
            short_description=plain_alert_text(fa.BOT_SHORT_DESCRIPTION)
        )
        logger.info("Bot profile description updated.")
    except Exception as exc:
        logger.warning("Could not update bot description: %s", exc)


async def delete(bot: Bot) -> None:
    await bot.delete_my_commands(
        scope=BotCommandScopeAllPrivateChats(),
    )
    logger.info("Bot commands removed successfully.")
