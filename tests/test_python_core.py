import json
import unittest

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

    def test_response_cycle_has_human_gate(self):
        cycle = run_response_cycle(load_seed_data(), zone_id="nyakach-north", now="2026-10-14T08:00:00.000Z")
        self.assertEqual(cycle["status"], "pending_approval")
        self.assertEqual([item["agent"] for item in cycle["audit"][:3]], ["Surveillance", "Supply", "Community"])
        plan = plan_resources(load_seed_data(), "nyakach-north", cycle["assessments"][0])
        self.assertTrue(plan["requiresApproval"])

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

    def test_ai_uses_structured_responses_and_current_network_data(self):
        dataset = load_seed_data()
        dataset["zones"][4]["weeklyCases"][-1] = 99
        captured = {}

        def fake_request(payload, api_key):
            captured["payload"] = payload
            captured["api_key"] = api_key
            return {"id": "resp_test", "output_text": json.dumps(SAMPLE_REVIEW)}

        result = create_ai_review(
            dataset,
            scope_id="network",
            api_key="sk-test-key-not-a-real-secret-12345",
            request_fn=fake_request,
        )
        self.assertFalse(captured["payload"]["store"])
        self.assertEqual(captured["payload"]["text"]["format"]["type"], "json_schema")
        self.assertIn('"currentCases":99', captured["payload"]["input"])
        self.assertEqual(result["review"]["headline"], SAMPLE_REVIEW["headline"])


if __name__ == "__main__":
    unittest.main()
