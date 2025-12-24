#!/usr/bin/env python3
"""Generate voice sample files for all available voices"""

import base64
import sys
import time
from pathlib import Path

import requests

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gemini_tts_bot.config import GEMINI_API_KEY
from gemini_tts_bot.services.audio import AudioConverter
from gemini_tts_bot.utils.voices import VOICES

# Sample text: English + Chinese greeting (~3 seconds)
SAMPLE_TEXT = "Hello! Nice to meet you. 你好！很高兴认识你。"

# Output directory
SAMPLES_DIR = Path(__file__).parent.parent / "samples"

# API endpoint
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent"


def generate_sample(voice_name: str) -> bytes | None:
    """Generate a sample audio for a voice using REST API"""
    try:
        url = f"{API_URL}?key={GEMINI_API_KEY}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": SAMPLE_TEXT}]
                }
            ],
            "generationConfig": {
                "temperature": 1,
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice_name
                        }
                    }
                }
            }
        }

        response = requests.post(url, json=payload, timeout=60)
        data = response.json()

        if "candidates" in data:
            inline_data = data["candidates"][0]["content"]["parts"][0].get("inlineData")
            if inline_data and inline_data.get("data"):
                return base64.b64decode(inline_data["data"])

        if "error" in data:
            print(f"  Error: {data['error'].get('message', 'Unknown error')}")
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

        pcm_data = generate_sample(voice_name)

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
