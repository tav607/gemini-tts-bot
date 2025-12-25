"""Dialogue analysis service using Gemini"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

from google import genai
from google.genai import types

from ..config import GEMINI_API_KEY
from ..utils.voices import VOICES, get_voice_for_character

logger = logging.getLogger(__name__)


@dataclass
class DialogueAnalysis:
    """Result of dialogue analysis"""

    is_dialogue: bool
    speakers: list[tuple[str, str]]  # [(speaker_name, voice_name), ...]
    error: Optional[str] = None


class DialogueAnalyzer:
    """Analyzes text to detect dialogue and assign appropriate voices"""

    MODEL = "gemini-2.0-flash"  # Fast model for analysis

    # Pattern to detect dialogue format: "Name:" or "Name："
    # Improved pattern to avoid matching URLs, times, and other false positives
    # - Must start at line beginning
    # - Speaker name: 1-20 chars, no slashes/dots (excludes URLs, file paths)
    # - Followed by : or ：
    # - Must have content after the colon
    DIALOGUE_PATTERN = re.compile(
        r"^([^:：/\.\n]{1,20})[：:]\s*\S",
        re.MULTILINE
    )

    # Patterns to exclude (URLs, times, technical patterns, etc.)
    EXCLUDE_PATTERNS = [
        re.compile(r"^\d+$"),                    # Pure numbers like "10"
        re.compile(r"^https?$", re.I),           # URL schemes
        re.compile(r"^\d{1,2}$"),                # Time hours like "10" in "10:30"
        re.compile(r".*\d+$"),                   # Ends with number (like "Step 1")
        re.compile(r"^(http|https|ftp|file)$", re.I),  # Protocol names
        re.compile(r"^(note|warning|error|info|debug|step)$", re.I),  # Common labels
    ]

    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)

    async def analyze(self, text: str) -> DialogueAnalysis:
        """
        Analyze text to determine if it's dialogue and assign voices.

        Args:
            text: The text to analyze

        Returns:
            DialogueAnalysis with speaker information
        """
        # First, try simple pattern matching
        speakers = self._extract_speakers_simple(text)

        if not speakers:
            return DialogueAnalysis(is_dialogue=False, speakers=[])

        # Gemini TTS multi-speaker mode requires exactly 2 speakers
        # If only 1 speaker detected, treat as monologue
        if len(speakers) == 1:
            logger.info(f"Only 1 speaker detected ({speakers[0]}), treating as monologue")
            return DialogueAnalysis(is_dialogue=False, speakers=[])

        if len(speakers) > 2:
            return DialogueAnalysis(
                is_dialogue=True,
                speakers=[],
                error=f"检测到 {len(speakers)} 个说话人，但目前仅支持最多 2 人的对话。请简化文本后重试。",
            )

        # Use Gemini to analyze speaker characteristics and assign voices
        try:
            voice_assignments = await self._analyze_with_gemini(text, speakers)
            return DialogueAnalysis(is_dialogue=True, speakers=voice_assignments)
        except Exception as e:
            logger.exception("Gemini analysis failed, using fallback")
            # Fallback: assign default voices
            fallback_voices = self._assign_default_voices(speakers)
            return DialogueAnalysis(is_dialogue=True, speakers=fallback_voices)

    def _extract_speakers_simple(self, text: str) -> list[str]:
        """Extract unique speaker names using regex"""
        matches = self.DIALOGUE_PATTERN.findall(text)
        # Get unique speakers while preserving order
        seen = set()
        speakers = []
        for name in matches:
            name = name.strip()
            if not name or name in seen:
                continue
            # Apply exclusion patterns
            excluded = False
            for pattern in self.EXCLUDE_PATTERNS:
                if pattern.match(name):
                    excluded = True
                    break
            if not excluded:
                seen.add(name)
                speakers.append(name)
        return speakers

    async def _analyze_with_gemini(
        self, text: str, speakers: list[str]
    ) -> list[tuple[str, str]]:
        """Use Gemini to analyze speaker characteristics and assign voices"""
        # Run blocking API call in thread pool
        return await asyncio.to_thread(
            self._analyze_with_gemini_sync, text, speakers
        )

    def _analyze_with_gemini_sync(
        self, text: str, speakers: list[str]
    ) -> list[tuple[str, str]]:
        """Synchronous implementation of Gemini analysis"""
        voice_names = list(VOICES.keys())

        prompt = f"""Analyze the following dialogue and assign appropriate voices to each speaker.

Available voices and their characteristics:
{self._format_voice_list()}

Speakers in the dialogue: {speakers}

Dialogue:
{text}

Based on the content and context of the dialogue, assign the most appropriate voice to each speaker.
Consider factors like:
- Gender implied by name or content
- Age (young/old)
- Personality (cheerful, serious, calm, etc.)
- Role (narrator, protagonist, etc.)

Respond ONLY with a JSON object in this exact format:
{{"assignments": [{{"speaker": "speaker_name", "voice": "voice_name", "reason": "brief reason"}}]}}

Make sure each speaker gets a DIFFERENT voice."""

        response = self.client.models.generate_content(
            model=self.MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json",
            ),
        )

        # Parse the response
        try:
            result = json.loads(response.text)
            assignments = []
            used_voices = set()
            assigned_speakers = set()

            # Only process speakers that were originally detected
            # This prevents the model from adding extra speakers
            for item in result.get("assignments", []):
                speaker = item.get("speaker", "")
                voice = item.get("voice", "")

                # Skip speakers not in the original list (model hallucination)
                if speaker not in speakers:
                    continue

                # Skip if already assigned (avoid duplicates)
                if speaker in assigned_speakers:
                    continue

                # Validate voice name
                if voice not in VOICES:
                    voice = "Charon" if "Charon" not in used_voices else "Kore"

                # Ensure unique voices
                if voice in used_voices:
                    for v in voice_names:
                        if v not in used_voices:
                            voice = v
                            break

                used_voices.add(voice)
                assigned_speakers.add(speaker)
                assignments.append((speaker, voice))

            # Handle missing speakers (ensure all original speakers get assigned)
            for speaker in speakers:
                if speaker not in assigned_speakers:
                    for v in voice_names:
                        if v not in used_voices:
                            assignments.append((speaker, v))
                            used_voices.add(v)
                            assigned_speakers.add(speaker)
                            break

            return assignments

        except (json.JSONDecodeError, KeyError):
            return self._assign_default_voices(speakers)

    def _assign_default_voices(self, speakers: list[str]) -> list[tuple[str, str]]:
        """Assign default voices when analysis fails"""
        default_voices = ["Charon", "Zephyr", "Kore", "Puck"]
        assignments = []
        for i, speaker in enumerate(speakers[:2]):
            assignments.append((speaker, default_voices[i % len(default_voices)]))
        return assignments

    def _format_voice_list(self) -> str:
        """Format voice list for the prompt"""
        lines = []
        for name, info in VOICES.items():
            lines.append(f"- {name}: {info.description}")
        return "\n".join(lines)


# Global analyzer instance
dialogue_analyzer = DialogueAnalyzer()
