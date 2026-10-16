import { defineTool } from "eve/tools";
import { z } from "zod";
import { buildNetworkSnapshot, loadDataset } from "../../src/domain/engine.mjs";

export default defineTool({
  description:
    "Read the latest aggregate MalariaPulse surveillance, intervention, and facility-supply context for every micro-zone or one selected micro-zone. This is read-only and never returns patient-level records.",
  inputSchema: z.object({
    zoneId: z.string().min(1).optional()
  }),
  label: {
    start: ({ zoneId }) => zoneId ? `Read surveillance snapshot for ${zoneId}` : "Read network surveillance snapshot",
    complete: ({ zoneId }) => zoneId ? `Snapshot ready for ${zoneId}` : "Network snapshot ready"
  },
  execute({ zoneId }) {
    const dataset = loadDataset();
    const snapshot = buildNetworkSnapshot(dataset);
    const zones = zoneId
      ? dataset.zones.filter((zone: { id: string }) => zone.id === zoneId)
      : dataset.zones;

    if (zones.length === 0) throw new Error(`Unknown zone: ${zoneId}`);

    const zoneIds = new Set(zones.map((zone: { id: string }) => zone.id));
    return {
      metadata: snapshot.metadata,
      summary: snapshot.summary,
      assessments: snapshot.assessments.filter((assessment: { zoneId: string }) => zoneIds.has(assessment.zoneId)),
      zones: zones.map((zone: {
        id: string;
        name: string;
        subcounty: string;
        population: number;
        weeklyCases: number[];
        tests: number;
        positiveTests: number;
        clinical?: Record<string, unknown>;
        environment: Record<string, unknown>;
        interventions?: Record<string, unknown>;
      }) => ({
        id: zone.id,
        name: zone.name,
        subcounty: zone.subcounty,
        population: zone.population,
        weeklyCases: zone.weeklyCases,
        tests: zone.tests,
        positiveTests: zone.positiveTests,
        clinical: zone.clinical ?? {},
        environment: zone.environment,
        interventions: zone.interventions ?? {}
      })),
      clinics: snapshot.clinics.filter((clinic: { zoneId: string }) => zoneIds.has(clinic.zoneId)),
      validationStatus:
        "Aggregate decision support only. The demonstration score requires local epidemiological calibration and human validation before operational use."
    };
  }
});
