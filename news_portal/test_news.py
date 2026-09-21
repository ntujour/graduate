import copy
import json
import tempfile
import unittest
from pathlib import Path

from .import_local import build_seed
from .model import release_files
from .store import Conflict, LocalStore, publish, save_draft


class NewsPortalTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = LocalStore(Path(self.temp.name))
        self.seed = build_seed()
        save_draft(self.store, self.seed, "0")
        _, self.token = self.store.read("draft.json")

    def tearDown(self):
        self.temp.cleanup()

    def test_import_and_release_indexes(self):
        self.assertEqual(len(self.seed["records"]), 86)
        _, files = release_files(self.seed)
        self.assertEqual(len(files["index.zh.json"]["items"]), 20)
        self.assertEqual(len(files["index.en.json"]["items"]), 6)
        self.assertEqual(len(files["index.activities.zh.json"]["items"]), 60)
        self.assertEqual(len(files["index.activities.en.json"]["items"]), 0)
        for lang in ("zh", "en"):
            encoded = json.dumps(files[f"index.{lang}.json"])
            self.assertNotIn("bodyHtml", encoded)
            self.assertLess(len(encoded.encode()), 30000)

    def test_draft_backup_conflict_and_atomic_publish(self):
        first = publish(self.store, self.token, "0")
        _, public_token = self.store.read("public/current.json")
        edited = copy.deepcopy(self.seed)
        edited["records"][0]["locales"]["zh"]["title"] = "只在草稿"
        save_draft(self.store, edited, self.token)
        self.assertEqual(self.store.read("public/current.json")[0], first)
        with self.assertRaises(Conflict):
            save_draft(self.store, self.seed, self.token)
        _, latest = self.store.read("draft.json")
        second = publish(self.store, latest, public_token)
        self.assertNotEqual(first["release"], second["release"])
        detail, _ = self.store.read(f"public/releases/{second['release']}/{edited['records'][0]['id']}.zh.json")
        self.assertEqual(detail["title"], "只在草稿")
        self.assertTrue(list((self.store.root / "backups").glob("*.json")))


if __name__ == "__main__":
    unittest.main()
