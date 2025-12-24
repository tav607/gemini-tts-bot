"""Voice definitions and utilities for Gemini TTS"""

from dataclasses import dataclass


@dataclass
class VoiceInfo:
    """Information about a voice"""

    name: str
    description: str
    character: str  # Brief character trait for dialogue matching


# All 30 available Gemini TTS voices
VOICES: dict[str, VoiceInfo] = {
    "Kore": VoiceInfo("Kore", "Firm and authoritative", "professional"),
    "Puck": VoiceInfo("Puck", "Upbeat and cheerful", "energetic"),
    "Charon": VoiceInfo("Charon", "Informative and clear", "narrator"),
    "Zephyr": VoiceInfo("Zephyr", "Bright and friendly", "cheerful"),
    "Fenrir": VoiceInfo("Fenrir", "Excitable and dynamic", "enthusiastic"),
    "Enceladus": VoiceInfo("Enceladus", "Breathy and soft", "gentle"),
    "Sulafat": VoiceInfo("Sulafat", "Warm and comforting", "warm"),
    "Leda": VoiceInfo("Leda", "Youthful and light", "young"),
    "Orus": VoiceInfo("Orus", "Deep and resonant", "deep"),
    "Aoede": VoiceInfo("Aoede", "Melodic and smooth", "melodic"),
    "Callirrhoe": VoiceInfo("Callirrhoe", "Elegant and refined", "elegant"),
    "Autonoe": VoiceInfo("Autonoe", "Calm and composed", "calm"),
    "Iapetus": VoiceInfo("Iapetus", "Strong and commanding", "commanding"),
    "Umbriel": VoiceInfo("Umbriel", "Mysterious and low", "mysterious"),
    "Algieba": VoiceInfo("Algieba", "Bright and articulate", "articulate"),
    "Despina": VoiceInfo("Despina", "Sweet and gentle", "sweet"),
    "Erinome": VoiceInfo("Erinome", "Expressive and vivid", "expressive"),
    "Algenib": VoiceInfo("Algenib", "Clear and precise", "precise"),
    "Rasalgethi": VoiceInfo("Rasalgethi", "Rich and warm", "rich"),
    "Laomedeia": VoiceInfo("Laomedeia", "Soft and soothing", "soothing"),
    "Achernar": VoiceInfo("Achernar", "Crisp and professional", "professional"),
    "Alnilam": VoiceInfo("Alnilam", "Bold and confident", "confident"),
    "Schedar": VoiceInfo("Schedar", "Mature and steady", "mature"),
    "Gacrux": VoiceInfo("Gacrux", "Friendly and approachable", "friendly"),
    "Pulcherrima": VoiceInfo("Pulcherrima", "Beautiful and flowing", "flowing"),
    "Achird": VoiceInfo("Achird", "Neutral and balanced", "neutral"),
    "Zubenelgenubi": VoiceInfo("Zubenelgenubi", "Thoughtful and measured", "thoughtful"),
    "Vindemiatrix": VoiceInfo("Vindemiatrix", "Warm and inviting", "inviting"),
    "Sadachbia": VoiceInfo("Sadachbia", "Light and pleasant", "pleasant"),
    "Sadaltager": VoiceInfo("Sadaltager", "Gentle and kind", "kind"),
}

# Featured voices for the selection menu (most distinct/popular)
FEATURED_VOICES = [
    "Kore",
    "Puck",
    "Charon",
    "Zephyr",
    "Fenrir",
    "Enceladus",
    "Sulafat",
    "Orus",
]


def get_voice_description(voice_name: str) -> str:
    """Get description for a voice"""
    if voice_name in VOICES:
        return VOICES[voice_name].description
    return "Unknown voice"


def is_valid_voice(voice_name: str) -> bool:
    """Check if a voice name is valid"""
    return voice_name in VOICES


def get_all_voice_names() -> list[str]:
    """Get all available voice names"""
    return list(VOICES.keys())


def get_voice_for_character(character_trait: str) -> str:
    """Suggest a voice based on character trait"""
    trait_lower = character_trait.lower()

    # Direct match
    for name, info in VOICES.items():
        if info.character == trait_lower:
            return name

    # Keyword matching
    trait_mappings = {
        "male": ["Orus", "Iapetus", "Fenrir", "Charon"],
        "female": ["Leda", "Despina", "Zephyr", "Aoede"],
        "old": ["Schedar", "Rasalgethi", "Orus"],
        "young": ["Leda", "Puck", "Zephyr"],
        "serious": ["Kore", "Charon", "Achernar"],
        "funny": ["Puck", "Fenrir", "Gacrux"],
        "angry": ["Iapetus", "Fenrir", "Alnilam"],
        "sad": ["Enceladus", "Laomedeia", "Umbriel"],
        "happy": ["Puck", "Zephyr", "Gacrux"],
        "calm": ["Autonoe", "Laomedeia", "Sulafat"],
        "excited": ["Fenrir", "Puck", "Erinome"],
    }

    for keyword, voices in trait_mappings.items():
        if keyword in trait_lower:
            return voices[0]

    # Default
    return "Charon"


# Sample text for voice preview
PREVIEW_TEXT = "Hello! Nice to meet you. 你好！很高兴认识你。"

# Samples directory path
import os
from pathlib import Path


def _get_samples_dir() -> Path:
    """Get samples directory from env or use default relative to project root"""
    env_path = os.getenv("SAMPLES_DIR_PATH")
    if env_path:
        return Path(env_path)
    # Default: samples in the project root (parent of src)
    return Path(__file__).parent.parent.parent.parent / "samples"


SAMPLES_DIR = _get_samples_dir()


def get_sample_path(voice_name: str) -> Path | None:
    """Get path to pre-generated sample file for a voice"""
    if not is_valid_voice(voice_name):
        return None
    sample_file = SAMPLES_DIR / f"{voice_name}.mp3"
    if sample_file.exists():
        return sample_file
    return None
