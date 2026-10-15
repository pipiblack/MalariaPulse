import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import malariapulse.core as core


class StreamlitDataEntryTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        temporary_path = Path(self.temporary_directory.name)
        self.seed_path = temporary_path / "seed.json"
        self.operational_path = temporary_path / "operational.json"
        self.seed_path.write_text(json.dumps(core.load_seed_data()), encoding="utf-8")

        self.seed_patch = patch.object(core, "SEED_PATH", self.seed_path)
        self.operational_patch = patch.object(core, "OPERATIONAL_PATH", self.operational_path)
        self.seed_patch.start()
        self.operational_patch.start()
        self.addCleanup(self.seed_patch.stop)
        self.addCleanup(self.operational_patch.stop)

    def _new_app(self) -> AppTest:
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=45)
        self.assertFalse(app.exception)
        return app

    def _login(self, app: AppTest) -> AppTest:
        app.text_input(key="login-username").set_value("admin@malariapulse.demo")
        app.text_input(key="login-password").set_value("DemoPulse!2026")
        app.button[0].click().run(timeout=45)
        self.assertFalse(app.exception)
        self.assertTrue(app.radio)
        return app

    def _app_on_page(self, page: str) -> AppTest:
        app = self._login(self._new_app())
        app.radio(key="workspace-page").set_value(page).run(timeout=45)
        self.assertFalse(app.exception)
        return app

    def test_login_rejects_invalid_credentials(self):
        app = self._new_app()
        self.assertFalse(app.radio)
        app.text_input(key="login-username").set_value("wrong@example.com")
        app.text_input(key="login-password").set_value("incorrect")
        app.button[0].click().run(timeout=45)

        self.assertFalse(app.exception)
        self.assertFalse(app.radio)
        self.assertTrue(any("incorrect" in message.value for message in app.error))

    def test_logout_clears_the_authenticated_session(self):
        app = self._login(self._new_app())
        app.button(key="logout").click().run(timeout=45)

        self.assertFalse(app.exception)
        self.assertFalse(app.radio)
        self.assertEqual(app.text_input(key="login-username").value, "")

    def test_clinical_save_persists_and_confirms_after_rerun(self):
        app = self._app_on_page("Clinical data")
        self.assertEqual([tab.label for tab in app.tabs], ["Manual entry", "File upload"])
        self.assertEqual(app.get("file_uploader")[0].key, "clinical-inline-uploader")

        app.number_input(key="clinical-nyakach-north-5").set_value(82)
        app.button(key="FormSubmitter:clinical-form-nyakach-north-Save clinical data").click().run(timeout=45)

        self.assertFalse(app.exception)
        saved = json.loads(self.operational_path.read_text(encoding="utf-8"))
        zone = next(item for item in saved["zones"] if item["id"] == "nyakach-north")
        self.assertEqual(zone["weeklyCases"][-1], 82)
        self.assertTrue(any("saved successfully" in message.value for message in app.success))

    def test_environmental_save_persists_and_confirms_after_rerun(self):
        app = self._app_on_page("Environmental data")
        self.assertEqual([tab.label for tab in app.tabs], ["Manual entry", "File upload"])
        self.assertEqual(app.get("file_uploader")[0].key, "environment-inline-uploader")

        app.number_input[0].set_value(91.5)
        app.button(key="FormSubmitter:environment-form-nyakach-north-Save environmental data").click().run(timeout=45)

        self.assertFalse(app.exception)
        saved = json.loads(self.operational_path.read_text(encoding="utf-8"))
        zone = next(item for item in saved["zones"] if item["id"] == "nyakach-north")
        self.assertEqual(zone["environment"]["rainfall7dMm"], 91.5)
        self.assertTrue(any("saved successfully" in message.value for message in app.success))


if __name__ == "__main__":
    unittest.main()
