import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.video_editing.whisper import WhisperTool


VALID_TRANSCRIPTION = {
    "transcription": [
        {
            "text": "hello",
            "offsets": {"from": 0, "to": 1000},
            "tokens": [
                {"text": " hello", "offsets": {"from": 0, "to": 1000}}
            ],
        }
    ]
}


class WhisperExecutionTests(unittest.TestCase):
    @patch("tools.video_editing.whisper.subprocess.run")
    def test_runs_without_shell_and_uses_timeout(self, run):
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        tool = WhisperTool()

        tool._run(["whisper-cli", "-f", "audio file.wav"])

        self.assertEqual(run.call_args.args[0], ["whisper-cli", "-f", "audio file.wav"])
        self.assertFalse(run.call_args.kwargs["shell"])
        self.assertEqual(run.call_args.kwargs["timeout"], tool.TIMEOUT_SECONDS)

    @patch("tools.video_editing.whisper.subprocess.run")
    def test_timeout_is_reported_as_actionable_runtime_error(self, run):
        run.side_effect = subprocess.TimeoutExpired(
            cmd=["whisper-cli"], timeout=900, stderr=b"model still processing"
        )

        with self.assertRaisesRegex(RuntimeError, "timed out after 900s") as error:
            WhisperTool()._run(["whisper-cli", "-f", "audio.wav"])

        self.assertIn("model still processing", str(error.exception))

    @patch("tools.video_editing.whisper.subprocess.run")
    def test_nonzero_exit_includes_diagnostics(self, run):
        run.return_value = MagicMock(
            returncode=2, stdout="", stderr="model file not found"
        )

        with self.assertRaisesRegex(RuntimeError, "exit code 2.*model file not found"):
            WhisperTool()._run(["whisper-cli", "-m", "missing.bin"])

    @patch.object(WhisperTool, "_run")
    def test_invalid_existing_cache_is_deleted_and_regenerated(self, run):
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "batch_0001.wav"
            cache = audio.with_name(audio.name + ".json")
            audio.write_bytes(b"wav")
            cache.write_text("{invalid json", encoding="utf-8")

            def write_valid_output(command):
                cache.write_text(json.dumps(VALID_TRANSCRIPTION), encoding="utf-8")

            run.side_effect = write_valid_output

            result = WhisperTool()._get_transcription_json(audio)

            self.assertEqual(result.transcription[0].text, "hello")
            self.assertEqual(run.call_count, 1)
            self.assertTrue(cache.is_file())

    @patch.object(WhisperTool, "_run")
    def test_missing_cache_is_generated_and_validated(self, run):
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "batch_0001.wav"
            cache = audio.with_name(audio.name + ".json")
            audio.write_bytes(b"wav")

            def write_valid_output(command):
                cache.write_text(json.dumps(VALID_TRANSCRIPTION), encoding="utf-8")

            run.side_effect = write_valid_output

            result = WhisperTool()._get_transcription_json(audio)

            self.assertEqual(result.transcription[0].text, "hello")
            run.assert_called_once()

    def test_full_whisper_json_accepts_zero_duration_boundary_tokens(self):
        # whisper.cpp emits zero-duration [_BEG_] and [_TT_*] control tokens.
        payload = {
            "transcription": [
                {
                    "text": " hello",
                    "offsets": {"from": 0, "to": 1000},
                    "tokens": [
                        {"text": "[_BEG_]", "offsets": {"from": 0, "to": 0}},
                        {"text": " hello", "offsets": {"from": 100, "to": 900}},
                        {"text": "[_TT_50]", "offsets": {"from": 1000, "to": 1000}},
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "transcription.json"
            cache.write_text(json.dumps(payload), encoding="utf-8")

            result = WhisperTool._load_transcription_cache(cache)

        self.assertEqual(len(result.transcription[0].tokens), 3)
        self.assertEqual(result.transcription[0].tokens[0].offsets.from_ms, 0)
        self.assertEqual(result.transcription[0].tokens[2].offsets.to_ms, 1000)

    @patch.object(WhisperTool, "_run")
    def test_invalid_fresh_output_is_deleted_with_clear_error(self, run):
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "batch_0001.wav"
            cache = audio.with_name(audio.name + ".json")
            audio.write_bytes(b"wav")
            run.side_effect = lambda command: cache.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "generated an invalid transcription JSON"):
                WhisperTool()._get_transcription_json(audio)

            self.assertFalse(cache.exists())


if __name__ == "__main__":
    unittest.main()
