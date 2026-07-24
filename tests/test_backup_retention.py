from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.backup_service import rotate_backup_archives


class BackupRetentionTests(unittest.TestCase):
    def test_rotation_keeps_only_official_archives_and_preserves_other_files(self):
        with tempfile.TemporaryDirectory(prefix="checklist-backup-retention-") as temporary:
            folder = Path(temporary)
            for index in range(3):
                archive = folder / f"backup-checklist-20260724-12010{index}.zip"
                archive.write_bytes(b"backup")
                archive.touch()
            unrelated = folder / "nao-remover.txt"
            unrelated.write_text("preservar", encoding="utf-8")

            result = rotate_backup_archives(folder, keep_count=2)

            self.assertEqual(result["kept"], 2)
            self.assertEqual(len(result["removed"]), 1)
            self.assertTrue(unrelated.exists())
            self.assertEqual(len(list(folder.glob("backup-checklist-*.zip"))), 2)


if __name__ == "__main__":
    unittest.main()
