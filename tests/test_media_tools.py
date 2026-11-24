import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from tools.video_editing.ffmpeg import FFmpegTool
from tools.video_editing.whisper import WhisperTool


class MediaToolDiagnosticsTests(unittest.TestCase):
    def test_ffmpeg_failure_includes_captured_stderr(self) -> None:
        process = CompletedProcess(
            args="ffmpeg",
            returncode=1,
            stdout="",
            stderr="Invalid data found when processing input",
        )
        with patch(
            "tools.video_editing.ffmpeg.subprocess.run",
            return_value=process,
        ) as run:
            with self.assertRaisesRegex(RuntimeError, "Invalid data found"):
                FFmpegTool()._run("ffmpeg -i broken.mp4 output.mp4")

        self.assertTrue(run.call_args.kwargs["capture_output"])
        self.assertTrue(run.call_args.kwargs["text"])

    def test_ffprobe_failure_includes_captured_stderr(self) -> None:
        process = CompletedProcess(
            args="ffprobe",
            returncode=1,
            stdout="",
            stderr="No such file or directory",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "missing.wav"
            with patch(
                "tools.video_editing.ffmpeg.subprocess.run",
                return_value=process,
            ):
                with self.assertRaisesRegex(RuntimeError, "No such file"):
                    FFmpegTool().get_audio_duration(audio_path)

    def test_whisper_failure_includes_captured_stderr(self) -> None:
        process = CompletedProcess(
            args="whisper-cli",
            returncode=2,
            stdout="",
            stderr="failed to load model file",
        )
        with patch(
            "tools.video_editing.whisper.subprocess.run",
            return_value=process,
        ) as run:
            with self.assertRaisesRegex(RuntimeError, "failed to load model file"):
                WhisperTool()._run("whisper-cli -m missing.bin -f input.wav")

        self.assertTrue(run.call_args.kwargs["capture_output"])

    def test_invalid_whisper_cache_schema_is_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "scene.wav"
            cache_path = audio_path.with_name(audio_path.name + ".json")
            cache_path.write_text(json.dumps({"unexpected": []}), encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "Invalid Whisper transcription cache"):
                WhisperTool()._get_transcription_json(audio_path)

            self.assertFalse(cache_path.exists())

    def test_empty_whisper_result_is_not_accepted_as_successful_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "scene.wav"
            cache_path = audio_path.with_name(audio_path.name + ".json")
            cache_path.write_text(json.dumps({"transcription": []}), encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "no usable speech segments"):
                WhisperTool().get_transcription_segments(audio_path)

    def test_empty_whisper_result_is_not_written_as_an_empty_srt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "scene.wav"
            cache_path = audio_path.with_name(audio_path.name + ".json")
            output_srt = Path(temp_dir) / "scene.srt"
            cache_path.write_text(
                json.dumps({
                    "transcription": [{
                        "text": "",
                        "offsets": {"from": 0, "to": 1000},
                        "tokens": [],
                    }]
                }),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "no usable words"):
                WhisperTool().generate_srt(audio_path, output_srt)

            self.assertFalse(output_srt.exists())


if __name__ == "__main__":
    unittest.main()
