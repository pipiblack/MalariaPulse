import { defineTool } from "eve/tools";
import { z } from "zod";
import { assessZone, loadDataset, planResources } from "../../../../src/domain/engine.mjs";

export default defineTool({
  description: "Calculate safety-stock gaps and draft nearest feasible redistribution routes for one flagged zone.",
  inputSchema: z.object({
    zoneId: z.string().min(1)
  }),
  label: {
    start: ({ zoneId }) => `Plan resource coverage for ${zoneId}`,
    complete: ({ zoneId }) => `Resource draft ready for ${zoneId}`
  },
  execute({ zoneId }) {
    const dataset = loadDataset();
    const zone = dataset.zones.find((item) => item.id === zoneId);
    if (!zone) throw new Error(`Unknown zone: ${zoneId}`);
    const assessment = assessZone(zone, dataset.metadata);
    return {
      sourceTimestamp: dataset.metadata.updatedAt,
      assessment: { score: assessment.score, riskLevel: assessment.riskLevel },
      plan: planResources(structuredClone(dataset), zoneId, assessment)
    };
  }
});

