import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from malariapulse.auth import create_remember_token
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

    def test_login_exposes_remember_me_and_password_visibility(self):
        app = self._new_app()
        self.assertFalse(app.checkbox(key="login-remember").value)
        self.assertFalse(app.checkbox(key="login-show-password").value)
        self.assertEqual(app.text_input(key="login-password").proto.type, 1)

        app.text_input(key="login-password").set_value("DemoPulse!2026")
        app.checkbox(key="login-show-password").check().run(timeout=45)

        self.assertFalse(app.exception)
        self.assertEqual(app.text_input(key="login-password").proto.type, 0)
        self.assertEqual(app.text_input(key="login-password").value, "DemoPulse!2026")

    def test_logout_clears_the_authenticated_session(self):
        app = self._login(self._new_app())
        logout = app.button(key="logout")
        self.assertEqual(logout.proto.type, "primary")
        self.assertEqual(logout.proto.icon, "")
        logout.click().run(timeout=45)

        self.assertFalse(app.exception)
        self.assertFalse(app.radio)
        self.assertEqual(app.text_input(key="login-username").value, "")

    def test_forget_request_wins_over_stale_remember_token_and_cleans_url(self):
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(app_path))
        app.query_params["_mp_remember"] = create_remember_token(
            "admin@malariapulse.demo",
            "malariapulse-demo:DemoPulse!2026",
        )
        app.query_params["_mp_forget"] = "1"
        app.run(timeout=45)

        self.assertFalse(app.exception)
        self.assertFalse(app.radio)
        self.assertEqual(app.query_params, {})

    def test_overview_exposes_clear_operational_sections(self):
        app = self._login(self._new_app())
        headings = [item.value for item in app.subheader]
        for expected in (
            "County transmission pattern",
            "County risk watchlist",
            "Clinical severity and priority groups",
            "Climate and prevention context",
            "Commodity readiness",
        ):
            self.assertIn(expected, headings)
        self.assertGreaterEqual(len(app.get("dataframe")), 4)
        self.assertGreaterEqual(len(app.get("vega_lite_chart")), 4)

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

    def test_intervention_page_supports_manual_and_file_entry(self):
        app = self._app_on_page("Intervention data")
        self.assertEqual([tab.label for tab in app.tabs], ["Manual entry", "File upload"])
        self.assertEqual(app.get("file_uploader")[0].key, "intervention-inline-uploader")

        app.number_input[0].set_value(79.0)
        app.button(key="FormSubmitter:intervention-form-nyakach-north-Save intervention data").click().run(timeout=45)

        self.assertFalse(app.exception)
        saved = json.loads(self.operational_path.read_text(encoding="utf-8"))
        zone = next(item for item in saved["zones"] if item["id"] == "nyakach-north")
        self.assertEqual(zone["interventions"]["llinUsePct"], 79.0)
        self.assertTrue(any("saved successfully" in message.value for message in app.success))

    def test_ai_review_exposes_a_subcounty_pdf_download(self):
        app = self._app_on_page("AI analyst")
        dataset = core.load_seed_data()
        app.session_state["ai_result"] = {
            "review": {
                "headline": "Elevated signal requires verification",
                "overallRisk": "high",
                "executiveSummary": "One zone needs rapid validation while response actions remain drafts.",
                "keyFindings": [
                    {
                        "title": "Cases are rising",
                        "evidence": "Nyakach North reports 68 latest-week cases.",
                        "implication": "Verify facility reports before escalation.",
                    }
                ],
                "priorities": [
                    {
                        "rank": 1,
                        "action": "Verify reports",
                        "owner": "Surveillance lead",
                        "timeframe": "Within 4 hours",
                        "rationale": "Confirm the aggregate signal.",
                        "requiresApproval": False,
                    }
                ],
                "dataQuality": {
                    "freshness": "Current reporting week",
                    "completeness": "94%",
                    "concerns": ["Check late reports"],
                },
                "limitations": ["This signal is not an outbreak declaration."],
            },
            "model": "gemini-3.8-flash",
            "responseId": "resp_test",
            "generatedAt": "2026-10-15T09:00:00.000Z",
            "sourceUpdatedAt": dataset["metadata"]["updatedAt"],
            "scope": {
                "type": "zone",
                "id": "nyakach-north",
                "label": "Nyakach North",
                "subcounty": "Nyakach",
            },
        }
        app.run(timeout=45)

        self.assertFalse(app.exception)
        downloads = app.get("download_button")
        self.assertEqual(len(downloads), 1)
        self.assertEqual(downloads[0].label, "Download AI report")
        self.assertEqual(downloads[0].key, "download-ai-report")
        self.assertTrue(any("Nyakach Sub-County letterhead" in caption.value for caption in app.caption))


if __name__ == "__main__":
    unittest.main()
