import asyncio
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from starlette.datastructures import UploadFile

from api.routers import music as music_router


def upload(name: str, payload: bytes) -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(payload))


class MusicUploadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.library = Path(self.temp_dir.name) / "music"
        self.library.mkdir()
        self.library_patch = patch.object(music_router, "_LIBRARY", self.library)
        self.library_patch.start()

    def tearDown(self) -> None:
        self.library_patch.stop()
        self.temp_dir.cleanup()

    def test_upload_installs_all_tracks_and_replaces_existing_files(self) -> None:
        (self.library / "existing.mp3").write_bytes(b"old content")

        result = asyncio.run(
            music_router.upload_tracks(
                [
                    upload("existing.mp3", b"new content"),
                    upload("ambient.wav", b"wave content"),
                ], folder=""
            )
        )

        self.assertEqual(result["uploaded"], ["existing.mp3", "ambient.wav"])
        self.assertEqual((self.library / "existing.mp3").read_bytes(), b"new content")
        self.assertEqual((self.library / "ambient.wav").read_bytes(), b"wave content")
        self.assertEqual(list(self.library.glob(".music-upload-*")), [])

    def test_duplicate_filenames_are_rejected_before_any_write(self) -> None:
        existing = self.library / "same.mp3"
        existing.write_bytes(b"keep this")

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                music_router.upload_tracks(
                    [
                        upload("same.mp3", b"first"),
                        upload("SAME.MP3", b"second"),
                    ], folder=""
                )
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(existing.read_bytes(), b"keep this")
        self.assertEqual(list(self.library.glob(".music-upload-*")), [])

    def test_oversized_later_file_does_not_partially_install_batch(self) -> None:
        existing = self.library / "keep.mp3"
        existing.write_bytes(b"previous version")

        with patch.object(music_router, "_MAX_AUDIO_UPLOAD_BYTES", 3):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    music_router.upload_tracks(
                        [
                            upload("new.mp3", b"ok"),
                            upload("too-large.wav", b"four"),
                        ], folder=""
                    )
                )

        self.assertEqual(raised.exception.status_code, 413)
        self.assertEqual(existing.read_bytes(), b"previous version")
        self.assertFalse((self.library / "new.mp3").exists())
        self.assertEqual(list(self.library.glob(".music-upload-*")), [])

    def test_install_failure_rolls_back_every_replaced_track(self) -> None:
        first = self.library / "first.mp3"
        second = self.library / "second.wav"
        first.write_bytes(b"old first")
        second.write_bytes(b"old second")
        original_replace = Path.replace

        def fail_second_install(source: Path, target: Path):
            target_path = Path(target)
            if source.name == "upload-0001.wav" and target_path.name == "second.wav":
                raise OSError("simulated music install failure")
            return original_replace(source, target)

        with patch.object(Path, "replace", new=fail_second_install):
            with self.assertRaisesRegex(OSError, "simulated music install failure"):
                asyncio.run(
                    music_router.upload_tracks(
                        [
                            upload("first.mp3", b"new first"),
                            upload("second.wav", b"new second"),
                        ], folder=""
                    )
                )

        self.assertEqual(first.read_bytes(), b"old first")
        self.assertEqual(second.read_bytes(), b"old second")
        self.assertEqual(list(self.library.glob(".music-upload-*")), [])

    def test_cannot_delete_music_library_root_through_dot_paths(self) -> None:
        sentinel = self.library / "important.mp3"
        sentinel.write_bytes(b"keep this")

        for path in (".", "./"):
            with self.subTest(path=path):
                with self.assertRaises(HTTPException) as raised:
                    music_router.delete_entry(path)

                self.assertEqual(raised.exception.status_code, 400)
                self.assertTrue(sentinel.is_file())
                self.assertEqual(sentinel.read_bytes(), b"keep this")

    def test_rejects_path_traversal_folder(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(
                music_router.upload_tracks([upload("track.mp3", b"audio")], folder="../outside")
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertFalse((self.library.parent / "outside").exists())


if __name__ == "__main__":
    unittest.main()
