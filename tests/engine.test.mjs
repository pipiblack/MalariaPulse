import test from "node:test";
import assert from "node:assert/strict";
import { createAIIncidentBrief } from "../src/ai.mjs";
import { assessZone, buildNetworkSnapshot, draftAdvisories, loadSeedData, planResources, runResponseCycle } from "../src/domain/engine.mjs";
import { applyParsedImport, parseDataImport } from "../src/domain/imports.mjs";

test("risk assessment flags the seeded Nyakach spike", () => {
  const dataset = loadSeedData();
  const zone = dataset.zones.find((item) => item.id === "nyakach-north");
  const result = assessZone(zone, dataset.metadata);
  assert.equal(result.zoneId, "nyakach-north");
  assert.ok(result.score >= 60);
  assert.ok(["high", "critical"].includes(result.riskLevel));
  assert.ok(result.expectedCasesNextWeek > result.currentCases);
  assert.equal(result.drivers.length, 3);
});

test("stable zones remain below the action threshold", () => {
  const dataset = loadSeedData();
  const zone = dataset.zones.find((item) => item.id === "kisumu-west");
  const result = assessZone(zone, dataset.metadata);
  assert.ok(result.score < 60);
});

test("resource planning preserves donor safety stock and creates an auditable route", () => {
  const dataset = loadSeedData();
  const assessment = assessZone(dataset.zones.find((item) => item.id === "nyakach-north"), dataset.metadata);
  const plan = planResources(structuredClone(dataset), "nyakach-north", assessment);
  assert.equal(plan.requiresApproval, true);
  assert.ok(plan.recommendations.length > 0 || plan.restockRequests.length > 0);
  for (const move of plan.recommendations) {
    assert.ok(move.quantity > 0);
    assert.ok(move.etaMinutes >= 25);
    assert.notEqual(move.fromClinicId, move.toClinicId);
  }
});

test("community drafts include English, Kiswahili, and explicit review gates", () => {
  const dataset = loadSeedData();
  const zone = dataset.zones.find((item) => item.id === "nyakach-north");
  const assessment = assessZone(zone, dataset.metadata);
  const advisories = draftAdvisories(dataset, zone.id, assessment);
  assert.equal(advisories.requiresApproval, true);
  assert.deepEqual(advisories.messages.map((item) => item.language), ["English", "Kiswahili", "English"]);
  assert.match(advisories.messages[0].text, /alert, not a diagnosis/i);
  assert.match(advisories.messages[1].text, /si utambuzi/i);
});

test("response cycle executes all three agent stages and waits for approval", () => {
  const cycle = runResponseCycle(loadSeedData(), { zoneId: "nyakach-north", now: "2026-10-14T08:00:00.000Z" });
  assert.equal(cycle.id, "cycle-20261014080000-nyakach-north");
  assert.equal(cycle.status, "pending_approval");
  assert.equal(cycle.interventions.length, 1);
  assert.deepEqual(cycle.audit.slice(0, 3).map((item) => item.agent), ["Surveillance", "Supply", "Community"]);
});

test("network snapshot reports internally consistent totals", () => {
  const snapshot = buildNetworkSnapshot(loadSeedData());
  assert.equal(snapshot.summary.zonesMonitored, snapshot.assessments.length);
  assert.equal(snapshot.summary.facilitiesReporting, snapshot.clinics.length);
  assert.ok(snapshot.summary.stock.rdt > 0);
});

test("live AI brief uses the Responses API without storing the aggregate snapshot", async () => {
  let request;
  const brief = await createAIIncidentBrief({
    dataset: loadSeedData(),
    zoneId: "nyakach-north",
    question: "What needs attention?",
    apiKey: "test-key",
    model: "gpt-6-astra",
    fetchImpl: async (url, options) => {
      request = { url, options, body: JSON.parse(options.body) };
      return {
        ok: true,
        status: 200,
        async json() {
          return {
            id: "resp_test",
            output: [{ type: "message", content: [{ type: "output_text", text: "Review the critical signal." }] }]
          };
        }
      };
    }
  });
  assert.equal(request.url, "https://api.openai.com/v1/responses");
  assert.equal(request.body.model, "gpt-6-astra");
  assert.equal(request.body.store, false);
  assert.match(request.body.input, /Nyakach North/);
  assert.equal(brief.text, "Review the critical signal.");
  assert.equal(brief.responseId, "resp_test");
});

test("clinical CSV imports validate and update matching zones atomically", () => {
  const dataset = loadSeedData();
  const content = [
    "zone_id,reporting_week,week_1_cases,week_2_cases,week_3_cases,week_4_cases,week_5_cases,week_6_cases,tests,positive_tests",
    "nyakach-north,2026-W42,20,22,25,31,49,72,200,72",
    "kano-plains,2026-W42,30,32,35,39,48,57,210,57"
  ].join("\n");
  const result = parseDataImport({ kind: "clinical", filename: "clinical.csv", content, dataset });
  assert.equal(result.canApply, true);
  assert.equal(result.validCount, 2);
  const updated = applyParsedImport(dataset, result);
  assert.deepEqual(updated.zones.find((zone) => zone.id === "nyakach-north").weeklyCases, [20, 22, 25, 31, 49, 72]);
  assert.equal(updated.metadata.reportingWeek, "2026-W42");
  assert.deepEqual(dataset.zones.find((zone) => zone.id === "nyakach-north").weeklyCases, [18, 21, 24, 29, 47, 68]);
});

test("a bad CSV row blocks the entire import and reports row-level errors", () => {
  const dataset = loadSeedData();
  const content = [
    "zone_id,reporting_week,week_1_cases,week_2_cases,week_3_cases,week_4_cases,week_5_cases,week_6_cases,tests,positive_tests",
    "nyakach-north,2026-W42,20,22,25,31,49,72,40,72"
  ].join("\n");
  const result = parseDataImport({ kind: "clinical", filename: "clinical.csv", content, dataset });
  assert.equal(result.canApply, false);
  assert.equal(result.invalidCount, 1);
  assert.match(result.rows[0].errors.join(" "), /cannot exceed tests/);
  assert.throws(() => applyParsedImport(dataset, result), /Resolve all import errors/);
});

test("environment JSON imports accept a rows wrapper", () => {
  const dataset = loadSeedData();
  const content = JSON.stringify({ rows: [{ zone_id: "kisumu-west", rainfall_7d_mm: 61.5, temperature_c: 27.2, humidity_pct: 68 }] });
  const result = parseDataImport({ kind: "environment", filename: "environment.json", content, dataset });
  assert.equal(result.canApply, true);
  const updated = applyParsedImport(dataset, result);
  assert.deepEqual(updated.zones.find((zone) => zone.id === "kisumu-west").environment, { rainfall7dMm: 61.5, temperatureC: 27.2, humidityPct: 68 });
});

test("supply imports accept tab-separated files", () => {
  const dataset = loadSeedData();
  const content = [
    "clinic_id\tstock_rdt\tstock_act\tstock_nets\tweekly_use_rdt\tweekly_use_act\tweekly_use_nets",
    "chulaimbo-sch\t260\t180\t110\t46\t28\t11"
  ].join("\n");
  const result = parseDataImport({ kind: "supply", filename: "supply.tsv", content, dataset });
  assert.equal(result.canApply, true);
  const updated = applyParsedImport(dataset, result);
  assert.deepEqual(updated.clinics.find((clinic) => clinic.id === "chulaimbo-sch").stock, { rdt: 260, act: 180, nets: 110 });
});

test("patient-identifying columns are rejected from aggregate uploads", () => {
  const dataset = loadSeedData();
  const content = "zone_id,rainfall_7d_mm,temperature_c,humidity_pct,patient_name\nkisumu-west,61,27,68,Example Person";
  const result = parseDataImport({ kind: "environment", filename: "unsafe.csv", content, dataset });
  assert.equal(result.canApply, false);
  assert.match(result.fileErrors.join(" "), /Patient-identifying columns/);
});

