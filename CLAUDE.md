# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
# Install dependencies
uv sync

# Run the bot
uv run python -m gemini_tts_bot

# Generate voice samples (optional, for faster previews)
uv run python scripts/generate_samples.py
```

## Required Environment Variables

Set in `.env` file (copy from `.env.example`):
- `TELEGRAM_BOT_TOKEN` - From @BotFather
- `GEMINI_API_KEY` - From AI Studio
- `ALLOWED_CHAT_IDS` - Optional comma-separated list of allowed Telegram chat IDs

## Architecture

### Request Flow

1. User sends text message to Telegram bot
2. `handlers/text.py` receives message, applies rate limiting (5 req/min per user)
3. `services/analyzer.py` uses regex + Gemini Flash to detect dialogue vs monologue
4. `services/tts.py` calls Gemini TTS REST API (`gemini-2.5-pro-preview-tts`)
5. `services/audio.py` converts PCM (24kHz mono 16-bit) to MP3 via pydub
6. Bot sends audio file back to user

### Key Design Decisions

- **REST API for TTS**: Uses direct HTTP calls to Gemini API instead of SDK due to SDK limitations with audio response handling
- **Dialogue Detection**: Two-stage approach - fast regex pattern matching first, then Gemini Flash for voice assignment if dialogue detected
- **Multi-speaker limit**: Gemini TTS supports max 2 speakers in dialogue mode
- **Thread-safe config**: `ConfigManager` uses `threading.RLock` for concurrent access to user settings stored in `~/.config/gemini_tts_bot/config.json`

### Service Dependencies

- `tts_service` - Singleton for TTS generation
- `dialogue_analyzer` - Singleton for text analysis
- `config_manager` - Singleton for user settings persistence

### Voice System

30 prebuilt voices defined in `utils/voices.py`. Voice assignment for dialogue uses Gemini to match speaker characteristics (gender, age, personality) to appropriate voices.
