import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel

from tools.common.storage_folder import FolderStore


class TestRecord(BaseModel):
    id: int
    state: str


class FolderStoreTests(unittest.TestCase):
    def test_failed_atomic_replace_preserves_previous_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = FolderStore(Path(temp_dir), TestRecord)
            record = store.add(TestRecord(id=1, state="before"))
            meta_path = Path(temp_dir) / "idea_000001" / "meta.json"
            original_content = meta_path.read_text(encoding="utf-8")

            record.state = "after"
            with patch(
                "tools.common.storage_folder.os.replace",
                side_effect=OSError("simulated disk failure"),
            ):
                with self.assertRaisesRegex(OSError, "simulated disk failure"):
                    store.save(record)

            self.assertEqual(meta_path.read_text(encoding="utf-8"), original_content)
            self.assertEqual(
                list(meta_path.parent.glob(".meta.json.*.tmp")),
                [],
                "temporary metadata files should be cleaned up after failure",
            )


if __name__ == "__main__":
    unittest.main()
