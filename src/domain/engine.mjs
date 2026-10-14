import { existsSync, readFileSync } from "node:fs";

const SEED_URL = new URL("../../data/seed.json", import.meta.url);
const OPERATIONAL_URL = new URL("../../data/operational.json", import.meta.url);
const RESOURCE_LABELS = { rdt: "RDT kits", act: "ACT courses", nets: "treated nets" };

const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
const average = (values) => values.reduce((sum, value) => sum + value, 0) / Math.max(values.length, 1);
const round = (value, precision = 0) => {
  const factor = 10 ** precision;
  return Math.round(value * factor) / factor;
};

export function loadSeedData() {
  return JSON.parse(readFileSync(SEED_URL, "utf8"));
}

export function loadDataset() {
  const source = existsSync(OPERATIONAL_URL) ? OPERATIONAL_URL : SEED_URL;
  return JSON.parse(readFileSync(source, "utf8"));
}

export function classifyRisk(score) {
  if (score >= 75) return "critical";
  if (score >= 60) return "high";
  if (score >= 40) return "watch";
  return "low";
}

export function assessZone(zone, metadata = {}) {
  if (!zone || !Array.isArray(zone.weeklyCases) || zone.weeklyCases.length < 4) {
    throw new TypeError("A zone with at least four weekly case counts is required.");
  }

  const history = zone.weeklyCases;
  const baseline = average(history.slice(0, -2));
  const recent = average(history.slice(-2));
  const latest = history.at(-1);
  const growthRatio = recent / Math.max(baseline, 1);
  const positivity = zone.positiveTests / Math.max(zone.tests, 1);
  const trendSignal = clamp((growthRatio - 0.9) / 1.25);
  const positivitySignal = clamp(positivity / 0.34);
  const rainfallSignal = clamp(zone.environment.rainfall7dMm / 130);
  const humiditySignal = clamp((zone.environment.humidityPct - 52) / 30);
  const temperatureSignal = clamp(1 - Math.abs(zone.environment.temperatureC - 27) / 9);

  const components = [
    { key: "caseTrend", label: `${round((growthRatio - 1) * 100)}% case acceleration`, value: trendSignal, weight: 0.4 },
    { key: "positivity", label: `${round(positivity * 100)}% test positivity`, value: positivitySignal, weight: 0.23 },
    { key: "rainfall", label: `${zone.environment.rainfall7dMm} mm rainfall / 7 days`, value: rainfallSignal, weight: 0.16 },
    { key: "humidity", label: `${zone.environment.humidityPct}% humidity`, value: humiditySignal, weight: 0.11 },
    { key: "temperature", label: `${zone.environment.temperatureC}°C transmission suitability`, value: temperatureSignal, weight: 0.1 }
  ];

  const score = Math.round(components.reduce((sum, item) => sum + item.value * item.weight, 0) * 100);
  const riskLevel = classifyRisk(score);
  const projectedMultiplier = clamp(0.6 + growthRatio * 0.55, 0.75, 1.85);
  const expectedCasesNextWeek = Math.round(latest * projectedMultiplier);
  const incidencePerThousand = round((latest / zone.population) * 1000, 2);
  const dataCompleteness = metadata.dataCompleteness ?? 0.9;
  const confidence = round(clamp(0.7 + dataCompleteness * 0.24 - (zone.tests < 30 ? 0.15 : 0)), 2);

  return {
    zoneId: zone.id,
    zoneName: zone.name,
    subcounty: zone.subcounty,
    score,
    riskLevel,
    confidence,
    currentCases: latest,
    expectedCasesNextWeek,
    growthPct: round((growthRatio - 1) * 100),
    positivityPct: round(positivity * 100, 1),
    incidencePerThousand,
    coordinates: zone.coordinates,
    drivers: components
      .map((item) => ({ ...item, contribution: round(item.value * item.weight * 100, 1) }))
      .sort((a, b) => b.contribution - a.contribution)
      .slice(0, 3)
      .map(({ label, contribution }) => ({ label, contribution })),
    recommendation:
      riskLevel === "critical"
        ? "Activate rapid response review within 4 hours."
        : riskLevel === "high"
          ? "Validate the alert and prepare targeted response within 24 hours."
          : riskLevel === "watch"
            ? "Increase reporting cadence and verify case data."
            : "Continue routine surveillance."
  };
}

function distanceKm(a, b) {
  const radius = 6371;
  const toRad = (degrees) => (degrees * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return radius * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}

export function planResources(dataset, zoneId, assessment) {
  const zone = dataset.zones.find((item) => item.id === zoneId);
  if (!zone) throw new Error(`Unknown zone: ${zoneId}`);

  const targetClinics = dataset.clinics.filter((clinic) => zone.clinicIds.includes(clinic.id));
  const donorClinics = dataset.clinics.filter((clinic) => !zone.clinicIds.includes(clinic.id));
  const multiplier = assessment.riskLevel === "critical" ? 1.7 : assessment.riskLevel === "high" ? 1.45 : 1.2;
  const recommendations = [];
  const restockRequests = [];

  for (const target of targetClinics) {
    for (const resource of Object.keys(RESOURCE_LABELS)) {
      const targetLevel = Math.ceil(target.weeklyUse[resource] * 3 * multiplier);
      let deficit = Math.max(0, targetLevel - target.stock[resource]);
      if (deficit === 0) continue;

      const donors = donorClinics
        .map((clinic) => ({
          clinic,
          surplus: Math.max(0, clinic.stock[resource] - Math.ceil(clinic.weeklyUse[resource] * 3)),
          distance: distanceKm(clinic.coordinates, target.coordinates)
        }))
        .filter((candidate) => candidate.surplus > 0)
        .sort((a, b) => a.distance - b.distance);

      for (const donor of donors) {
        if (deficit <= 0) break;
        const quantity = Math.min(deficit, donor.surplus);
        if (quantity < 1) continue;
        recommendations.push({
          priority: assessment.riskLevel === "critical" ? "urgent" : "high",
          resource,
          resourceLabel: RESOURCE_LABELS[resource],
          quantity,
          fromClinicId: donor.clinic.id,
          fromClinic: donor.clinic.name,
          toClinicId: target.id,
          toClinic: target.name,
          distanceKm: round(donor.distance, 1),
          etaMinutes: Math.max(25, Math.round(donor.distance * 2.4 + 18)),
          rationale: `Restores approximately three weeks of safety stock at projected ${assessment.riskLevel} demand.`
        });
        deficit -= quantity;
        donor.clinic.stock[resource] -= quantity;
      }

      if (deficit > 0) {
        restockRequests.push({
          resource,
          resourceLabel: RESOURCE_LABELS[resource],
          quantity: deficit,
          clinicId: target.id,
          clinic: target.name,
          priority: assessment.riskLevel === "critical" ? "urgent" : "high"
        });
      }
    }
  }

  const readinessValues = targetClinics.flatMap((clinic) =>
    Object.keys(RESOURCE_LABELS).map((resource) =>
      clamp(clinic.stock[resource] / Math.max(clinic.weeklyUse[resource] * 3 * multiplier, 1))
    )
  );

  return {
    zoneId,
    generatedForRisk: assessment.riskLevel,
    readinessPct: Math.round(average(readinessValues) * 100),
    recommendations,
    restockRequests,
    requiresApproval: recommendations.length > 0 || restockRequests.length > 0,
    note: "Draft only. A county pharmacist or authorized logistics officer must verify counts and approve movement."
  };
}

function smsSegments(text) {
  return Math.ceil(text.length / 153);
}

export function draftAdvisories(dataset, zoneId, assessment) {
  const zone = dataset.zones.find((item) => item.id === zoneId);
  if (!zone) throw new Error(`Unknown zone: ${zoneId}`);
  const clinics = dataset.clinics.filter((clinic) => zone.clinicIds.includes(clinic.id));
  const clinicName = clinics[0]?.name ?? "your nearest health facility";

  const english = `Malaria risk is rising in ${zone.name}. Sleep under a treated net every night. If you have fever, chills or headache, seek a malaria test promptly at ${clinicName}. Children under 5 and pregnant people need prompt attention. Test before treatment. This is an alert, not a diagnosis.`;
  const swahili = `Hatari ya malaria inaongezeka ${zone.name}. Lala ndani ya chandarua chenye dawa kila usiku. Ukipata homa, baridi au maumivu ya kichwa, nenda kupimwa mapema katika ${clinicName}. Watoto chini ya miaka 5 na wajawazito wahudumiwe haraka. Pima kabla ya dawa. Huu ni ujumbe wa tahadhari, si utambuzi.`;
  const chw = `CHW ACTION — ${zone.name}: verify fever reports, encourage prompt testing, check treated-net use, and refer severe illness immediately. Prioritize children under 5 and pregnant people. Do not recommend antimalarials without an approved test-and-treat protocol. Report stock gaps and unusual clusters to the sub-county surveillance lead.`;

  return {
    zoneId,
    messages: [
      { audience: "residents", language: "English", channel: "SMS/WhatsApp", text: english, characters: english.length, segments: smsSegments(english) },
      { audience: "residents", language: "Kiswahili", channel: "SMS/WhatsApp", text: swahili, characters: swahili.length, segments: smsSegments(swahili) },
      { audience: "community health workers", language: "English", channel: "WhatsApp", text: chw, characters: chw.length, segments: smsSegments(chw) }
    ],
    requiresApproval: true,
    clinicalSafety: "Templates follow WHO-aligned prevention and prompt-testing principles; local health authorities must review before release."
  };
}

export function buildNetworkSnapshot(dataset = loadSeedData()) {
  const assessments = dataset.zones
    .map((zone) => assessZone(zone, dataset.metadata))
    .sort((a, b) => b.score - a.score);
  const stock = dataset.clinics.reduce(
    (totals, clinic) => {
      for (const resource of Object.keys(RESOURCE_LABELS)) totals[resource] += clinic.stock[resource];
      return totals;
    },
    { rdt: 0, act: 0, nets: 0 }
  );
  const readiness = dataset.clinics.map((clinic) =>
    average(Object.keys(RESOURCE_LABELS).map((resource) => clamp(clinic.stock[resource] / (clinic.weeklyUse[resource] * 3))))
  );

  return {
    metadata: dataset.metadata,
    assessments,
    clinics: dataset.clinics,
    summary: {
      zonesMonitored: assessments.length,
      highRiskZones: assessments.filter((item) => ["high", "critical"].includes(item.riskLevel)).length,
      facilitiesReporting: dataset.clinics.length,
      supplyReadinessPct: Math.round(average(readiness) * 100),
      stock
    }
  };
}

export function runResponseCycle(dataset = loadSeedData(), options = {}) {
  const createdAt = options.now ?? new Date().toISOString();
  const allAssessments = dataset.zones.map((zone) => assessZone(zone, dataset.metadata)).sort((a, b) => b.score - a.score);
  const requested = options.zoneId ? allAssessments.filter((item) => item.zoneId === options.zoneId) : allAssessments;
  if (requested.length === 0) throw new Error(`Unknown zone: ${options.zoneId}`);
  const triggered = requested.filter((item) => ["high", "critical"].includes(item.riskLevel));
  const interventions = triggered.map((assessment) => ({
    zoneId: assessment.zoneId,
    zoneName: assessment.zoneName,
    assessment,
    supplyPlan: planResources(structuredClone(dataset), assessment.zoneId, assessment),
    advisories: draftAdvisories(dataset, assessment.zoneId, assessment)
  }));
  const idStamp = createdAt.replace(/[-:.TZ]/g, "").slice(0, 14);

  return {
    id: `cycle-${idStamp}-${options.zoneId ?? "network"}`,
    createdAt,
    status: interventions.length > 0 ? "pending_approval" : "monitoring",
    mode: dataset.metadata.mode,
    assessments: requested,
    interventions,
    audit: [
      { agent: "Surveillance", status: "complete", detail: `${requested.length} zone${requested.length === 1 ? "" : "s"} assessed`, at: createdAt },
      { agent: "Supply", status: "complete", detail: `${interventions.reduce((sum, item) => sum + item.supplyPlan.recommendations.length, 0)} transfer drafts`, at: createdAt },
      { agent: "Community", status: "complete", detail: `${interventions.reduce((sum, item) => sum + item.advisories.messages.length, 0)} message drafts`, at: createdAt },
      { agent: "Human review", status: interventions.length > 0 ? "waiting" : "not_required", detail: interventions.length > 0 ? "Release and movement approval required" : "No action threshold crossed", at: createdAt }
    ]
  };
}

