import unittest

from pydantic import ValidationError

from flows.image_content_generator.pipeline.prompt_base.models import VideoScript
from flows.image_content_generator.pipeline.schemas import AudioAlignment, SceneAlignment


def scene(scene_number: int) -> dict:
    return {
        "scene_number": scene_number,
        "image_prompt": {
            "subjects": [],
            "environment": "A quiet room",
            "lighting": "Soft light",
            "composition": "Wide shot",
            "style": "Cinematic",
            "aspect_ratio": "9:16",
        },
        "video_prompt": {
            "motion": "Slow movement",
            "camera_movement": "Static",
            "transition": "Cut",
            "duration_hint": "Short",
        },
        "narration": "A test narration",
    }


class VideoScriptValidationTests(unittest.TestCase):
    def test_accepts_sequential_scene_numbers(self) -> None:
        script = VideoScript.model_validate({"scenes": [scene(1), scene(2)]})
        self.assertEqual([item.scene_number for item in script.scenes], [1, 2])

    def test_rejects_duplicate_or_out_of_order_scene_numbers(self) -> None:
        for numbers in ([1, 1], [2, 1], [1, 3]):
            with self.subTest(numbers=numbers):
                with self.assertRaises(ValidationError):
                    VideoScript.model_validate({"scenes": [scene(n) for n in numbers]})

    def test_rejects_empty_script(self) -> None:
        with self.assertRaises(ValidationError):
            VideoScript.model_validate({"scenes": []})


class AudioAlignmentValidationTests(unittest.TestCase):
    def test_accepts_sequential_valid_alignments(self) -> None:
        alignment = AudioAlignment.model_validate({
            "alignments": [
                {"scene_number": 1, "start_time": 0.0, "end_time": 2.5},
                {"scene_number": 2, "start_time": 2.5, "end_time": 5.0},
            ]
        })
        self.assertEqual(len(alignment.alignments), 2)

    def test_rejects_duplicate_or_out_of_order_scene_numbers(self) -> None:
        with self.assertRaises(ValidationError):
            AudioAlignment.model_validate({
                "alignments": [
                    {"scene_number": 1, "start_time": 0.0, "end_time": 2.5},
                    {"scene_number": 1, "start_time": 2.5, "end_time": 5.0},
                ]
            })

    def test_rejects_overlapping_scene_time_ranges(self) -> None:
        with self.assertRaisesRegex(ValidationError, "must not overlap"):
            AudioAlignment.model_validate({
                "alignments": [
                    {"scene_number": 1, "start_time": 0.0, "end_time": 2.8},
                    {"scene_number": 2, "start_time": 2.5, "end_time": 5.0},
                ]
            })

    def test_accepts_adjacent_scene_time_ranges(self) -> None:
        alignment = AudioAlignment.model_validate({
            "alignments": [
                {"scene_number": 1, "start_time": 0.0, "end_time": 2.5},
                {"scene_number": 2, "start_time": 2.5, "end_time": 5.0},
            ]
        })
        self.assertEqual(len(alignment.alignments), 2)

    def test_rejects_negative_non_finite_and_reversed_times(self) -> None:
        invalid_ranges = [
            (-0.1, 1.0),
            (1.0, 1.0),
            (2.0, 1.0),
            (0.0, float("nan")),
            (0.0, float("inf")),
        ]
        for start_time, end_time in invalid_ranges:
            with self.subTest(start_time=start_time, end_time=end_time):
                with self.assertRaises(ValidationError):
                    SceneAlignment.model_validate({
                        "scene_number": 1,
                        "start_time": start_time,
                        "end_time": end_time,
                    })


if __name__ == "__main__":
    unittest.main()
