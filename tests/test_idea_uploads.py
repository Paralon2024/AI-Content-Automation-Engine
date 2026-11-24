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
    def test_mp4_validator_rejects_files_without_a_video_stream(self):
        from subprocess import CompletedProcess

        invalid = CompletedProcess(
            args=["ffprobe"], returncode=0,
            stdout='{"streams": [], "format": {"duration": "2.0"}}',
            stderr="",
        )
        with patch.object(ideas_router.subprocess, "run", return_value=invalid):
            with self.assertRaises(HTTPException) as raised:
                ideas_router._validate_mp4(Path("fake.mp4"))
        self.assertEqual(raised.exception.status_code, 415)

    def test_mp4_validator_rejects_zero_duration_video(self):
        from subprocess import CompletedProcess

        invalid = CompletedProcess(
            args=["ffprobe"], returncode=0,
            stdout='{"streams": [{"codec_type": "video"}], "format": {"duration": "0"}}',
            stderr="",
        )
        with patch.object(ideas_router.subprocess, "run", return_value=invalid):
            with self.assertRaises(HTTPException) as raised:
                ideas_router._validate_mp4(Path("empty.mp4"))
        self.assertEqual(raised.exception.status_code, 415)

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

    def test_script_upload_invalidates_all_assets_from_the_previous_script(self):
        audios = self.idea_dir / "audios"
        videos = self.idea_dir / "videos"
        editions = self.idea_dir / "editions"
        audios.mkdir()
        videos.mkdir()
        editions.mkdir()
        (audios / "scene_0001.wav").write_bytes(b"old audio")
        (videos / "scene_0001.mp4").write_bytes(b"old video")
        (editions / "raw_video.mp4").write_bytes(b"old edition")
        (self.idea_dir / "old_final.mp4").write_bytes(b"old final")

        asyncio.run(
            ideas_router.upload_script(
                1, upload("script.json", valid_script()), title="Replacement script",
                orientation=self.orientation,
            )
        )

        self.assertFalse(audios.exists())
        self.assertFalse(videos.exists())
        self.assertFalse(editions.exists())
        self.assertEqual(list(self.idea_dir.glob("*.mp4")), [])
        self.assertEqual(list(self.idea_dir.glob(".*.backup")), [])

    def test_script_staging_failure_preserves_existing_script(self):
        existing = b'{"scenes":[]}'
        script_path = self.idea_dir / "script.json"
        script_path.write_bytes(existing)
        original_write_bytes = Path.write_bytes

        def fail_staging_write(path, data):
            if ".script-" in path.name and path.name.endswith(".tmp"):
                raise OSError("simulated staging disk failure")
            return original_write_bytes(path, data)

        with patch.object(Path, "write_bytes", fail_staging_write):
            with self.assertRaisesRegex(OSError, "simulated staging disk failure"):
                asyncio.run(
                    ideas_router.upload_script(
                        1, upload("script.json", valid_script()),
                        orientation=self.orientation,
                    )
                )

        self.assertEqual(script_path.read_bytes(), existing)
        self.assertEqual(self.store.get_by_id(1).state, State.NEW)

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

    def test_script_upload_rolls_back_when_metadata_save_fails(self):
        old_script = b'{"old":"script"}'
        script_path = self.idea_dir / "script.json"
        script_path.write_bytes(old_script)
        audios = self.idea_dir / "audios"
        videos = self.idea_dir / "videos"
        editions = self.idea_dir / "editions"
        audios.mkdir()
        videos.mkdir()
        editions.mkdir()
        (audios / "scene_0001.wav").write_bytes(b"old audio")
        (videos / "scene_0001.mp4").write_bytes(b"old video")
        (editions / "raw_video.mp4").write_bytes(b"old edition")
        old_final = self.idea_dir / "old_final.mp4"
        old_final.write_bytes(b"old final")
        idea = self.idea

        class FailingStore:
            def get_by_id(self, idea_id):
                return idea

            def save(self, record):
                raise OSError("simulated metadata persistence failure")

        with patch.object(ideas_router, "_store", return_value=FailingStore()):
            with self.assertRaisesRegex(OSError, "simulated metadata persistence failure"):
                asyncio.run(
                    ideas_router.upload_script(
                        1, upload("script.json", valid_script()), title="New title",
                        orientation=self.orientation,
                    )
                )

        self.assertEqual(script_path.read_bytes(), old_script)
        self.assertEqual(idea.title, "Original title")
        self.assertEqual(idea.state, State.NEW)
        self.assertEqual(list(self.idea_dir.glob(".script-*.bak")), [])
        self.assertEqual((audios / "scene_0001.wav").read_bytes(), b"old audio")
        self.assertEqual((videos / "scene_0001.mp4").read_bytes(), b"old video")
        self.assertEqual((editions / "raw_video.mp4").read_bytes(), b"old edition")
        self.assertEqual(old_final.read_bytes(), b"old final")

    def test_video_upload_installs_expected_scene_set(self):
        (self.idea_dir / "script.json").write_bytes(valid_script())
        videos_dir = self.idea_dir / "videos"
        videos_dir.mkdir()
        stale = videos_dir / "scene_0002.mp4"
        stale.write_bytes(b"stale")
        mp4 = bytes.fromhex("000000186674797069736f6d") + b"-clip"

        result = with patch.object(ideas_router, "_validate_mp4"):
            result = asyncio.run(
                ideas_router.upload_videos(
                    1, [upload("scene.mp4", mp4)], orientation=self.orientation
                )
            )

        self.assertEqual(result["files_uploaded"], 1)
        self.assertEqual(self.store.get_by_id(1).state, State.VIDEOS_GENERATED)
        self.assertEqual((videos_dir / "scene_0001.mp4").read_bytes(), mp4)
        self.assertFalse(stale.exists())
        self.assertEqual(list(videos_dir.glob(".upload-*")), [])
        self.assertEqual(list(videos_dir.glob(".backup-*")), [])

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

    def test_video_upload_preserves_backup_when_rollback_restore_fails(self):
        (self.idea_dir / "script.json").write_bytes(valid_script())
        videos_dir = self.idea_dir / "videos"
        videos_dir.mkdir()
        existing = videos_dir / "scene_0001.mp4"
        existing.write_bytes(b"old-scene")
        original_state = self.idea.state
        original_replace = Path.replace
        preserved_backup = {}

        idea = self.idea

        class FailingStore:
            def get_by_id(self, idea_id):
                return idea

            def save(self, record):
                raise OSError("simulated metadata persistence failure")

        def fail_backup_restore(source, target):
            if source.parent.name.startswith(".backup-") and Path(target).name == source.name:
                preserved_backup["directory"] = source.parent
                raise OSError("simulated restore failure")
            return original_replace(source, target)

        with (
            patch.object(ideas_router, "_store", return_value=FailingStore()),
            patch.object(Path, "replace", fail_backup_restore),
        ):
            with patch.object(ideas_router, "_validate_mp4"), self.assertRaisesRegex(RuntimeError, "rollback was incomplete"):
                asyncio.run(
                    ideas_router.upload_videos(
                        1,
                        [upload("scene.mp4", bytes.fromhex("000000186674797069736f6d") + b"-new")],
                        orientation=self.orientation,
                    )
                )

        backup_dir = preserved_backup["directory"]
        self.assertTrue(backup_dir.is_dir())
        self.assertEqual((backup_dir / "scene_0001.mp4").read_bytes(), b"old-scene")
        self.assertEqual(self.idea.state, original_state)
        self.assertEqual(list(videos_dir.glob(".upload-*")), [])

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
            with patch.object(ideas_router, "_validate_mp4"), self.assertRaisesRegex(OSError, "simulated metadata persistence failure"):
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
