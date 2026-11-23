import asyncio
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from starlette.datastructures import UploadFile

from api.routers import ideas as ideas_router
from flows.image_content_generator.pipeline.schemas import IdeaRaw, State, VideoOrientation
from tools.common.storage_folder import FolderStore


def valid_script(scene_count=1):
    scene = {
        "scene_number": 1,
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
    return json.dumps({"scenes": [dict(scene, scene_number=i) for i in range(1, scene_count + 1)]}).encode()


def upload(name, data):
    return UploadFile(filename=name, file=io.BytesIO(data))


class UploadEndpointTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.out_root = self.root / "out"
        self.idea_dir = self.out_root / "ideas" / "idea_000001"
        self.idea_dir.mkdir(parents=True)
        self.store = FolderStore(self.root / "store" / "ideas", IdeaRaw)
        self.idea = self.store.add(
            IdeaRaw(id=1, title="Original title", category="test", state=State.NEW)
        )
        self.orientation = VideoOrientation.SHORT
        self.patches = [
            patch.object(ideas_router, "_out", return_value=self.out_root),
            patch.object(ideas_router, "_store", return_value=self.store),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp_dir.cleanup()

    def test_script_upload_saves_valid_script_and_updates_state(self):
        result = asyncio.run(
            ideas_router.upload_script(
                1, upload("script.json", valid_script()), title="Updated title",
                orientation=self.orientation,
            )
        )
        self.assertEqual(result["title"], "Updated title")
        self.assertEqual(self.store.get_by_id(1).state, State.SCRIPT_GENERATED)
        self.assertEqual(
            (self.idea_dir / "script.json").read_bytes(),
            valid_script(),
        )

    def test_invalid_script_upload_does_not_change_existing_script_or_state(self):
        existing = b'{"scenes":[]}'
        (self.idea_dir / "script.json").write_bytes(existing)
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                ideas_router.upload_script(
                    1, upload("bad.json", b'{"scenes":'),
                    orientation=self.orientation,
                )
            )
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual((self.idea_dir / "script.json").read_bytes(), existing)
        self.assertEqual(self.store.get_by_id(1).state, State.NEW)

    def test_video_upload_rejects_scene_count_mismatch_before_replacing_files(self):
        (self.idea_dir / "script.json").write_bytes(valid_script(scene_count=2))
        videos_dir = self.idea_dir / "videos"
        videos_dir.mkdir()
        existing = videos_dir / "scene_0001.mp4"
        existing.write_bytes(b"old-scene")
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                ideas_router.upload_videos(
                    1, [upload("scene.mp4", bytes.fromhex("000000186674797069736f6d"))],
                    orientation=self.orientation,
                )
            )
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(existing.read_bytes(), b"old-scene")

    def test_video_upload_rolls_back_when_metadata_save_fails(self):
        (self.idea_dir / "script.json").write_bytes(valid_script())
        videos_dir = self.idea_dir / "videos"
        videos_dir.mkdir()
        existing = videos_dir / "scene_0001.mp4"
        existing.write_bytes(b"old-scene")
        original_state = self.idea.state

        idea = self.idea

        class FailingStore:
            def get_by_id(self, idea_id):
                return idea

            def save(self, idea):
                raise OSError("simulated metadata persistence failure")

        with patch.object(ideas_router, "_store", return_value=FailingStore()):
            with self.assertRaisesRegex(OSError, "simulated metadata persistence failure"):
                asyncio.run(
                    ideas_router.upload_videos(
                        1,
                        [upload("scene.mp4", bytes.fromhex("000000186674797069736f6d") + b"-new")],
                        orientation=self.orientation,
                    )
                )

        self.assertEqual(existing.read_bytes(), b"old-scene")
        self.assertEqual(self.idea.state, original_state)
        self.assertEqual(list(videos_dir.glob(".upload-*")), [])
        self.assertEqual(list(videos_dir.glob(".backup-*")), [])


if __name__ == "__main__":
    unittest.main()
