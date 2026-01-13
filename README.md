# Gemini TTS Telegram Bot

A Telegram bot that converts text to speech using Google's Gemini TTS API.

## Features

- **Single-speaker (Monologue)**: Send plain text for narration
- **Multi-speaker (Dialogue)**: Send text with speaker names for conversations
  ```
  Alice: Hello, how are you?
  Bob: I'm doing great, thanks!
  ```
- **30 Voice Options**: Choose from various voice styles (warm, energetic, calm, etc.)
- **Custom Prompts**: Control tone, pace, and style with natural language instructions
- **Multilingual**: Supports Chinese, English, and other languages

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- ffmpeg (for audio conversion)
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Google Gemini API Key (from [AI Studio](https://aistudio.google.com/apikey))

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/gemini-tts-bot.git
   cd gemini-tts-bot
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

3. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

4. Edit `.env`:
   ```
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   GEMINI_API_KEY=your_gemini_api_key
   ALLOWED_CHAT_IDS=123456789,987654321  # Optional: restrict access
   ```

5. (Optional) Generate voice samples for faster previews:
   ```bash
   uv run python scripts/generate_samples.py
   ```

## Usage

Start the bot:
```bash
uv run python -m gemini_tts_bot
```

### Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message and help |
| `/voice` | Choose your default voice |
| `/prompt` | Set custom TTS style |
| `/reset` | Reset all settings to default |
| `/help` | Show help message |

### Examples

**Simple text:**
```
Hello! This is a test message.
```

**With custom prompt:**
```
/prompt Speak slowly with a warm tone
```

**Dialogue (auto-detected):**
```
Teacher: Today we'll learn about planets.
Student: How many planets are in our solar system?
Teacher: There are eight planets.
```

## Available Voices

30 voices organized by style:

| Category | Voices |
|----------|--------|
| Bright/Upbeat | Zephyr, Puck, Leda, Aoede, Autonoe, Laomedeia, Sadachbia |
| Firm/Informative | Charon, Kore, Orus, Rasalgethi, Alnilam, Schedar |
| Smooth/Easy-going | Callirrhoe, Umbriel, Algieba, Despina |
| Clear | Iapetus, Erinome |
| Distinctive | Fenrir, Enceladus, Algenib, Achernar, Gacrux, Pulcherrima, Achird, Zubenelgenubi, Vindemiatrix, Sadaltager, Sulafat |

## Project Structure

```
gemini-tts-bot/
├── src/gemini_tts_bot/
│   ├── main.py           # Bot entry point
│   ├── config.py         # Configuration management
│   ├── handlers/
│   │   ├── commands.py   # Slash command handlers
│   │   └── text.py       # Text message handlers
│   ├── services/
│   │   ├── tts.py        # Gemini TTS API client
│   │   ├── audio.py      # Audio conversion (PCM to MP3)
│   │   └── analyzer.py   # Text analysis (dialogue detection)
│   └── utils/
│       └── voices.py     # Voice definitions
├── scripts/
│   └── generate_samples.py  # Voice sample generator
├── samples/              # Pre-generated voice samples
├── .env.example
├── pyproject.toml
└── README.md
```

## Configuration

User settings are stored in `~/.config/gemini_tts_bot/config.json`.

Environment variables:
- `TELEGRAM_BOT_TOKEN` - Required
- `GEMINI_API_KEY` - Required
- `ALLOWED_CHAT_IDS` - Optional, comma-separated list of allowed chat IDs
- `CONFIG_FILE_PATH` - Optional, custom config file path
- `SAMPLES_DIR_PATH` - Optional, custom samples directory path

## License

MIT
