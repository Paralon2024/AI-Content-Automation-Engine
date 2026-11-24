import subprocess
import unittest
from unittest.mock import MagicMock, patch

from tools.video_editing.whisper import WhisperTool


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


if __name__ == "__main__":
    unittest.main()
