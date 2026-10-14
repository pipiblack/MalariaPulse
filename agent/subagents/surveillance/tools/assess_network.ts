import { defineTool } from "eve/tools";
import { z } from "zod";
import { buildNetworkSnapshot, loadDataset } from "../../../../src/domain/engine.mjs";

export default defineTool({
  description: "Read the latest aggregated demo feeds and compute transparent malaria risk assessments for all zones or one zone.",
  inputSchema: z.object({
    zoneId: z.string().min(1).optional()
  }),
  label: {
    start: ({ zoneId }) => zoneId ? `Assess malaria risk in ${zoneId}` : "Assess network malaria risk",
    complete: ({ zoneId }) => zoneId ? `Risk assessed for ${zoneId}` : "Network risk assessed"
  },
  execute({ zoneId }) {
    const snapshot = buildNetworkSnapshot(loadDataset());
    const assessments = zoneId
      ? snapshot.assessments.filter((assessment) => assessment.zoneId === zoneId)
      : snapshot.assessments;
    if (assessments.length === 0) throw new Error(`Unknown zone: ${zoneId}`);
    return {
      metadata: snapshot.metadata,
      assessments,
      thresholdPolicy: { low: "0-39", watch: "40-59", high: "60-74", critical: "75-100" },
      validationStatus: "Demonstration model; local retrospective calibration is required before operational use."
    };
  }
});

