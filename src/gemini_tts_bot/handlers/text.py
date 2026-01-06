"""Text message handler for TTS conversion"""

import time
from collections import defaultdict
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from ..config import config_manager, is_allowed_chat, MAX_TEXT_LENGTH
from ..services.tts import tts_service
from ..services.analyzer import dialogue_analyzer
from ..services.audio import AudioConverter
from .commands import _ensure_commands_set

# Rate limiting: max requests per user per minute
RATE_LIMIT_REQUESTS = 5
RATE_LIMIT_WINDOW = 60  # seconds

# Track user request timestamps for rate limiting
_user_requests: dict[int, list[float]] = defaultdict(list)


def _check_rate_limit(chat_id: int) -> bool:
    """Check if user is within rate limit. Returns True if allowed."""
    now = time.time()
    # Clean old entries
    _user_requests[chat_id] = [
        ts for ts in _user_requests[chat_id]
        if now - ts < RATE_LIMIT_WINDOW
    ]
    # Check limit
    if len(_user_requests[chat_id]) >= RATE_LIMIT_REQUESTS:
        return False
    _user_requests[chat_id].append(now)
    return True


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages - convert to speech"""
    if not update.effective_chat or not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    if not is_allowed_chat(chat_id):
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        return

    # Rate limiting check
    if not _check_rate_limit(chat_id):
        await update.message.reply_text(
            f"Rate limit exceeded. Please wait before sending more requests.\n"
            f"(Maximum {RATE_LIMIT_REQUESTS} requests per minute)"
        )
        return

    # Ensure commands are set for this user (on first interaction)
    await _ensure_commands_set(context.bot, chat_id)

    text = update.message.text.strip()
    if not text:
        return

    # Validate text length
    if len(text) > MAX_TEXT_LENGTH:
        await update.message.reply_text(
            f"Text is too long. Maximum length is {MAX_TEXT_LENGTH} characters.\n"
            f"Your text has {len(text)} characters."
        )
        return

    # Get user config
    config = config_manager.get(chat_id)

    # Send "processing" message
    processing_msg = await update.message.reply_text("Analyzing text...")

    # Analyze if this is dialogue or monologue
    analysis = await dialogue_analyzer.analyze(text)

    if analysis.error:
        await processing_msg.edit_text(f"Error: {analysis.error}")
        return

    if analysis.is_dialogue:
        # Multi-speaker dialogue
        await processing_msg.edit_text(
            f"Detected dialogue with {len(analysis.speakers)} speakers. Generating audio..."
        )

        result = await tts_service.generate_dialogue(
            text=text,
            speakers=analysis.speakers,
            custom_prompt=config.custom_prompt,
            model=config.tts_model,
        )

        caption = f"Dialogue TTS | Model: {config.tts_model}\n"
        for speaker, voice in analysis.speakers:
            caption += f"• {speaker}: {voice}\n"
    else:
        # Single speaker monologue
        await processing_msg.edit_text(
            f"Generating audio with voice: {config.default_voice}..."
        )

        result = await tts_service.generate_monologue(
            text=text,
            voice_name=config.default_voice,
            custom_prompt=config.custom_prompt,
            model=config.tts_model,
        )

        caption = f"Voice: {config.default_voice} | Model: {config.tts_model}"

    # Handle result
    if result.success:
        # Convert PCM to M4A
        try:
            audio_data = AudioConverter.pcm_to_m4a(result.audio_data)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"gemini_tts_{timestamp}.m4a"
            audio_data.name = filename
            duration = AudioConverter.get_duration_seconds(result.audio_data)

            # Delete processing message
            await processing_msg.delete()

            # Send audio file
            await update.message.reply_audio(
                audio=audio_data,
                title=filename,
                caption=caption,
                duration=int(duration),
                filename=filename,
            )

        except Exception as e:
            await processing_msg.edit_text(f"Error converting audio: {str(e)}")
    else:
        await processing_msg.edit_text(f"TTS Error: {result.error}")
