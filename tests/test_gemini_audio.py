import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.audio_generation.gemini import GeminiAudioGenerator


class GeminiAudioFileTests(unittest.TestCase):
    def _wav(self, payload: bytes = b"audio payload") -> bytes:
        return b"RIFF" + (len(payload) + 36).to_bytes(4, "little") + b"WAVE" + b"fmt " + b"\x10\x00\x00\x00" + b"\x01\x00\x01\x00" + b"\x80\x3e\x00\x00" + b"\x00\x7d\x00\x00" + b"\x02\x00\x10\x00" + b"data" + len(payload).to_bytes(4, "little") + payload

    def test_writes_valid_wav_and_replaces_existing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "speech.wav"
            output.write_bytes(b"old audio")

            GeminiAudioGenerator._write_wav_atomically(output, self._wav())

            self.assertEqual(output.read_bytes(), self._wav())
            self.assertEqual(list(Path(temp_dir).glob("*.tmp")), [])
            self.assertEqual(list(Path(temp_dir).glob(".*.tmp")), [])

    def test_rejects_truncated_wav_without_replacing_previous_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "speech.wav"
            output.write_bytes(b"previous audio")

            with self.assertRaisesRegex(RuntimeError, "empty or truncated"):
                GeminiAudioGenerator._write_wav_atomically(
                    output, b"RIFF" + b"\x00" * 4 + b"WAVE"
                )

            self.assertEqual(output.read_bytes(), b"previous audio")

    @patch("tools.audio_generation.gemini.os.replace", side_effect=OSError("disk error"))
    def test_failed_atomic_replace_preserves_previous_file_and_cleans_temp(self, _replace):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "speech.wav"
            output.write_bytes(b"previous audio")

            with self.assertRaisesRegex(OSError, "disk error"):
                GeminiAudioGenerator._write_wav_atomically(output, self._wav())

            self.assertEqual(output.read_bytes(), b"previous audio")
            self.assertEqual(list(Path(temp_dir).glob(".*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
