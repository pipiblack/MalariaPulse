import { existsSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { buildNetworkSnapshot, loadDataset, runResponseCycle } from "./engine.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const RUNTIME_PATH = resolve(ROOT, "data/runtime.json");
const OPERATIONAL_PATH = resolve(ROOT, "data/operational.json");

function readRuntime() {
  if (!existsSync(RUNTIME_PATH)) return { cycles: [] };
  try {
    const data = JSON.parse(readFileSync(RUNTIME_PATH, "utf8"));
    return Array.isArray(data.cycles) ? data : { cycles: [] };
  } catch {
    return { cycles: [] };
  }
}

function writeRuntime(runtime) {
  const tempPath = `${RUNTIME_PATH}.tmp`;
  writeFileSync(tempPath, `${JSON.stringify(runtime, null, 2)}\n`, "utf8");
  renameSync(tempPath, RUNTIME_PATH);
}

function writeDataset(dataset) {
  const tempPath = `${OPERATIONAL_PATH}.tmp`;
  writeFileSync(tempPath, `${JSON.stringify(dataset, null, 2)}\n`, "utf8");
  renameSync(tempPath, OPERATIONAL_PATH);
}

function finiteNumber(value, field, { min = 0, max = Number.MAX_SAFE_INTEGER, integer = false } = {}) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < min || number > max || (integer && !Number.isInteger(number))) {
    throw new Error(`${field} must be ${integer ? "a whole number" : "a number"} between ${min} and ${max}.`);
  }
  return number;
}

function stamp(dataset, source) {
  dataset.metadata.updatedAt = new Date().toISOString();
  dataset.metadata.mode = "operator-entry";
  dataset.metadata.lastUpdatedSource = source;
  return dataset;
}

export function getDashboardState() {
  const dataset = loadDataset();
  const runtime = readRuntime();
  return {
    ...buildNetworkSnapshot(dataset),
    latestCycle: runtime.cycles.at(0) ?? null,
    recentCycles: runtime.cycles.slice(0, 8)
  };
}

export function createCycle({ zoneId } = {}) {
  const runtime = readRuntime();
  const cycle = runResponseCycle(loadDataset(), { zoneId });
  runtime.cycles.unshift(cycle);
  runtime.cycles = runtime.cycles.slice(0, 25);
  writeRuntime(runtime);
  return cycle;
}

export function getOperationalData() {
  return loadDataset();
}

export function updateClinicalData(zoneId, input) {
  const dataset = loadDataset();
  const zone = dataset.zones.find((item) => item.id === zoneId);
  if (!zone) throw new Error(`Unknown zone: ${zoneId}`);
  if (!Array.isArray(input.weeklyCases) || input.weeklyCases.length !== 6) {
    throw new Error("weeklyCases must contain exactly six weekly totals.");
  }
  const weeklyCases = input.weeklyCases.map((value, index) => finiteNumber(value, `Week ${index + 1} cases`, { integer: true }));
  const tests = finiteNumber(input.tests, "Tests", { integer: true });
  const positiveTests = finiteNumber(input.positiveTests, "Positive tests", { integer: true });
  if (positiveTests > tests) throw new Error("Positive tests cannot exceed total tests.");
  zone.weeklyCases = weeklyCases;
  zone.tests = tests;
  zone.positiveTests = positiveTests;
  if (typeof input.reportingWeek === "string" && /^\d{4}-W\d{2}$/.test(input.reportingWeek)) {
    dataset.metadata.reportingWeek = input.reportingWeek;
  }
  writeDataset(stamp(dataset, "clinical-entry"));
  return { zone, metadata: dataset.metadata };
}

export function updateEnvironmentData(zoneId, input) {
  const dataset = loadDataset();
  const zone = dataset.zones.find((item) => item.id === zoneId);
  if (!zone) throw new Error(`Unknown zone: ${zoneId}`);
  zone.environment = {
    rainfall7dMm: finiteNumber(input.rainfall7dMm, "7-day rainfall", { max: 2_000 }),
    temperatureC: finiteNumber(input.temperatureC, "Temperature", { min: -10, max: 60 }),
    humidityPct: finiteNumber(input.humidityPct, "Humidity", { max: 100 })
  };
  writeDataset(stamp(dataset, "environment-entry"));
  return { zone, metadata: dataset.metadata };
}

export function updateSupplyData(clinicId, input) {
  const dataset = loadDataset();
  const clinic = dataset.clinics.find((item) => item.id === clinicId);
  if (!clinic) throw new Error(`Unknown clinic: ${clinicId}`);
  for (const group of ["stock", "weeklyUse"]) {
    clinic[group] = {
      rdt: finiteNumber(input[group]?.rdt, `${group} RDT`, { integer: true }),
      act: finiteNumber(input[group]?.act, `${group} ACT`, { integer: true }),
      nets: finiteNumber(input[group]?.nets, `${group} nets`, { integer: true })
    };
  }
  writeDataset(stamp(dataset, "supply-entry"));
  return { clinic, metadata: dataset.metadata };
}

export function decideCycle(cycleId, decision, reviewer = "Operations reviewer") {
  if (!["approve", "reject"].includes(decision)) throw new Error("Decision must be approve or reject.");
  const runtime = readRuntime();
  const cycle = runtime.cycles.find((item) => item.id === cycleId);
  if (!cycle) return null;
  if (cycle.status !== "pending_approval") throw new Error(`Cycle is already ${cycle.status}.`);
  cycle.status = decision === "approve" ? "approved" : "rejected";
  cycle.review = { decision, reviewer, at: new Date().toISOString() };
  cycle.audit.push({
    agent: "Human review",
    status: cycle.status,
    detail: `${reviewer} ${decision === "approve" ? "approved the draft response" : "rejected the draft response"}`,
    at: cycle.review.at
  });
  writeRuntime(runtime);
  return cycle;
}

