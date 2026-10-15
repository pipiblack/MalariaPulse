import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

import malariapulse.core as core
from malariapulse.ai import create_ai_review
from malariapulse.core import (
    apply_parsed_import,
    assess_zone,
    build_network_snapshot,
    load_seed_data,
    parse_data_import,
    plan_resources,
    run_response_cycle,
)
from malariapulse.report import ai_report_filename, build_ai_report_pdf, report_jurisdiction


SAMPLE_REVIEW = {
    "headline": "Elevated signal requires verification",
    "overallRisk": "high",
    "executiveSummary": "One zone needs rapid validation while stock movements remain draft actions.",
    "keyFindings": [
        {
            "title": "Cases are rising",
            "evidence": "Nyakach North reports 68 latest-week cases.",
            "implication": "Verify the facility reports before escalation.",
        }
    ],
    "priorities": [
        {
            "rank": 1,
            "action": "Verify reports",
            "owner": "Surveillance lead",
            "timeframe": "Within 4 hours",
            "rationale": "Confirm the signal.",
            "requiresApproval": False,
        }
    ],
    "dataQuality": {"freshness": "Current week", "completeness": "94%", "concerns": ["Check late reports"]},
    "limitations": ["This signal is not an outbreak declaration."],
}


class CoreTests(unittest.TestCase):
    def test_seed_risk_and_snapshot_are_consistent(self):
        dataset = load_seed_data()
        assessment = assess_zone(dataset["zones"][0], dataset["metadata"])
        snapshot = build_network_snapshot(dataset)
        self.assertEqual(assessment["zoneId"], "nyakach-north")
        self.assertGreaterEqual(assessment["score"], 60)
        self.assertEqual(snapshot["summary"]["zonesMonitored"], len(dataset["zones"]))
        self.assertEqual(snapshot["assessments"][0]["score"], max(item["score"] for item in snapshot["assessments"]))
        self.assertGreater(snapshot["summary"]["currentCases"], 0)
        self.assertGreater(snapshot["summary"]["positivityPct"], 0)
        self.assertIn("clinicalContext", assessment)
        self.assertIn("rainfall30dMm", assessment["environmentContext"])
        self.assertIn("llinUsePct", assessment["interventionContext"])

    def test_response_cycle_has_human_gate(self):
        cycle = run_response_cycle(load_seed_data(), zone_id="nyakach-north", now="2026-10-14T08:00:00.000Z")
        self.assertEqual(cycle["status"], "pending_approval")
        self.assertEqual([item["agent"] for item in cycle["audit"][:3]], ["Surveillance", "Supply", "Community"])
        plan = plan_resources(load_seed_data(), "nyakach-north", cycle["assessments"][0])
        self.assertTrue(plan["requiresApproval"])
        self.assertIn("three weeks", plan["method"])
        self.assertTrue(all("receiverWeeksAfter" in move for move in plan["recommendations"]))
        advisory = cycle["interventions"][0]["advisories"]["messages"][0]
        self.assertIn("purpose", advisory)
        self.assertEqual(len(advisory["reviewChecklist"]), 3)

    def test_clinical_csv_is_validated_and_applied_atomically(self):
        dataset = load_seed_data()
        content = (
            "zone_id,reporting_week,week_1_cases,week_2_cases,week_3_cases,week_4_cases,week_5_cases,week_6_cases,tests,positive_tests\n"
            "nyakach-north,2026-W42,20,22,25,31,49,72,200,72\n"
        ).encode()
        preview = parse_data_import("clinical", "clinical.csv", content, dataset)
        self.assertTrue(preview["canApply"])
        updated = apply_parsed_import(dataset, preview)
        self.assertEqual(updated["zones"][0]["weeklyCases"][-1], 72)
        self.assertEqual(dataset["zones"][0]["weeklyCases"][-1], 68)

    def test_identifying_columns_are_rejected(self):
        content = b"zone_id,rainfall_7d_mm,temperature_c,humidity_pct,patient_name\nkisumu-west,61,27,68,Example Person"
        preview = parse_data_import("environment", "unsafe.csv", content, load_seed_data())
        self.assertFalse(preview["canApply"])
        self.assertIn("Patient-identifying columns", " ".join(preview["fileErrors"]))

    def test_semicolon_delimited_txt_is_supported(self):
        content = (
            "zone_id;rainfall_7d_mm;temperature_c;humidity_pct\n"
            "kisumu-west;61.5;27.2;68\n"
        ).encode()
        preview = parse_data_import("environment", "environment.txt", content, load_seed_data())
        self.assertTrue(preview["canApply"])
        self.assertEqual(preview["format"], "txt")
        self.assertEqual(preview["normalizedRows"][0]["rainfall7dMm"], 61.5)

    def test_tab_separated_supply_file_is_supported(self):
        content = (
            "clinic_id\tstock_rdt\tstock_act\tstock_nets\tweekly_use_rdt\tweekly_use_act\tweekly_use_nets\n"
            "chulaimbo-sch\t260\t180\t110\t46\t28\t11\n"
        ).encode()
        preview = parse_data_import("supply", "supply.tsv", content, load_seed_data())
        self.assertTrue(preview["canApply"])
        self.assertEqual(preview["normalizedRows"][0]["weeklyUse"]["act"], 28)

    def test_json_rows_wrapper_is_supported(self):
        content = json.dumps(
            {"rows": [{"zone_id": "kisumu-west", "rainfall_7d_mm": 61.5, "temperature_c": 27.2, "humidity_pct": 68}]}
        ).encode()
        preview = parse_data_import("environment", "environment.json", content, load_seed_data())
        self.assertTrue(preview["canApply"])
        self.assertEqual(preview["normalizedRows"][0]["temperatureC"], 27.2)

    def test_intervention_csv_updates_zone_coverage_context(self):
        dataset = load_seed_data()
        content = (
            "zone_id,coverage_date,llin_use_pct,iptp3_coverage_pct,vaccine_dose4_coverage_pct,larval_sites_managed_pct\n"
            "nyakach-north,2026-10-01,78,66,82,57\n"
        ).encode()
        preview = parse_data_import("intervention", "interventions.csv", content, dataset)
        self.assertTrue(preview["canApply"])
        updated = apply_parsed_import(dataset, preview)
        zone = next(item for item in updated["zones"] if item["id"] == "nyakach-north")
        self.assertEqual(zone["interventions"]["llinUsePct"], 78)
        self.assertEqual(zone["interventions"]["coverageDate"], "2026-10-01")

    def test_extended_clinical_and_environment_columns_are_imported(self):
        dataset = load_seed_data()
        clinical = (
            "zone_id,reporting_week,week_1_cases,week_2_cases,week_3_cases,week_4_cases,week_5_cases,week_6_cases,tests,positive_tests,"
            "suspected_cases,severe_cases,admissions,deaths,under_5_confirmed_cases,pregnancy_confirmed_cases,chw_fever_referrals,reporting_completeness_pct\n"
            "nyakach-north,2026-W42,20,22,25,31,49,72,200,72,218,8,7,1,26,7,35,96\n"
        ).encode()
        preview = parse_data_import("clinical", "clinical.csv", clinical, dataset)
        self.assertTrue(preview["canApply"])
        updated = apply_parsed_import(dataset, preview)
        self.assertEqual(updated["zones"][0]["clinical"]["severeCases"], 8)

        environment = (
            "zone_id,rainfall_7d_mm,temperature_c,humidity_pct,rainfall_30d_mm,standing_water_index,flooded_sites\n"
            "nyakach-north,142,27.6,82,331,89,16\n"
        ).encode()
        preview = parse_data_import("environment", "environment.csv", environment, updated)
        self.assertTrue(preview["canApply"])
        updated = apply_parsed_import(updated, preview)
        self.assertEqual(updated["zones"][0]["environment"]["standingWaterIndex"], 89)

    def test_first_html_table_is_supported(self):
        content = b"""
        <html><body><table>
          <tr><th>zone_id</th><th>rainfall_7d_mm</th><th>temperature_c</th><th>humidity_pct</th></tr>
          <tr><td>kisumu-west</td><td>62</td><td>27.3</td><td>69</td></tr>
        </table></body></html>
        """
        preview = parse_data_import("environment", "environment.html", content, load_seed_data())
        self.assertTrue(preview["canApply"])
        self.assertEqual(preview["format"], "html")
        self.assertEqual(preview["normalizedRows"][0]["humidityPct"], 69)

    def test_first_excel_sheet_is_supported(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["clinic_id", "stock_rdt", "stock_act", "stock_nets", "weekly_use_rdt", "weekly_use_act", "weekly_use_nets"])
        sheet.append(["chulaimbo-sch", 260, 180, 110, 46, 28, 11])
        content = BytesIO()
        workbook.save(content)
        workbook.close()
        preview = parse_data_import("supply", "supply.xlsx", content.getvalue(), load_seed_data())
        self.assertTrue(preview["canApply"])
        self.assertEqual(preview["format"], "xlsx")
        self.assertEqual(preview["normalizedRows"][0]["stock"]["rdt"], 260)

    def test_manual_save_functions_persist_clinical_environment_and_supply_data(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            seed_path = temporary_path / "seed.json"
            operational_path = temporary_path / "operational.json"
            seed_path.write_text(json.dumps(load_seed_data()), encoding="utf-8")

            with (
                patch.object(core, "SEED_PATH", seed_path),
                patch.object(core, "OPERATIONAL_PATH", operational_path),
            ):
                core.update_clinical("nyakach-north", [21, 24, 29, 37, 55, 81], 240, 81, "2026-W42")
                core.update_environment("nyakach-north", 88.5, 27.4, 79)
                core.update_supply(
                    "nyakach-ch",
                    {"rdt": 310, "act": 205, "nets": 90},
                    {"rdt": 63, "act": 39, "nets": 14},
                )

            saved = json.loads(operational_path.read_text(encoding="utf-8"))
            zone = next(item for item in saved["zones"] if item["id"] == "nyakach-north")
            clinic = next(item for item in saved["clinics"] if item["id"] == "nyakach-ch")
            self.assertEqual(zone["weeklyCases"], [21, 24, 29, 37, 55, 81])
            self.assertEqual(zone["environment"]["rainfall7dMm"], 88.5)
            self.assertEqual(clinic["stock"]["rdt"], 310)
            self.assertEqual(saved["metadata"]["reportingWeek"], "2026-W42")
            self.assertEqual(saved["metadata"]["lastUpdatedSource"], "supply-entry")

    def test_ai_uses_gemini_structured_output_and_current_network_data(self):
        dataset = load_seed_data()
        dataset["zones"][4]["weeklyCases"][-1] = 99
        captured = {}

        def fake_request(payload, api_key):
            captured["payload"] = payload
            captured["api_key"] = api_key
            return {
                "responseId": "resp_test",
                "candidates": [{"content": {"parts": [{"text": json.dumps(SAMPLE_REVIEW)}]}}],
            }

        result = create_ai_review(
            dataset,
            scope_id="network",
            api_key="gemini-test-key-not-a-real-secret-12345",
            request_fn=fake_request,
        )
        self.assertEqual(captured["payload"]["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(captured["payload"]["generationConfig"]["responseJsonSchema"]["type"], "object")
        self.assertIn('"currentCases":99', captured["payload"]["contents"][0]["parts"][0]["text"])
        self.assertIn('"severeCases":7', captured["payload"]["contents"][0]["parts"][0]["text"])
        self.assertIn('"llinUsePct":71', captured["payload"]["contents"][0]["parts"][0]["text"])
        self.assertIn("senior public-health operations analyst", captured["payload"]["systemInstruction"]["parts"][0]["text"])
        self.assertEqual(result["review"]["headline"], SAMPLE_REVIEW["headline"])
        self.assertEqual(result["responseId"], "resp_test")

    def test_ai_review_pdf_uses_the_selected_subcounty_letterhead(self):
        dataset = load_seed_data()
        result = {
            "review": SAMPLE_REVIEW,
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

        report = build_ai_report_pdf(result, dataset)

        self.assertTrue(report.startswith(b"%PDF-"))
        self.assertGreater(len(report), 2_500)
        self.assertEqual(report_jurisdiction(result, dataset), "Nyakach Sub-County")
        self.assertEqual(ai_report_filename(result, dataset), "malariapulse-ai-report-nyakach-sub-county-2026-W41.pdf")


if __name__ == "__main__":
    unittest.main()
