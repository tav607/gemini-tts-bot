"""Gemini TTS service"""

import asyncio
import base64
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from ..config import GEMINI_API_KEY, TTS_MODELS, DEFAULT_MODEL

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

    MAX_RETRIES = 3

    def __init__(self):
        self.api_key = GEMINI_API_KEY

    def _get_model_name(self, model: str) -> str:
        """Get full model name from short name"""
        return TTS_MODELS.get(model, TTS_MODELS[DEFAULT_MODEL])

    def _parse_response(self, data: dict) -> TTSResult:
        """Parse API response and extract audio data"""
        # Log full response for debugging
        logger.debug(f"API response: {data}")

        if "candidates" in data:
            candidate = data["candidates"][0]

            # Check for finish reason that indicates blocked/failed generation
            finish_reason = candidate.get("finishReason", "")
            if finish_reason and finish_reason not in ("STOP", ""):
                logger.warning(f"TTS finished with reason: {finish_reason}")
                # Check for safety ratings
                safety_ratings = candidate.get("safetyRatings", [])
                if safety_ratings:
                    logger.warning(f"Safety ratings: {safety_ratings}")
                return TTSResult(
                    audio_data=b"",
                    success=False,
                    error=f"Content blocked: {finish_reason}",
                )

            # Try to get audio data
            content = candidate.get("content")
            if content and "parts" in content:
                inline_data = content["parts"][0].get("inlineData")
                if inline_data and inline_data.get("data"):
                    audio_data = base64.b64decode(inline_data["data"])
                    return TTSResult(audio_data=audio_data, success=True)

            # No content in candidate - log for debugging
            logger.warning(f"No content in candidate: {candidate}")
            return TTSResult(
                audio_data=b"",
                success=False,
                error="No audio content generated",
            )

        if "error" in data:
            error_msg = data["error"].get("message", "Unknown error")
            logger.error(f"TTS API error: {error_msg}")
            return TTSResult(
                audio_data=b"",
                success=False,
                error=self._sanitize_error_message(error_msg),
            )

        # Unknown response format
        logger.error(f"Unexpected API response format: {data}")
        return TTSResult(
            audio_data=b"",
            success=False,
            error="Unexpected API response",
        )

    async def generate_monologue(
        self,
        text: str,
        voice_name: str = "Kore",
        custom_prompt: str = "",
        model: str = DEFAULT_MODEL,
    ) -> TTSResult:
        """
        Generate speech for single-speaker text.

        Args:
            text: Text to convert to speech
            voice_name: Name of the voice to use
            custom_prompt: Additional instructions for TTS style
            model: TTS model to use ("flash" or "pro")

        Returns:
            TTSResult with audio data or error
        """
        # Build content with optional style instructions
        if custom_prompt:
            content = f"[Instructions: {custom_prompt}]\n\n{text}"
        else:
            content = text

        model_name = self._get_model_name(model)
        url = f"{API_URL}/{model_name}:generateContent?key={self.api_key}"
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

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    response = await client.post(url, json=payload)
                    data = response.json()

                result = self._parse_response(data)
                if result.success:
                    return result

                # If failed with "OTHER" or similar, retry
                last_error = result.error
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"TTS attempt {attempt + 1} failed: {result.error}, retrying...")
                    await asyncio.sleep(1)  # Brief delay before retry

            except Exception as e:
                logger.exception(f"TTS monologue attempt {attempt + 1} failed")
                last_error = self._sanitize_error(e)
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(1)

        return TTSResult(
            audio_data=b"",
            success=False,
            error=last_error or "TTS generation failed after retries",
        )

    async def generate_dialogue(
        self,
        text: str,
        speakers: list[tuple[str, str]],
        custom_prompt: str = "",
        model: str = DEFAULT_MODEL,
    ) -> TTSResult:
        """
        Generate speech for multi-speaker dialogue.

        Args:
            text: Dialogue text with speaker names
            speakers: List of (speaker_name, voice_name) tuples
            custom_prompt: Additional instructions for TTS style
            model: TTS model to use ("flash" or "pro")

        Returns:
            TTSResult with audio data or error
        """
        if len(speakers) > 2:
            return TTSResult(
                audio_data=b"",
                success=False,
                error="Gemini TTS supports maximum 2 speakers",
            )

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

        model_name = self._get_model_name(model)
        url = f"{API_URL}/{model_name}:generateContent?key={self.api_key}"
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

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    response = await client.post(url, json=payload)
                    data = response.json()

                result = self._parse_response(data)
                if result.success:
                    return result

                last_error = result.error
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"TTS dialogue attempt {attempt + 1} failed: {result.error}, retrying...")
                    await asyncio.sleep(1)

            except Exception as e:
                logger.exception(f"TTS dialogue attempt {attempt + 1} failed")
                last_error = self._sanitize_error(e)
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(1)

        return TTSResult(
            audio_data=b"",
            success=False,
            error=last_error or "TTS generation failed after retries",
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
