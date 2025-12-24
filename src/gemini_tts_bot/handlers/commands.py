"""Slash command handlers for the bot"""

import io
import re

from telegram import BotCommand, BotCommandScopeChat, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


def escape_markdown_v1(text: str) -> str:
    """Escape Markdown V1 special characters to prevent Telegram BadRequest errors.

    Telegram Markdown V1 (parse_mode="Markdown") only uses:
    - *bold*
    - _italic_
    - [link](url)
    - `code`
    """
    # Only escape characters that have meaning in Markdown V1
    escape_chars = r"_*`["
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

from ..config import config_manager, is_allowed_chat, needs_commands_setup, mark_commands_set
from ..services.tts import tts_service
from ..services.audio import AudioConverter
from ..utils.voices import (
    VOICES,
    FEATURED_VOICES,
    get_voice_description,
    is_valid_voice,
    get_sample_path,
    PREVIEW_TEXT,
)

# Bot commands (same as in main.py)
_BOT_COMMANDS = [
    BotCommand("start", "Show welcome message and help"),
    BotCommand("voice", "Choose your default voice"),
    BotCommand("prompt", "Set custom TTS style"),
    BotCommand("reset", "Reset all settings to default"),
    BotCommand("help", "Show help message"),
]


async def _ensure_commands_set(bot, chat_id: int) -> None:
    """Ensure commands are set for this chat (called on first interaction)"""
    if needs_commands_setup(chat_id):
        try:
            await bot.set_my_commands(
                _BOT_COMMANDS,
                scope=BotCommandScopeChat(chat_id=chat_id),
            )
            mark_commands_set(chat_id)
        except Exception:
            pass  # Silently ignore errors


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    if not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    if not is_allowed_chat(chat_id):
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return

    # Ensure commands are set for this user (on first interaction)
    await _ensure_commands_set(context.bot, chat_id)

    welcome_text = """Welcome to Gemini TTS Bot!

Send me any text and I'll convert it to speech using Google's Gemini TTS.

**Features:**
- **Monologue**: Send plain text for single-voice narration
- **Dialogue**: Send text with speaker names (e.g., "Alice: Hello\\nBob: Hi!") for multi-voice conversation

**Commands:**
- /voice - Choose your default voice
- /prompt - Set custom TTS style (pace, tone, etc.)
- /reset - Reset all settings to default
- /help - Show this help message

**Current Settings:**
"""
    config = config_manager.get(chat_id)
    settings_text = f"- Voice: {config.default_voice}\n"
    if config.custom_prompt:
        # Escape markdown special characters in user-provided prompt
        escaped_prompt = escape_markdown_v1(config.custom_prompt)
        settings_text += f"- Custom Prompt: {escaped_prompt}\n"
    else:
        settings_text += "- Custom Prompt: (none)\n"

    await update.message.reply_text(
        welcome_text + settings_text,
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command"""
    await start_command(update, context)


async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /voice command - show voice selection menu"""
    if not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    if not is_allowed_chat(chat_id):
        return

    # Build inline keyboard with featured voices (2 per row)
    keyboard = []
    row = []
    for voice_name in FEATURED_VOICES:
        desc = get_voice_description(voice_name)
        button = InlineKeyboardButton(
            f"{voice_name}",
            callback_data=f"voice_preview:{voice_name}",
        )
        row.append(button)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    # Add "More voices" button
    keyboard.append([
        InlineKeyboardButton("More voices...", callback_data="voice_more"),
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    current_voice = config_manager.get(chat_id).default_voice
    await update.message.reply_text(
        f"**Select a voice to preview**\n\n"
        f"Current voice: {current_voice}\n\n"
        f"Tap a voice to hear a sample, then confirm to set as default.",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def voice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice selection callbacks"""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    chat_id = query.message.chat.id
    if not is_allowed_chat(chat_id):
        return

    data = query.data

    if data == "voice_more":
        # Show all voices
        keyboard = []
        row = []
        for voice_name in VOICES.keys():
            if voice_name not in FEATURED_VOICES:
                button = InlineKeyboardButton(
                    voice_name,
                    callback_data=f"voice_preview:{voice_name}",
                )
                row.append(button)
                if len(row) == 3:
                    keyboard.append(row)
                    row = []
        if row:
            keyboard.append(row)

        keyboard.append([
            InlineKeyboardButton("« Back", callback_data="voice_back"),
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "**All available voices**\n\nTap to preview:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    elif data == "voice_back":
        # Go back to featured voices
        # Delete the current message (may be a voice message that can't be edited)
        try:
            await query.delete_message()
        except Exception:
            pass

        keyboard = []
        row = []
        for voice_name in FEATURED_VOICES:
            button = InlineKeyboardButton(
                voice_name,
                callback_data=f"voice_preview:{voice_name}",
            )
            row.append(button)
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append([
            InlineKeyboardButton("More voices...", callback_data="voice_more"),
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)
        current_voice = config_manager.get(chat_id).default_voice
        await query.message.chat.send_message(
            f"**Select a voice to preview**\n\n"
            f"Current voice: {current_voice}\n\n"
            f"Tap a voice to hear a sample, then confirm to set as default.",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    elif data.startswith("voice_preview:"):
        voice_name = data.split(":", 1)[1]
        if not is_valid_voice(voice_name):
            await query.answer("Invalid voice", show_alert=True)
            return

        # Try to use pre-generated sample first
        sample_path = get_sample_path(voice_name)

        if sample_path:
            # Use local sample file with proper resource management
            with open(sample_path, "rb") as f:
                mp3_data = io.BytesIO(f.read())
        else:
            # Fallback: generate on the fly
            await query.edit_message_text(f"Generating preview for {voice_name}...")

            result = await tts_service.generate_monologue(PREVIEW_TEXT, voice_name)

            if not result.success:
                await query.edit_message_text(
                    f"Failed to generate preview: {result.error}\n\n"
                    "Please try again.",
                )
                return

            mp3_data = AudioConverter.pcm_to_mp3(result.audio_data)

        # Send audio with confirmation button
        keyboard = [[
            InlineKeyboardButton(
                f"✓ Use {voice_name}",
                callback_data=f"voice_set:{voice_name}",
            ),
            InlineKeyboardButton("« Back", callback_data="voice_back"),
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        desc = get_voice_description(voice_name)
        # Use voice message instead of audio to prevent Telegram's auto-play queue
        await query.message.reply_voice(
            voice=mp3_data,
            caption=f"**{voice_name}**\n{desc}",
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )

        await query.delete_message()

    elif data.startswith("voice_set:"):
        voice_name = data.split(":", 1)[1]
        if not is_valid_voice(voice_name):
            await query.answer("Invalid voice", show_alert=True)
            return

        config_manager.set_voice(chat_id, voice_name)
        await query.answer(f"Voice set to {voice_name}!")

        # Delete the voice message and send a text confirmation
        try:
            await query.delete_message()
        except Exception:
            pass

        await query.message.chat.send_message(
            f"✓ Voice set to **{voice_name}**",
            parse_mode="Markdown",
        )


async def prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /prompt command"""
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    if not is_allowed_chat(chat_id):
        return

    config = config_manager.get(chat_id)

    # Check if user provided a new prompt
    if context.args:
        new_prompt = " ".join(context.args)

        # Check for clear command
        if new_prompt.lower() in ("clear", "reset", "none", "off"):
            config_manager.set_prompt(chat_id, "")
            await update.message.reply_text(
                "Custom prompt cleared!",
                parse_mode="Markdown",
            )
            return

        config_manager.set_prompt(chat_id, new_prompt)
        # Escape markdown special characters in user-provided prompt
        escaped_prompt = escape_markdown_v1(new_prompt)
        await update.message.reply_text(
            f"Custom prompt updated!\n\n**New prompt:**\n{escaped_prompt}",
            parse_mode="Markdown",
        )
    else:
        # Show current prompt and usage
        if config.custom_prompt:
            # Escape markdown special characters in user-provided prompt
            current = escape_markdown_v1(config.custom_prompt)
        else:
            current = "(none)"

        await update.message.reply_text(
            f"**Custom TTS Prompt**\n\n"
            f"Current: {current}\n\n"
            f"**Usage:**\n"
            f"`/prompt <your instructions>`\n"
            f"`/prompt clear` - Remove custom prompt\n\n"
            f"**Examples:**\n"
            f"• `/prompt Speak slowly and clearly`\n"
            f"• `/prompt Use a warm, friendly tone`\n"
            f"• `/prompt Read with dramatic pauses`",
            parse_mode="Markdown",
        )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reset command"""
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    if not is_allowed_chat(chat_id):
        return

    config_manager.reset(chat_id)
    config = config_manager.get(chat_id)

    await update.message.reply_text(
        f"Settings have been reset to defaults!\n\n"
        f"**Current Settings:**\n"
        f"- Voice: {config.default_voice}\n"
        f"- Custom Prompt: (none)",
        parse_mode="Markdown",
    )
