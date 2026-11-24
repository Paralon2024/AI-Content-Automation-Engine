import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from api.routers import config as config_router


class GeminiKeyConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"
        self.previous_key = os.environ.pop("GEMINI_API_KEY", None)
        self.path_patch = patch.object(config_router, "CONFIG_PATH", self.config_path)
        self.path_patch.start()

    def tearDown(self) -> None:
        self.path_patch.stop()
        os.environ.pop("GEMINI_API_KEY", None)
        if self.previous_key is not None:
            os.environ["GEMINI_API_KEY"] = self.previous_key
        self.temp_dir.cleanup()

    def test_key_is_persisted_and_loaded_from_file(self) -> None:
        result = config_router.set_gemini_key(config_router.KeyPayload(key="  test-key  "))

        self.assertEqual(result, {"ok": True})
        self.assertEqual(json.loads(self.config_path.read_text(encoding="utf-8")), {
            "gemini_api_key": "test-key"
        })

        os.environ.pop("GEMINI_API_KEY", None)
        self.assertEqual(config_router.get_gemini_key(), "test-key")
        self.assertEqual(config_router.check_gemini_key()["source"], "file")

    def test_failed_atomic_replace_preserves_previous_config(self) -> None:
        original = {"gemini_api_key": "previous-key", "other_setting": "preserved"}
        self.config_path.write_text(json.dumps(original), encoding="utf-8")

        with patch("api.routers.config.os.replace", side_effect=OSError("simulated disk failure")):
            with self.assertRaises(HTTPException) as raised:
                config_router._save({"gemini_api_key": "new-key"})

        self.assertEqual(raised.exception.status_code, 500)
        self.assertEqual(json.loads(self.config_path.read_text(encoding="utf-8")), original)
        self.assertEqual(list(self.config_path.parent.glob(".config.json.*.tmp")), [])

    def test_delete_removes_saved_key_and_environment_value(self) -> None:
        self.config_path.write_text(
            json.dumps({"gemini_api_key": "saved-key", "other_setting": "preserved"}),
            encoding="utf-8",
        )
        os.environ["GEMINI_API_KEY"] = "saved-key"

        result = config_router.delete_gemini_key()

        self.assertEqual(result, {"ok": True})
        self.assertNotIn("GEMINI_API_KEY", os.environ)
        self.assertEqual(
            json.loads(self.config_path.read_text(encoding="utf-8")),
            {"other_setting": "preserved"},
        )


if __name__ == "__main__":
    unittest.main()
