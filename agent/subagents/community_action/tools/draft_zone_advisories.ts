import { defineTool } from "eve/tools";
import { z } from "zod";
import { assessZone, draftAdvisories, loadDataset } from "../../../../src/domain/engine.mjs";

export default defineTool({
  description: "Generate review-ready resident and CHW malaria advisory drafts for one zone in the approved MVP languages.",
  inputSchema: z.object({
    zoneId: z.string().min(1)
  }),
  label: {
    start: ({ zoneId }) => `Draft outreach for ${zoneId}`,
    complete: ({ zoneId }) => `Outreach drafts ready for ${zoneId}`
  },
  execute({ zoneId }) {
    const dataset = loadDataset();
    const zone = dataset.zones.find((item) => item.id === zoneId);
    if (!zone) throw new Error(`Unknown zone: ${zoneId}`);
    const assessment = assessZone(zone, dataset.metadata);
    return {
      sourceTimestamp: dataset.metadata.updatedAt,
      riskLevel: assessment.riskLevel,
      ...draftAdvisories(dataset, zoneId, assessment)
    };
  }
});

