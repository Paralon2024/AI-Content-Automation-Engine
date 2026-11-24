import math
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.video_editing.ffmpeg import FFmpegTool


class FFmpegSyncValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = FFmpegTool()

    @patch.object(FFmpegTool, "_run")
    @patch.object(FFmpegTool, "get_video_duration", return_value=10.0)
    @patch.object(FFmpegTool, "get_audio_duration")
    def test_rejects_invalid_audio_duration(self, get_audio_duration, _video_duration, run):
        for duration in (0.0, -1.0, math.nan, math.inf, -math.inf):
            with self.subTest(duration=duration):
                get_audio_duration.return_value = duration
                with self.assertRaisesRegex(RuntimeError, "Invalid audio duration"):
                    self.tool.sync_video_and_audio(
                        Path("scene.mp4"), Path("scene.wav"), Path("synced.mp4")
                    )
        run.assert_not_called()

    @patch.object(FFmpegTool, "_run")
    @patch.object(FFmpegTool, "get_video_duration")
    @patch.object(FFmpegTool, "get_audio_duration", return_value=5.0)
    def test_rejects_invalid_video_duration(self, _audio_duration, get_video_duration, run):
        for duration in (0.0, -1.0, math.nan, math.inf, -math.inf):
            with self.subTest(duration=duration):
                get_video_duration.return_value = duration
                with self.assertRaisesRegex(RuntimeError, "Invalid video duration"):
                    self.tool.sync_video_and_audio(
                        Path("scene.mp4"), Path("scene.wav"), Path("synced.mp4")
                    )
        run.assert_not_called()

    @patch.object(FFmpegTool, "_run")
    @patch.object(FFmpegTool, "get_video_duration", return_value=10.0)
    @patch.object(FFmpegTool, "get_audio_duration", return_value=5.0)
    def test_valid_durations_produce_half_speed_factor(self, _audio_duration, _video_duration, run):
        self.tool.sync_video_and_audio(
            Path("scene.mp4"), Path("scene.wav"), Path("synced.mp4")
        )
        command = run.call_args.args[0]
        self.assertIn("setpts=0.500000*PTS", command)


if __name__ == "__main__":
    unittest.main()
