import unittest
from pathlib import Path

from flows.image_content_generator.pipeline.pipeline import Pipeline


class BatchAudioDurationValidationTests(unittest.TestCase):
    def test_rejects_non_finite_or_non_positive_batch_duration(self) -> None:
        audio_path = Path("batch.wav")
        for duration in (float("nan"), float("inf"), float("-inf"), 0.0, -1.0):
            with self.subTest(duration=duration):
                with self.assertRaisesRegex(RuntimeError, "Invalid batch audio duration"):
                    Pipeline._validate_batch_audio_duration(audio_path, duration)

    def test_accepts_positive_finite_batch_duration(self) -> None:
        Pipeline._validate_batch_audio_duration(Path("batch.wav"), 12.5)


if __name__ == "__main__":
    unittest.main()
