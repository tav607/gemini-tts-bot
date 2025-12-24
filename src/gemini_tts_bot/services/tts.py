"""Gemini TTS service"""

import asyncio
import base64
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from ..config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

# API endpoint
API_URL = "https://generativelanguage.googleapis.com/v1beta/models"


@dataclass
class TTSResult:
    """Result of TTS generation"""

    audio_data: bytes
    success: bool
    error: Optional[str] = None


class TTSService:
    """Service for generating speech using Gemini TTS"""

    MODEL = "gemini-2.5-pro-preview-tts"

    def __init__(self):
        self.api_key = GEMINI_API_KEY

    async def generate_monologue(
        self,
        text: str,
        voice_name: str = "Kore",
        custom_prompt: str = "",
    ) -> TTSResult:
        """
        Generate speech for single-speaker text.

        Args:
            text: Text to convert to speech
            voice_name: Name of the voice to use
            custom_prompt: Additional instructions for TTS style

        Returns:
            TTSResult with audio data or error
        """
        try:
            # Build content with optional style instructions
            if custom_prompt:
                content = f"[Instructions: {custom_prompt}]\n\n{text}"
            else:
                content = text

            url = f"{API_URL}/{self.MODEL}:generateContent?key={self.api_key}"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": content}]
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

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)
                data = response.json()

            if "candidates" in data:
                inline_data = data["candidates"][0]["content"]["parts"][0].get("inlineData")
                if inline_data and inline_data.get("data"):
                    audio_data = base64.b64decode(inline_data["data"])
                    return TTSResult(audio_data=audio_data, success=True)

            if "error" in data:
                error_msg = data["error"].get("message", "Unknown error")
                logger.error(f"TTS API error: {error_msg}")
                return TTSResult(
                    audio_data=b"",
                    success=False,
                    error=self._sanitize_error_message(error_msg),
                )

            return TTSResult(
                audio_data=b"",
                success=False,
                error="No audio data in response",
            )

        except Exception as e:
            logger.exception("TTS monologue generation failed")
            return TTSResult(
                audio_data=b"",
                success=False,
                error=self._sanitize_error(e),
            )

    async def generate_dialogue(
        self,
        text: str,
        speakers: list[tuple[str, str]],
        custom_prompt: str = "",
    ) -> TTSResult:
        """
        Generate speech for multi-speaker dialogue.

        Args:
            text: Dialogue text with speaker names
            speakers: List of (speaker_name, voice_name) tuples
            custom_prompt: Additional instructions for TTS style

        Returns:
            TTSResult with audio data or error
        """
        if len(speakers) > 2:
            return TTSResult(
                audio_data=b"",
                success=False,
                error="Gemini TTS supports maximum 2 speakers",
            )

        try:
            # Build content with optional style instructions
            if custom_prompt:
                content = f"[Instructions: {custom_prompt}]\n\n{text}"
            else:
                content = text

            # Build speaker voice configs
            speaker_configs = []
            for speaker_name, voice_name in speakers:
                speaker_configs.append({
                    "speaker": speaker_name,
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice_name
                        }
                    }
                })

            url = f"{API_URL}/{self.MODEL}:generateContent?key={self.api_key}"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": content}]
                    }
                ],
                "generationConfig": {
                    "temperature": 1,
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "multiSpeakerVoiceConfig": {
                            "speakerVoiceConfigs": speaker_configs
                        }
                    }
                }
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)
                data = response.json()

            if "candidates" in data:
                inline_data = data["candidates"][0]["content"]["parts"][0].get("inlineData")
                if inline_data and inline_data.get("data"):
                    audio_data = base64.b64decode(inline_data["data"])
                    return TTSResult(audio_data=audio_data, success=True)

            if "error" in data:
                error_msg = data["error"].get("message", "Unknown error")
                logger.error(f"TTS API error: {error_msg}")
                return TTSResult(
                    audio_data=b"",
                    success=False,
                    error=self._sanitize_error_message(error_msg),
                )

            return TTSResult(
                audio_data=b"",
                success=False,
                error="No audio data in response",
            )

        except Exception as e:
            logger.exception("TTS dialogue generation failed")
            return TTSResult(
                audio_data=b"",
                success=False,
                error=self._sanitize_error(e),
            )

    def _sanitize_error_message(self, msg: str) -> str:
        """Sanitize API error message"""
        if "quota" in msg.lower() or "limit" in msg.lower():
            return "API quota exceeded. Please try again later."
        if "invalid" in msg.lower() and "key" in msg.lower():
            return "API authentication error. Please check your configuration."
        return "TTS generation failed. Please try again."

    def _sanitize_error(self, e: Exception) -> str:
        """Sanitize error message to avoid leaking sensitive information"""
        error_str = str(e)
        # Remove potential API keys or tokens from error messages
        if "api_key" in error_str.lower() or "token" in error_str.lower():
            return "API authentication error. Please check your configuration."
        if "quota" in error_str.lower() or "limit" in error_str.lower():
            return "API quota exceeded. Please try again later."
        if "timeout" in error_str.lower():
            return "Request timed out. Please try again."
        if "connection" in error_str.lower():
            return "Connection error. Please check your network."
        # For other errors, return a generic message with the exception type
        return f"TTS generation failed: {type(e).__name__}"


# Global TTS service instance
tts_service = TTSService()
