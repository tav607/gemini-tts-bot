"""Audio format conversion service"""

import io
from pydub import AudioSegment


class AudioConverter:
    """Converts PCM audio data to various formats"""

    # Gemini TTS output format: 24kHz, mono, 16-bit PCM
    SAMPLE_RATE = 24000
    CHANNELS = 1
    SAMPLE_WIDTH = 2  # 16-bit = 2 bytes

    @classmethod
    def pcm_to_mp3(cls, pcm_data: bytes, bitrate: str = "128k") -> io.BytesIO:
        """
        Convert PCM audio data to MP3 format.

        Args:
            pcm_data: Raw PCM audio bytes (24kHz, mono, 16-bit)
            bitrate: MP3 bitrate (default: 128k)

        Returns:
            BytesIO containing MP3 data
        """
        # Create AudioSegment from raw PCM data
        audio = AudioSegment(
            data=pcm_data,
            sample_width=cls.SAMPLE_WIDTH,
            frame_rate=cls.SAMPLE_RATE,
            channels=cls.CHANNELS,
        )

        # Export to MP3
        mp3_buffer = io.BytesIO()
        audio.export(mp3_buffer, format="mp3", bitrate=bitrate)
        mp3_buffer.seek(0)

        return mp3_buffer

    @classmethod
    def pcm_to_ogg(cls, pcm_data: bytes) -> io.BytesIO:
        """
        Convert PCM audio data to OGG/Opus format.

        Args:
            pcm_data: Raw PCM audio bytes (24kHz, mono, 16-bit)

        Returns:
            BytesIO containing OGG data
        """
        audio = AudioSegment(
            data=pcm_data,
            sample_width=cls.SAMPLE_WIDTH,
            frame_rate=cls.SAMPLE_RATE,
            channels=cls.CHANNELS,
        )

        ogg_buffer = io.BytesIO()
        audio.export(ogg_buffer, format="ogg", codec="libopus")
        ogg_buffer.seek(0)

        return ogg_buffer

    @classmethod
    def pcm_to_wav(cls, pcm_data: bytes) -> io.BytesIO:
        """
        Convert PCM audio data to WAV format.

        Args:
            pcm_data: Raw PCM audio bytes (24kHz, mono, 16-bit)

        Returns:
            BytesIO containing WAV data
        """
        audio = AudioSegment(
            data=pcm_data,
            sample_width=cls.SAMPLE_WIDTH,
            frame_rate=cls.SAMPLE_RATE,
            channels=cls.CHANNELS,
        )

        wav_buffer = io.BytesIO()
        audio.export(wav_buffer, format="wav")
        wav_buffer.seek(0)

        return wav_buffer

    @classmethod
    def get_duration_seconds(cls, pcm_data: bytes) -> float:
        """
        Calculate duration of PCM audio in seconds.

        Args:
            pcm_data: Raw PCM audio bytes

        Returns:
            Duration in seconds
        """
        # bytes / (sample_width * channels * sample_rate) = seconds
        return len(pcm_data) / (cls.SAMPLE_WIDTH * cls.CHANNELS * cls.SAMPLE_RATE)
