"""Main entry point for Gemini TTS Telegram Bot"""

import logging
import sys

from telegram import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from .config import (
    TELEGRAM_BOT_TOKEN,
    ALLOWED_CHAT_IDS,
    validate_config,
    mark_commands_set,
)
from .handlers.commands import (
    start_command,
    help_command,
    voice_command,
    voice_callback,
    model_command,
    model_callback,
    prompt_command,
    reset_command,
)
from .handlers.text import text_handler

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Bot commands for authorized users
BOT_COMMANDS = [
    BotCommand("start", "Show welcome message and help"),
    BotCommand("voice", "Choose your default voice"),
    BotCommand("model", "Switch TTS model (flash/pro)"),
    BotCommand("prompt", "Set custom TTS style"),
    BotCommand("reset", "Reset all settings to default"),
    BotCommand("help", "Show help message"),
]


async def post_init(application: Application) -> None:
    """Set up bot commands after initialization"""
    bot = application.bot

    # Clear commands for everyone (default scope) - non-whitelisted users see nothing
    await bot.set_my_commands([], scope=BotCommandScopeDefault())
    logger.info("Cleared default command menu for non-whitelisted users")

    # Try to set commands for each allowed chat
    for chat_id in ALLOWED_CHAT_IDS:
        try:
            await bot.set_my_commands(
                BOT_COMMANDS,
                scope=BotCommandScopeChat(chat_id=chat_id),
            )
            mark_commands_set(chat_id)
            logger.info(f"Set commands for chat_id: {chat_id}")
        except Exception as e:
            # May fail if bot hasn't chatted with user yet - will be set on first message
            logger.debug(f"Could not set commands for chat_id {chat_id}: {e}")


async def setup_commands_for_chat(bot, chat_id: int) -> None:
    """Set up commands for a specific chat (called on first interaction)"""
    try:
        await bot.set_my_commands(
            BOT_COMMANDS,
            scope=BotCommandScopeChat(chat_id=chat_id),
        )
        mark_commands_set(chat_id)
        logger.info(f"Set commands for chat_id: {chat_id} (on first interaction)")
    except Exception as e:
        logger.warning(f"Failed to set commands for chat_id {chat_id}: {e}")


def main() -> None:
    """Start the bot"""
    # Validate configuration
    errors = validate_config()
    if errors:
        for error in errors:
            logger.error(error)
        logger.error("Please set the required environment variables in .env file")
        sys.exit(1)

    logger.info("Starting Gemini TTS Bot...")

    # Create application with post_init hook
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("voice", voice_command))
    application.add_handler(CommandHandler("model", model_command))
    application.add_handler(CommandHandler("prompt", prompt_command))
    application.add_handler(CommandHandler("reset", reset_command))

    # Register callback handlers for voice and model selection
    application.add_handler(CallbackQueryHandler(voice_callback, pattern=r"^voice_"))
    application.add_handler(CallbackQueryHandler(model_callback, pattern=r"^model_"))

    # Register text message handler (must be last)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
    )

    # Start polling
    logger.info("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
