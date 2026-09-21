"""Regression checks for the bilingual migration and publication boundary."""
import copy
import json
import tempfile
import unittest
from io import BytesIO
from html.parser import HTMLParser
from pathlib import Path

from flask import Flask
from PIL import Image

from .model import release_files, profile, version
from .routes import register_faculty
from .store import LocalStore, Conflict, publish, save_draft

SEED = Path(__file__).resolve().parents[1] / "output/faculty-pilot/draft.json"


class Text(HTMLParser):
    def __init__(self, raw):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.feed(raw)

    def handle_data(self, value):
        self.parts.append(value)


class FacultyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LocalStore(self.temp.name)
        self.seed = json.loads(SEED.read_text())
        save_draft(self.store, self.seed, "0")
        _, self.token = self.store.read("draft.json")

    def test_complete_bilingual_import(self):
        self.assertEqual(len(self.seed["records"]), 30)
        for r in self.seed["records"]:
            for lang in ("zh", "en"):
                source = r["importSource"][lang + "HtmlBeforeSanitization"]
                actual = profile(r, lang)["bodyHtml"]
                self.assertEqual("".join(Text(source).parts), "".join(Text(actual).parts), (r["id"], lang))

    def test_indexes_have_no_biographies_or_private_imports(self):
        _, files = release_files(self.seed)
        self.assertEqual(len(files), 39)
        self.assertEqual(len(files["index.zh.json"]["items"]), 30)
        self.assertEqual(len(files["index.en.json"]["items"]), 7)
        self.assertTrue(all(item["category"] == "fulltime" for item in files["index.en.json"]["items"]))
        for lang in ("zh", "en"):
            index = files["index." + lang + ".json"]
            self.assertNotIn("bodyHtml", json.dumps(index))
            self.assertLess(len(json.dumps(index).encode()), 20000)
        for data in files.values():
            self.assertNotIn("importSource", data)

    def test_hidden_languages_do_not_publish_profile_files(self):
        edited = copy.deepcopy(self.seed)
        adjunct = next(r for r in edited["records"] if r["category"] == "parttime")
        fulltime = next(r for r in edited["records"] if r["category"] == "fulltime")
        adjunct["locales"]["zh"]["visible"] = False
        adjunct["locales"]["en"]["visible"] = True
        fulltime["locales"]["en"]["visible"] = False
        _, files = release_files(edited)
        zh_ids = {item["id"] for item in files["index.zh.json"]["items"]}
        en_ids = {item["id"] for item in files["index.en.json"]["items"]}
        self.assertNotIn(adjunct["id"], zh_ids)
        self.assertIn(adjunct["id"], en_ids)
        self.assertNotIn(fulltime["id"], en_ids)
        self.assertNotIn(f"{adjunct['id']}.zh.json", files)
        self.assertIn(f"{adjunct['id']}.en.json", files)
        self.assertIn(f"{fulltime['id']}.zh.json", files)
        self.assertNotIn(f"{fulltime['id']}.en.json", files)

    def test_visibility_must_be_boolean(self):
        edited = copy.deepcopy(self.seed)
        edited["records"][0]["locales"]["zh"]["visible"] = "false"
        with self.assertRaisesRegex(ValueError, "顯示狀態"):
            release_files(edited)

    def test_additional_category_keeps_one_directory_item(self):
        edited = copy.deepcopy(self.seed)
        adjunct = next(r for r in edited["records"] if r["category"] == "parttime")
        adjunct["additionalCategories"] = ["retired"]
        _, files = release_files(edited)
        matches = [item for item in files["index.zh.json"]["items"] if item["id"] == adjunct["id"]]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["category"], "parttime")
        self.assertEqual(matches[0]["categories"], ["parttime", "retired"])
        self.assertEqual(files[f"{adjunct['id']}.zh.json"]["categories"], ["parttime", "retired"])

    def test_additional_category_is_validated(self):
        edited = copy.deepcopy(self.seed)
        edited["records"][0]["additionalCategories"] = ["unknown"]
        with self.assertRaisesRegex(ValueError, "額外列入分類"):
            release_files(edited)

    def test_new_hidden_joint_faculty_can_be_saved_then_published(self):
        edited = copy.deepcopy(self.seed)
        created = {
            "id": "new-joint-professor",
            "order": 502,
            "category": "joint",
            "additionalCategories": [],
            "shared": {"email": "", "phone": "", "office": "", "photo": "", "website": ""},
            "locales": {
                "zh": {"name": "新合聘教師", "title": "", "bodyHtml": "", "expertise": "", "originalUrl": "", "visible": False},
                "en": {"name": "New Joint Professor", "title": "", "bodyHtml": "", "expertise": "", "originalUrl": "", "visible": False},
            },
        }
        edited["records"].append(created)
        save_draft(self.store, edited, self.token)
        actual, _ = self.store.read("draft.json")
        self.assertNotIn("importSource", actual["records"][-1])
        _, files = release_files(actual)
        self.assertNotIn("new-joint-professor.zh.json", files)
        self.assertNotIn("new-joint-professor", {item["id"] for item in files["index.zh.json"]["items"]})

    def test_visible_new_faculty_requires_photo_and_title(self):
        edited = copy.deepcopy(self.seed)
        created = {
            "id": "new-joint-professor",
            "order": 502,
            "category": "joint",
            "additionalCategories": [],
            "shared": {"email": "", "phone": "", "office": "", "photo": "", "website": ""},
            "locales": {
                "zh": {"name": "新合聘教師", "title": "合聘教授", "bodyHtml": "", "expertise": "", "originalUrl": "", "visible": True},
                "en": {"name": "New Joint Professor", "title": "Joint Professor", "bodyHtml": "", "expertise": "", "originalUrl": "", "visible": False},
            },
        }
        edited["records"].append(created)
        with self.assertRaisesRegex(ValueError, "請先上傳照片"):
            release_files(edited)
        created["shared"]["photo"] = "https://example.com/faculty.jpg"
        created["locales"]["zh"]["title"] = ""
        with self.assertRaisesRegex(ValueError, "職稱"):
            release_files(edited)

    def test_draft_does_not_publish_and_conflicts_are_rejected(self):
        first = publish(self.store, self.token, "0")
        _, public_token = self.store.read("public/current.json")
        edited = copy.deepcopy(self.seed)
        edited["records"][0]["shared"]["phone"] = "test-only"
        save_draft(self.store, edited, self.token)
        self.assertEqual(self.store.read("public/current.json")[0], first)
        with self.assertRaises(Conflict):
            save_draft(self.store, self.seed, self.token)
        with self.assertRaises(Conflict):
            publish(self.store, self.token, public_token)
        _, latest = self.store.read("draft.json")
        second = publish(self.store, latest, public_token)
        self.assertNotEqual(first["release"], second["release"])
        for lang in ("zh", "en"):
            item, _ = self.store.read(f"public/releases/{second['release']}/{edited['records'][0]['id']}.{lang}.json")
            self.assertEqual(item["phone"], "test-only")
        self.assertTrue(list((self.store.root / "backups").glob("*.json")))

    def test_failed_upload_keeps_previous_release(self):
        first = publish(self.store, self.token, "0")
        _, public_token = self.store.read("public/current.json")
        edited = copy.deepcopy(self.seed)
        edited["records"][0]["locales"]["zh"]["title"] = "changed"
        save_draft(self.store, edited, self.token)
        _, token = self.store.read("draft.json")
        original = self.store.write
        def fail(key, *args):
            if key.endswith(".en.json"):
                raise OSError("simulated network failure")
            return original(key, *args)
        self.store.write = fail
        with self.assertRaises(OSError):
            publish(self.store, token, public_token)
        self.assertEqual(self.store.read("public/current.json")[0], first)

    def test_hidden_profile_cleanup_waits_for_successful_pointer_switch(self):
        first = publish(self.store, self.token, "0")
        _, public_token = self.store.read("public/current.json")
        edited = copy.deepcopy(self.seed)
        record = edited["records"][0]
        record["locales"]["zh"]["visible"] = False
        old_profile = (
            self.store.root / "public" / "releases" / first["release"] /
            f"{record['id']}.zh.json"
        )
        self.assertTrue(old_profile.exists())
        save_draft(self.store, edited, self.token)
        _, draft_token = self.store.read("draft.json")
        original_write = self.store.write

        def reject_pointer(key, *args):
            if key == "public/current.json":
                raise Conflict("simulated concurrent publish")
            return original_write(key, *args)

        self.store.write = reject_pointer
        with self.assertRaises(Conflict):
            publish(self.store, draft_token, public_token)
        self.assertEqual(self.store.read("public/current.json")[0], first)
        self.assertTrue(old_profile.exists())

    def test_hidden_profiles_are_pruned_only_after_pointer_switch(self):
        first = publish(self.store, self.token, "0")
        _, public_token = self.store.read("public/current.json")
        edited = copy.deepcopy(self.seed)
        record = edited["records"][0]
        record["locales"]["zh"]["visible"] = False
        old_profile = (
            self.store.root / "public" / "releases" / first["release"] /
            f"{record['id']}.zh.json"
        )
        save_draft(self.store, edited, self.token)
        _, draft_token = self.store.read("draft.json")
        observed_pointers = []
        original_cleanup = self.store.remove_public_profiles

        def capture_cleanup(names):
            observed_pointers.append(self.store.read("public/current.json")[0])
            return original_cleanup(names)

        self.store.remove_public_profiles = capture_cleanup
        second = publish(self.store, draft_token, public_token)
        self.assertEqual(observed_pointers, [second])
        self.assertFalse(old_profile.exists())

    def test_language_edits_do_not_replace_other_language(self):
        original = copy.deepcopy(self.seed["records"][0]["locales"]["en"])
        self.seed["records"][0]["locales"]["zh"]["bodyHtml"] += "<p>中文新增</p>"
        save_draft(self.store, self.seed, self.token)
        actual, _ = self.store.read("draft.json")
        self.assertEqual(actual["records"][0]["locales"]["en"], original)

    def test_former_practical_category_is_supported(self):
        edited = copy.deepcopy(self.seed)
        edited["records"][0]["category"] = "former_practical"
        save_draft(self.store, edited, self.token)
        actual, _ = self.store.read("draft.json")
        self.assertEqual(actual["records"][0]["category"], "former_practical")
        self.assertEqual(profile(actual["records"][0], "zh")["category"], "former_practical")
        invalid = copy.deepcopy(actual)
        invalid["records"][0]["category"] = "unknown"
        with self.assertRaisesRegex(ValueError, "排序與分類格式錯誤"):
            save_draft(self.store, invalid, version(actual))

    def test_published_html_removes_executable_markup(self):
        r = copy.deepcopy(self.seed["records"][0])
        r["locales"]["zh"]["bodyHtml"] = '<p onclick="bad()"><em>Journal</em><a href="javascript:bad()">link</a><img src="x" onerror="bad()"></p>'
        body = profile(r, "zh")["bodyHtml"]
        self.assertNotIn("onclick", body)
        self.assertNotIn("onerror", body)
        self.assertNotIn("javascript:", body)
        self.assertIn("<em>Journal</em>", body)

    def test_photo_upload_is_validated_resized_and_stored(self):
        app = Flask(__name__)
        register_faculty(app, lambda: None, self.store)
        client = app.test_client()
        source = BytesIO()
        Image.new("RGBA", (1800, 900), (20, 80, 140, 128)).save(source, "PNG")
        response = client.post(
            "/faculty/api/photo/ji-lung-hsieh",
            data={"photo": (BytesIO(source.getvalue()), "portrait.png")},
            headers={"X-Faculty-Request": "1"},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        result = response.get_json()
        self.assertEqual((result["width"], result["height"]), (1600, 800))
        self.assertRegex(result["url"], r"^http://localhost/faculty/media/ji-lung-hsieh-[a-f0-9]{20}\.jpg$")
        edited = copy.deepcopy(self.seed)
        edited["records"][0]["shared"]["photo"] = result["url"]
        save_draft(self.store, edited, self.token)
        stored = self.store.root / "public/media" / result["url"].rsplit("/", 1)[-1]
        with Image.open(stored) as uploaded:
            self.assertEqual(uploaded.format, "JPEG")
            self.assertEqual(uploaded.size, (1600, 800))
        rejected = client.post(
            "/faculty/api/photo/ji-lung-hsieh",
            data={"photo": (BytesIO(b"not an image"), "fake.jpg")},
            headers={"X-Faculty-Request": "1"},
        )
        self.assertEqual(rejected.status_code, 400)
        blocked = client.post(
            "/faculty/api/photo/ji-lung-hsieh",
            data={"photo": (BytesIO(source.getvalue()), "portrait.png")},
        )
        self.assertEqual(blocked.status_code, 403)

    def test_admin_auth_and_cross_origin_write_boundary(self):
        app = Flask(__name__)
        register_faculty(app, lambda: ("Forbidden", 403), self.store)
        self.assertEqual(app.test_client().get("/faculty/api/draft").status_code, 403)
        app = Flask(__name__)
        register_faculty(app, lambda: None, self.store)
        client = app.test_client()
        self.assertEqual(client.put("/faculty/api/draft", json={}).status_code, 403)
        response = client.get("/faculty/api/preview/ji-lung-hsieh/zh")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("importSource", response.json)
        self.assertEqual(client.get("/faculty/feed/../draft.json").status_code, 404)


if __name__ == "__main__":
    unittest.main()
