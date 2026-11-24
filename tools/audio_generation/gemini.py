import base64
import os
import tempfile
from pathlib import Path

from tools.common.gemini_base import GeminiBase
from tools.common.gemini_http import post_interaction
from tools.common.messenger import Messenger


class GeminiAudioGenerator(GeminiBase):
    tts_model: str = "gemini-3.8-flash-tts"
    voice_name: str = "Kore"
    api_url: str = "https://generativelanguage.googleapis.com/v1beta/interactions"

    @staticmethod
    def _write_wav_atomically(audio_path: Path, wav_data: bytes) -> None:
        """Validate and atomically replace a WAV file without exposing partial output."""
        if len(wav_data) <= 44:
            raise RuntimeError("Gemini TTS returned an empty or truncated WAV file")
        if not wav_data.startswith(b"RIFF") or wav_data[8:12] != b"WAVE":
            raise RuntimeError("Gemini TTS returned invalid WAV container data")

        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=audio_path.parent,
                prefix=f".{audio_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(wav_data)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, audio_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def text_to_speech(
        self,
        text: str,
        audio_path: Path,
    ) -> None:
        """
        Generate narration with the Gemini Interactions API and save the WAV output.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        audio_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "model": self.tts_model,
            "store": False,
            "input": [
                {
                    "type": "user_input",
                    "content": [
                        {
                            "type": "text",
                            "text": text,
                            "annotations": [
                                {
                                    "type": "speech_metadata",
                                    "style": (
                                        "Expressive, clear cinematic English narration. "
                                        "Use natural pacing and emotional emphasis. "
                                        "Read the supplied transcript verbatim."
                                    ),
                                }
                            ],
                        }
                    ],
                }
            ],
            "response_format": {"type": "audio", "mime_type": "audio/wav"},
            "generation_config": {
                "speech_config": [{"voice": self.voice_name}],
            },
        }

        result = post_interaction(
            api_url=self.api_url,
            api_key=api_key,
            payload=payload,
            timeout_seconds=600,
            operation="TTS",
        )

        audio_result = None
        for step in result.get("steps", []):
            if step.get("type") != "model_output":
                continue
            for item in step.get("content", []):
                if item.get("type") == "audio" and item.get("data"):
                    audio_result = item
                    break
            if audio_result:
                break

        if audio_result is None:
            raise RuntimeError(
                f"Gemini TTS returned no audio data. Response status: {result.get('status')}"
            )

        encoded_audio = audio_result["data"]

        try:
            wav_data = base64.b64decode(encoded_audio, validate=True)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("Gemini TTS returned invalid base64 audio data") from exc

        if not wav_data.startswith(b"RIFF") or wav_data[8:12] != b"WAVE":
            mime_type = audio_result.get("mime_type", "unknown")
            raise RuntimeError(
                f"Gemini TTS returned an unexpected audio format: {mime_type}. "
                "Expected audio/wav; verify the response_format configuration."
            )

        self._write_wav_atomically(audio_path, wav_data)

        usage = result.get("usage") or {}
        if usage:
            Messenger.usage(
                model=self.tts_model,
                prompt=usage.get("total_input_tokens", 0),
                thoughts=usage.get("total_thought_tokens", 0),
                output=usage.get("total_output_tokens", 0),
                total=usage.get("total_tokens", 0),
            )

        Messenger.audio(f"Audio generated: {audio_path}")
