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
    """
    Tool for transcribing audio using whisper-cpp and generating SRT files.
    """
    DEFAULT_MODEL: ClassVar[str] = os.getenv(
        "WHISPER_MODEL_PATH", "models/whisper/ggml-small.bin"
    )
    TIMEOUT_SECONDS: ClassVar[int] = 900

    def _run(self, cmd: List[str]) -> None:
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
                f"{details or 'No diagnostic output was returned.'}\\n"
                f"Command: {command_display}"
            )

    def _get_transcription_json(
        self,
        audio_path: Path,
    ) -> WhisperTranscription:
        """
        Runs whisper-cli (if needed) and returns the parsed JSON content.
        """
        json_path = audio_path.with_name(audio_path.name + ".json")
        if not json_path.exists():
            # -ojf: output json full (tokens with timestamps)
            cmd = [
                "whisper-cli",
                "-m", self.DEFAULT_MODEL,
                "-l", "en",
                "-ojf",
                "-f", str(audio_path),
            ]
            self._run(cmd)

        with open(json_path, 'r', encoding='utf-8') as f:
            try:
                return WhisperTranscription.model_validate(json.load(f))
            except (json.JSONDecodeError, ValidationError, UnicodeDecodeError) as exc:
                # A malformed or schema-incompatible cache must never be reused.
                json_path.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Invalid Whisper transcription cache: {json_path}. "
                    "The cache was deleted; retry this step to regenerate it."
                ) from exc

    def get_transcription_segments(
        self,
        audio_path: Path
    ) -> List[WhisperTranscriptionSegment]:
        """
        Transcribes audio and returns a list of segments with text and timestamps.
        Each segment: {"text": str, "start": float, "end": float} (times in seconds)
        """
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
            segments.append(
                WhisperTranscriptionSegment(text=text, start=start, end=end)
            )

        if not segments:
            raise RuntimeError(
                f"Whisper returned no usable speech segments for {audio_path}"
            )
        return segments

    def generate_srt(
        self,
        audio_path: Path,
        output_srt: Path,
    ) -> None:
        """
        Generates SRT file from audio file.
        """
        data = self._get_transcription_json(audio_path)

        # 1. Extract and merge tokens into words
        tokens = [
            t
            for s in data.transcription
            for t in s.tokens
            if not t.text.startswith("[_") and t.text.strip()
        ]

        if not tokens:
            raise RuntimeError(
                f"Whisper returned no usable words for subtitle generation: {audio_path}"
            )

        words: List[WhisperWord] = []
        for t in tokens:
            text, t_from, t_to = t.text, t.offsets.from_ms, t.offsets.to_ms
            if text.startswith(" ") or not words:
                words.append(WhisperWord(text=text.strip(), start=t_from, end=t_to))
            else:
                words[-1].text += text
                words[-1].end = t_to

        # 2. Group words into blocks (max 3 words or pause > 0.4s)
        blocks: List[List[WhisperWord]] = []
        current: List[WhisperWord] = []
        for w in words:
            pause = (float(w.start) - float(current[-1].end)) / 1000.0 if current else 0.0
            if len(current) >= 3 or pause > 0.4:
                blocks.append(current)
                current = []
            current.append(w)
        if current:
            blocks.append(current)

        def fmt(ms: int) -> str:
            s, ms = divmod(ms, 1000)
            m, s = divmod(s, 60)
            h, m = divmod(m, 60)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        # 3. Write SRT
        with open(output_srt, 'w', encoding='utf-8') as f:
            for i, block in enumerate(blocks):
                f.write(f"{i+1}\n{fmt(block[0].start)} --> {fmt(block[-1].end)}\n")
                f.write(" ".join(w.text for w in block) + "\n\n")
