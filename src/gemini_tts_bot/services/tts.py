"""Gemini TTS service"""

import asyncio
import base64
import logging
from dataclasses import dataclass
from typing import Optional

from google import genai
from google.genai import types

from ..config import GEMINI_API_KEY

logger = logging.getLogger(__name__)


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
        self.client = genai.Client(api_key=GEMINI_API_KEY)

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
        # Run blocking API call in thread pool to avoid blocking event loop
        return await asyncio.to_thread(
            self._generate_monologue_sync, text, voice_name, custom_prompt
        )

    def _generate_monologue_sync(
        self,
        text: str,
        voice_name: str,
        custom_prompt: str,
    ) -> TTSResult:
        """Synchronous implementation of monologue generation"""
        try:
            # Build content with optional style instructions
            if custom_prompt:
                content = f"[Instructions: {custom_prompt}]\n\n{text}"
            else:
                content = text

            response = self.client.models.generate_content(
                model=self.MODEL,
                contents=content,
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

            # Extract audio data from response
            audio_data = self._extract_audio(response)
            if audio_data:
                return TTSResult(audio_data=audio_data, success=True)
            else:
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

        # Run blocking API call in thread pool to avoid blocking event loop
        return await asyncio.to_thread(
            self._generate_dialogue_sync, text, speakers, custom_prompt
        )

    def _generate_dialogue_sync(
        self,
        text: str,
        speakers: list[tuple[str, str]],
        custom_prompt: str,
    ) -> TTSResult:
        """Synchronous implementation of dialogue generation"""
        try:
            # Build content with optional style instructions
            if custom_prompt:
                content = f"[Instructions: {custom_prompt}]\n\n{text}"
            else:
                content = text

            # Build speaker voice configs
            speaker_configs = []
            for speaker_name, voice_name in speakers:
                speaker_configs.append(
                    types.SpeakerVoiceConfig(
                        speaker=speaker_name,
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_name,
                            )
                        ),
                    )
                )

            response = self.client.models.generate_content(
                model=self.MODEL,
                contents=content,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                            speaker_voice_configs=speaker_configs,
                        )
                    ),
                ),
            )

            # Extract audio data from response
            audio_data = self._extract_audio(response)
            if audio_data:
                return TTSResult(audio_data=audio_data, success=True)
            else:
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

    def _extract_audio(self, response) -> Optional[bytes]:
        """Extract audio bytes from Gemini response"""
        try:
            # The response contains audio data in the candidates
            if response.candidates:
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            # Check for inline_data with audio
                            if hasattr(part, "inline_data") and part.inline_data:
                                if part.inline_data.mime_type.startswith("audio/"):
                                    # Data may be base64 encoded
                                    data = part.inline_data.data
                                    if isinstance(data, str):
                                        return base64.b64decode(data)
                                    return data
            return None
        except Exception:
            return None

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
