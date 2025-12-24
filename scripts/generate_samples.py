#!/usr/bin/env python3
"""Generate voice sample files for all available voices"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from google import genai
from google.genai import types

from gemini_tts_bot.config import GEMINI_API_KEY
from gemini_tts_bot.services.audio import AudioConverter
from gemini_tts_bot.utils.voices import VOICES

# Sample text: English + Chinese greeting (~3 seconds)
SAMPLE_TEXT = "Hello! Nice to meet you. 你好！很高兴认识你。"

# Output directory
SAMPLES_DIR = Path(__file__).parent.parent / "samples"


def generate_sample(client: genai.Client, voice_name: str) -> bytes | None:
    """Generate a sample audio for a voice"""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-pro-preview-tts",
            contents=SAMPLE_TEXT,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_name,
                        )
                    )
                ),
            ),
        )

        # Extract audio data
        if response.candidates:
            for candidate in response.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, "inline_data") and part.inline_data:
                            if part.inline_data.mime_type.startswith("audio/"):
                                import base64
                                data = part.inline_data.data
                                if isinstance(data, str):
                                    return base64.b64decode(data)
                                return data
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def main():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not set. Please configure .env file.")
        sys.exit(1)

    # Create output directory
    SAMPLES_DIR.mkdir(exist_ok=True)

    client = genai.Client(api_key=GEMINI_API_KEY)
    voice_names = list(VOICES.keys())
    total = len(voice_names)

    print(f"Generating samples for {total} voices...")
    print(f"Sample text: {SAMPLE_TEXT}")
    print(f"Output directory: {SAMPLES_DIR}")
    print()

    success = 0
    failed = []

    for i, voice_name in enumerate(voice_names, 1):
        output_file = SAMPLES_DIR / f"{voice_name}.mp3"

        # Skip if already exists
        if output_file.exists():
            print(f"[{i}/{total}] {voice_name}: Already exists, skipping")
            success += 1
            continue

        print(f"[{i}/{total}] {voice_name}: Generating...", end=" ", flush=True)

        pcm_data = generate_sample(client, voice_name)

        if pcm_data:
            # Convert to MP3
            mp3_buffer = AudioConverter.pcm_to_mp3(pcm_data)
            with open(output_file, "wb") as f:
                f.write(mp3_buffer.read())
            duration = AudioConverter.get_duration_seconds(pcm_data)
            print(f"OK ({duration:.1f}s)")
            success += 1
        else:
            print("FAILED")
            failed.append(voice_name)

        # Rate limiting - avoid hitting API too fast
        if i < total:
            time.sleep(1)

    print()
    print(f"Done! {success}/{total} samples generated.")
    if failed:
        print(f"Failed voices: {', '.join(failed)}")


if __name__ == "__main__":
    main()
