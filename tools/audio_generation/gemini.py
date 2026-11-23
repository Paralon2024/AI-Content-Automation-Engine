import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from tools.common.gemini_base import GeminiBase
from tools.common.messenger import Messenger


class GeminiAudioGenerator(GeminiBase):
    tts_model: str = "gemini-3.8-flash-tts"
    voice_name: str = "Kore"
    api_url: str = "https://generativelanguage.googleapis.com/v1beta/interactions"

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

        request = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Gemini TTS request failed (HTTP {exc.code}): {details}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not connect to the Gemini TTS API: {exc}") from exc

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

        audio_path.write_bytes(wav_data)

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
