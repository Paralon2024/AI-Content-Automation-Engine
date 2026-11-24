import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flows.image_content_generator.pipeline.pipeline import (
    Pipeline,
    preserve_audios_on_force,
)
from flows.image_content_generator.pipeline.prompt_base.models import VideoScript
from flows.image_content_generator.pipeline.schemas import (
    IdeaRaw,
    ScriptFormData,
    State,
    VideoOrientation,
)
from tools.common.project_assets import (
    discard_derived_asset_backups,
    restore_derived_assets,
    stage_derived_assets,
)


def make_script() -> VideoScript:
    return VideoScript.model_validate({
        "scenes": [{
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
            "narration": "A new narration",
        }]
    })


class ProjectAssetTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.idea_dir = Path(self.temp_dir.name) / "idea_000001"
        self.idea_dir.mkdir()

        for folder in ("audios", "videos", "editions"):
            asset_dir = self.idea_dir / folder
            asset_dir.mkdir()
            (asset_dir / "existing.bin").write_bytes(folder.encode("utf-8"))

        (self.idea_dir / "final.mp4").write_bytes(b"previous final")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_restore_recovers_all_staged_assets(self) -> None:
        backups = stage_derived_assets(self.idea_dir)

        self.assertFalse((self.idea_dir / "audios").exists())
        self.assertFalse((self.idea_dir / "videos").exists())
        self.assertFalse((self.idea_dir / "editions").exists())
        self.assertFalse((self.idea_dir / "final.mp4").exists())

        restore_derived_assets(backups)

        for folder in ("audios", "videos", "editions"):
            self.assertEqual(
                (self.idea_dir / folder / "existing.bin").read_bytes(),
                folder.encode("utf-8"),
            )
        self.assertEqual(
            (self.idea_dir / "final.mp4").read_bytes(),
            b"previous final",
        )
        self.assertEqual(list(self.idea_dir.glob(".*.backup")), [])

    def test_discard_removes_staged_assets_after_commit(self) -> None:
        backups = stage_derived_assets(self.idea_dir)
        discard_derived_asset_backups(backups)

        self.assertEqual(list(self.idea_dir.glob(".*.backup")), [])
        self.assertFalse((self.idea_dir / "audios").exists())
        self.assertFalse((self.idea_dir / "videos").exists())
        self.assertFalse((self.idea_dir / "editions").exists())
        self.assertFalse((self.idea_dir / "final.mp4").exists())


class ForcedAudioRegenerationTests(unittest.TestCase):
    def test_previous_audio_is_restored_when_forced_regeneration_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio_dir = root / "audios"
            audio_dir.mkdir()
            (audio_dir / "scene_0001.wav").write_bytes(b"previous audio")

            class FakePipeline:
                AUDIOS_DIR = "audios"

                def get_idea_path(self, idea_id: int) -> Path:
                    return root

                @preserve_audios_on_force
                def regenerate(self, idea_id: int, force: bool = False) -> None:
                    new_dir = self.get_idea_path(idea_id) / self.AUDIOS_DIR
                    new_dir.mkdir(exist_ok=True)
                    (new_dir / "partial.wav").write_bytes(b"partial")
                    raise RuntimeError("simulated TTS failure")

            with self.assertRaisesRegex(RuntimeError, "simulated TTS failure"):
                FakePipeline().regenerate(1, force=True)

            self.assertEqual(
                (audio_dir / "scene_0001.wav").read_bytes(),
                b"previous audio",
            )
            self.assertFalse((audio_dir / "partial.wav").exists())
            self.assertEqual(list(root.glob(".audios.*.backup")), [])

    def test_previous_audio_is_removed_only_after_successful_regeneration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio_dir = root / "audios"
            audio_dir.mkdir()
            (audio_dir / "scene_0001.wav").write_bytes(b"previous audio")

            class FakePipeline:
                AUDIOS_DIR = "audios"

                def get_idea_path(self, idea_id: int) -> Path:
                    return root

                @preserve_audios_on_force
                def regenerate(self, idea_id: int, force: bool = False) -> None:
                    new_dir = self.get_idea_path(idea_id) / self.AUDIOS_DIR
                    new_dir.mkdir(exist_ok=True)
                    (new_dir / "scene_0001.wav").write_bytes(b"new audio")

            FakePipeline().regenerate(1, force=True)

            self.assertEqual(
                (audio_dir / "scene_0001.wav").read_bytes(),
                b"new audio",
            )
            self.assertEqual(list(root.glob(".audios.*.backup")), [])


class ScriptReplacementTests(unittest.TestCase):
    def _make_pipeline(self, root: Path) -> Pipeline:
        pipeline = Pipeline(
            out_base=root / "out",
            resource_base=root / "resources",
            orientation=VideoOrientation.SHORT,
        )
        pipeline.store.add(
            IdeaRaw(
                id=1,
                title="Old title",
                category="finance",
                state=State.COMPLETED,
            )
        )
        return pipeline

    def _add_old_outputs(self, idea_dir: Path) -> None:
        for folder in ("audios", "videos", "editions"):
            asset_dir = idea_dir / folder
            asset_dir.mkdir()
            (asset_dir / "stale.bin").write_bytes(folder.encode("utf-8"))
        (idea_dir / "old-final.mp4").write_bytes(b"old final")
        (idea_dir / "script.json").write_text('{"old":true}', encoding="utf-8")

    def _form(self) -> ScriptFormData:
        return ScriptFormData(
            idea="A new video idea",
            style="stickman",
            category="horror",
            tone="dramatic",
            aspect_ratio="9:16",
        )

    def test_regenerating_script_invalidates_old_derived_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pipeline = self._make_pipeline(root)
            idea_dir = pipeline.get_idea_path(1)
            self._add_old_outputs(idea_dir)

            with patch.object(
                pipeline,
                "_generate_from_form",
                return_value=(make_script(), "New title", "horror"),
            ):
                pipeline.step1_generate_story(1, self._form())

            saved = pipeline.store.get_by_id(1)
            self.assertEqual(saved.state, State.SCRIPT_GENERATED)
            self.assertEqual(saved.title, "New title")
            self.assertFalse((idea_dir / "audios").exists())
            self.assertFalse((idea_dir / "videos").exists())
            self.assertFalse((idea_dir / "editions").exists())
            self.assertEqual(list(idea_dir.glob("*.mp4")), [])
            self.assertEqual(list(idea_dir.glob(".*.backup")), [])

    def test_failed_script_metadata_commit_restores_old_script_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pipeline = self._make_pipeline(root)
            idea_dir = pipeline.get_idea_path(1)
            self._add_old_outputs(idea_dir)
            store = pipeline.store

            with patch.object(
                pipeline,
                "_generate_from_form",
                return_value=(make_script(), "New title", "horror"),
            ), patch.object(
                store,
                "save",
                side_effect=OSError("simulated metadata persistence failure"),
            ):
                with self.assertRaisesRegex(
                    OSError, "simulated metadata persistence failure"
                ):
                    pipeline.step1_generate_story(1, self._form())

            self.assertEqual(
                (idea_dir / "script.json").read_text(encoding="utf-8"),
                '{"old":true}',
            )
            for folder in ("audios", "videos", "editions"):
                self.assertEqual(
                    (idea_dir / folder / "stale.bin").read_bytes(),
                    folder.encode("utf-8"),
                )
            self.assertEqual(
                (idea_dir / "old-final.mp4").read_bytes(),
                b"old final",
            )
            self.assertEqual(list(idea_dir.glob(".*.backup")), [])


if __name__ == "__main__":
    unittest.main()
