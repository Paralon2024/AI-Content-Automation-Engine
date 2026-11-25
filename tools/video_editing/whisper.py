import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import ClassVar, List

from pydantic import ValidationError

from tools.common.base_model import BaseModelTool
from tools.video_editing.whisper_schemas import (
    WhisperTranscription,
    WhisperTranscriptionSegment,
    WhisperWord,
)


class WhisperTool(BaseModelTool):
    """Transcribe audio using whisper.cpp and generate SRT files."""

    DEFAULT_MODEL: ClassVar[str] = os.getenv(
        "WHISPER_MODEL_PATH", "models/whisper/ggml-small.bin"
    )
    TIMEOUT_SECONDS: ClassVar[int] = 900

    def _run(self, cmd: List[str] | str) -> None:
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)
        command_display = shlex.join(cmd)
        try:
            process = subprocess.run(
                cmd,
                shell=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            details = exc.stderr or exc.stdout or ""
            if isinstance(details, bytes):
                details = details.decode("utf-8", errors="replace")
            details = str(details).strip()
            if len(details) > 2000:
                details = details[-2000:]
            raise RuntimeError(
                f"Whisper timed out after {self.TIMEOUT_SECONDS}s. "
                f"The transcription was stopped. {details} Command: {command_display}"
            ) from exc

        if process.returncode != 0:
            details = (process.stderr or process.stdout or "").strip()
            if len(details) > 4000:
                details = details[-4000:]
            raise RuntimeError(
                f"Whisper failed (exit code {process.returncode}): "
                f"{details or 'No diagnostic output was returned.'}\n"
                f"Command: {command_display}"
            )

    @staticmethod
    def _load_transcription_cache(json_path: Path) -> WhisperTranscription:
        """Read and validate a Whisper JSON cache, including its on-disk encoding."""
        with json_path.open("r", encoding="utf-8") as cache_file:
            payload = json.load(cache_file)
        return WhisperTranscription.model_validate(payload)

    @staticmethod
    def _validation_details(exc: Exception) -> str:
        details = str(exc).strip()
        if len(details) > 2500:
            details = details[:2500] + "..."
        return details or exc.__class__.__name__

    def _transcribe_to_json(self, audio_path: Path, json_path: Path) -> WhisperTranscription:
        """Run whisper.cpp and validate the JSON it just produced."""
        cmd = [
            "whisper-cli",
            "-m", self.DEFAULT_MODEL,
            "-l", "en",
            "-ojf",
            "-f", str(audio_path),
        ]
        self._run(cmd)

        if not json_path.is_file():
            raise RuntimeError(
                f"Whisper completed but did not create its expected JSON output: {json_path}. "
                "Check the Whisper CLI version and output permissions."
            )

        try:
            return self._load_transcription_cache(json_path)
        except (OSError, json.JSONDecodeError, ValidationError, UnicodeDecodeError) as exc:
            json_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Whisper generated invalid JSON at {json_path}: "
                f"{self._validation_details(exc)}. The invalid output was deleted."
            ) from exc

    def _get_transcription_json(self, audio_path: Path) -> WhisperTranscription:
        """Reuse a valid cache; regenerate a malformed cache once automatically."""
        json_path = audio_path.with_name(audio_path.name + ".json")

        if json_path.is_file():
            try:
                return self._load_transcription_cache(json_path)
            except (OSError, json.JSONDecodeError, ValidationError, UnicodeDecodeError):
                json_path.unlink(missing_ok=True)

        return self._transcribe_to_json(audio_path, json_path)

    def get_transcription_segments(
        self, audio_path: Path
    ) -> List[WhisperTranscriptionSegment]:
        """Return transcription segments with timestamps in seconds."""
        data = self._get_transcription_json(audio_path)
        segments: List[WhisperTranscriptionSegment] = []
        for segment in data.transcription:
            text = segment.text.strip()
            if not text:
                continue
            start = segment.offsets.from_ms / 1000.0
            end = segment.offsets.to_ms / 1000.0
            if start < 0 or end <= start:
                raise RuntimeError(
                    f"Whisper returned an invalid timestamp range for {audio_path}: "
                    f"{start:.3f}s to {end:.3f}s"
                )
            segments.append(WhisperTranscriptionSegment(text=text, start=start, end=end))

        if not segments:
            raise RuntimeError(f"Whisper returned no usable speech segments for {audio_path}")
        return segments

    def generate_srt(self, audio_path: Path, output_srt: Path) -> None:
        """Generate an SRT file from Whisper's token timestamps."""
        data = self._get_transcription_json(audio_path)

        tokens = [
            token
            for segment in data.transcription
            for token in segment.tokens
            if not token.text.startswith("[_") and token.text.strip()
        ]

        if not tokens:
            raise RuntimeError(
                f"Whisper returned no usable words for subtitle generation: {audio_path}"
            )

        words: List[WhisperWord] = []
        for token in tokens:
            text = token.text
            start_ms = token.offsets.from_ms
            end_ms = token.offsets.to_ms
            if start_ms < 0 or end_ms <= start_ms:
                raise RuntimeError(
                    f"Whisper returned invalid timing for speech token {text!r} "
                    f"in {audio_path}: {start_ms}ms to {end_ms}ms"
                )
            if text.startswith(" ") or not words:
                words.append(WhisperWord(text=text.strip(), start=start_ms, end=end_ms))
            else:
                words[-1].text += text
                words[-1].end = end_ms

        blocks: List[List[WhisperWord]] = []
        current: List[WhisperWord] = []
        for word in words:
            pause = (
                (float(word.start) - float(current[-1].end)) / 1000.0
                if current else 0.0
            )
            if len(current) >= 3 or pause > 0.4:
                blocks.append(current)
                current = []
            current.append(word)
        if current:
            blocks.append(current)

        def fmt(ms: int) -> str:
            seconds, milliseconds = divmod(ms, 1000)
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

        output_srt.parent.mkdir(parents=True, exist_ok=True)
        with output_srt.open("w", encoding="utf-8") as output_file:
            for index, block in enumerate(blocks):
                output_file.write(
                    f"{index + 1}\n{fmt(block[0].start)} --> {fmt(block[-1].end)}\n"
                )
                output_file.write(" ".join(word.text for word in block) + "\n\n")
