"""Configuration management for the bot"""

import json
import logging
import os
import threading
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables (override=True to prefer .env over system env vars)
load_dotenv(override=True)

# Environment variables
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
ALLOWED_CHAT_IDS: set[int] = set()

_allowed_ids = os.getenv("ALLOWED_CHAT_IDS", "")
if _allowed_ids:
    for x in _allowed_ids.split(","):
        x = x.strip()
        if x:
            try:
                ALLOWED_CHAT_IDS.add(int(x))
            except ValueError:
                # Log warning but don't crash on invalid values
                import sys
                print(f"Warning: Invalid chat ID '{x}' in ALLOWED_CHAT_IDS, skipping", file=sys.stderr)

# Default values
DEFAULT_VOICE = "Kore"
DEFAULT_PROMPT = ""

# Limits (Gemini TTS: 4000 bytes per field, 8000 bytes total for text+prompt)
MAX_PROMPT_LENGTH = 500  # Maximum custom prompt length
MAX_TEXT_LENGTH = 4000   # Maximum text length for TTS (API limit: 4000 bytes)


def _get_config_path() -> Path:
    """Get config file path from env or use user data directory"""
    env_path = os.getenv("CONFIG_FILE_PATH")
    if env_path:
        return Path(env_path)
    # Use user's config directory for writable storage
    # This works correctly even when installed as a package
    config_dir = Path.home() / ".config" / "gemini_tts_bot"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"


CONFIG_FILE = _get_config_path()


@dataclass
class UserConfig:
    """User-specific configuration"""

    default_voice: str = DEFAULT_VOICE
    custom_prompt: str = DEFAULT_PROMPT

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserConfig":
        return cls(
            default_voice=data.get("default_voice", DEFAULT_VOICE),
            custom_prompt=data.get("custom_prompt", DEFAULT_PROMPT),
        )


class ConfigManager:
    """Manages user configurations with JSON persistence and thread safety"""

    def __init__(self, config_file: Path = CONFIG_FILE):
        self.config_file = config_file
        self._configs: dict[str, UserConfig] = {}
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        self._load()

    def _load(self) -> None:
        """Load configurations from JSON file"""
        with self._lock:
            if self.config_file.exists():
                try:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for chat_id, config_data in data.items():
                            self._configs[chat_id] = UserConfig.from_dict(config_data)
                    logger.info(f"Loaded {len(self._configs)} user configurations")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse config file: {e}")
                    # Backup corrupted file
                    backup_path = self.config_file.with_suffix(".json.bak")
                    try:
                        self.config_file.rename(backup_path)
                        logger.warning(f"Corrupted config backed up to {backup_path}")
                    except OSError:
                        pass
                    self._configs = {}
                except IOError as e:
                    logger.error(f"Failed to read config file: {e}")
                    self._configs = {}

    def _save(self) -> None:
        """Save configurations to JSON file with atomic write"""
        with self._lock:
            data = {chat_id: config.to_dict() for chat_id, config in self._configs.items()}
            # Write to temp file first, then rename for atomic operation
            temp_file = self.config_file.with_suffix(".json.tmp")
            try:
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                temp_file.replace(self.config_file)
            except IOError as e:
                logger.error(f"Failed to save config file: {e}")
                if temp_file.exists():
                    temp_file.unlink()
                raise

    def get(self, chat_id: int) -> UserConfig:
        """Get configuration for a chat, creating default if not exists"""
        with self._lock:
            key = str(chat_id)
            if key not in self._configs:
                self._configs[key] = UserConfig()
            return self._configs[key]

    def set_voice(self, chat_id: int, voice: str) -> bool:
        """Set default voice for a chat. Returns True if successful."""
        # Import here to avoid circular import
        from .utils.voices import is_valid_voice

        if not is_valid_voice(voice):
            logger.warning(f"Invalid voice '{voice}' for chat {chat_id}")
            return False

        with self._lock:
            config = self.get(chat_id)
            config.default_voice = voice
            self._save()
            return True

    def set_prompt(self, chat_id: int, prompt: str) -> None:
        """Set custom prompt for a chat"""
        with self._lock:
            # Validate prompt length
            if len(prompt) > MAX_PROMPT_LENGTH:
                prompt = prompt[:MAX_PROMPT_LENGTH]
                logger.warning(f"Prompt truncated to {MAX_PROMPT_LENGTH} chars for chat {chat_id}")
            config = self.get(chat_id)
            config.custom_prompt = prompt
            self._save()

    def reset(self, chat_id: int) -> None:
        """Reset configuration for a chat to defaults"""
        with self._lock:
            self._configs[str(chat_id)] = UserConfig()
            self._save()


# Global config manager instance
config_manager = ConfigManager()

# Track users who have had their commands set (in memory, resets on restart)
_commands_set_for: set[int] = set()


def is_allowed_chat(chat_id: int) -> bool:
    """Check if a chat ID is in the allowed list"""
    if not ALLOWED_CHAT_IDS:
        return True  # If no allowed IDs configured, allow all
    return chat_id in ALLOWED_CHAT_IDS


def validate_config() -> list[str]:
    """Validate required configuration, return list of errors"""
    errors = []
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is not set")
    if not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY is not set")
    return errors


def needs_commands_setup(chat_id: int) -> bool:
    """Check if commands need to be set up for this chat"""
    return chat_id not in _commands_set_for


def mark_commands_set(chat_id: int) -> None:
    """Mark that commands have been set for this chat"""
    _commands_set_for.add(chat_id)
