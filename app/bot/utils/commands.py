import logging

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats

from app.bot.i18n import fa

logger = logging.getLogger(__name__)


async def setup(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Main menu"),
        BotCommand(command="buy", description="Buy service"),
        BotCommand(command="configs", description="My configs"),
        BotCommand(command="topup", description="Increase amount"),
    ]

    await bot.set_my_commands(
        commands=commands,
        scope=BotCommandScopeAllPrivateChats(),
    )
    logger.info("Bot commands configured successfully.")

    try:
        await bot.set_my_description(description=fa.BOT_DESCRIPTION)
        await bot.set_my_short_description(short_description=fa.BOT_SHORT_DESCRIPTION)
        logger.info("Bot profile description updated.")
    except Exception as exc:
        logger.warning("Could not update bot description: %s", exc)


async def delete(bot: Bot) -> None:
    await bot.delete_my_commands(
        scope=BotCommandScopeAllPrivateChats(),
    )
    logger.info("Bot commands removed successfully.")
