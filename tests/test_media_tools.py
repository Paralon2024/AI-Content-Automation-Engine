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

    def test_concat_manifest_escapes_quotes_and_backslashes(self) -> None:
        entry = FFmpegTool._format_concat_file_entry(
            Path("/tmp/video's\\final.mp4")
        )
        self.assertEqual(entry, "file '/tmp/video\\'s\\\\final.mp4'\n")

    def test_subtitle_filter_path_escapes_spaces(self) -> None:
        self.assertEqual(
            FFmpegTool._escape_filtergraph_value("/tmp/my video/final cut.srt"),
            "/tmp/my\\ video/final\\ cut.srt",
        )

    def test_subtitle_filter_path_rejects_newlines(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot contain newlines"):
            FFmpegTool._escape_filtergraph_value("/tmp/subtitles.srt\nforce_style=bad")

    def test_subtitle_filter_path_escapes_filtergraph_syntax(self) -> None:
        escaped = FFmpegTool._escape_filtergraph_value(
            "C:/media/it's, [final];a=b.srt"
        )
        self.assertEqual(
            escaped,
            "C\\:/media/it\\'s\\, \\[final\\]\\;a\\=b.srt",
        )

    def test_concat_manifest_rejects_newline_path_injection(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot contain newlines"):
            FFmpegTool._format_concat_file_entry(Path("/tmp/first.mp4\nfile 'other.mp4'"))

    def test_ffmpeg_runs_without_a_shell_and_uses_timeout(self) -> None:
        process = CompletedProcess(
            args=["ffmpeg", "-version"], returncode=0, stdout="ok", stderr=""
        )
        with patch(
            "tools.video_editing.ffmpeg.subprocess.run",
            return_value=process,
        ) as run:
            FFmpegTool()._run("ffmpeg -version")

        self.assertFalse(run.call_args.kwargs["shell"])
        self.assertEqual(
            run.call_args.kwargs["timeout"], FFmpegTool.FFMPEG_TIMEOUT_SECONDS
        )
        self.assertEqual(run.call_args.args[0], ["ffmpeg", "-version"])

    def test_ffmpeg_timeout_raises_actionable_error(self) -> None:
        from subprocess import TimeoutExpired

        with patch(
            "tools.video_editing.ffmpeg.subprocess.run",
            side_effect=TimeoutExpired(
                cmd=["ffmpeg", "-i", "input.mp4"], timeout=1800,
                stderr="processing stalled",
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "FFmpeg timed out after 1800 seconds.*processing stalled"
            ):
                FFmpegTool()._run("ffmpeg -i input.mp4 output.mp4")

    def test_ffprobe_uses_shorter_timeout(self) -> None:
        process = CompletedProcess(
            args=["ffprobe", "-version"], returncode=0, stdout="1.0", stderr=""
        )
        with patch(
            "tools.video_editing.ffmpeg.subprocess.run",
            return_value=process,
        ) as run:
            output = FFmpegTool()._probe("ffprobe -version", "test media")

        self.assertEqual(output, "1.0")
        self.assertFalse(run.call_args.kwargs["shell"])
        self.assertEqual(
            run.call_args.kwargs["timeout"], FFmpegTool.FFPROBE_TIMEOUT_SECONDS
        )

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
