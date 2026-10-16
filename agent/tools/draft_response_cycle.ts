import { defineTool } from "eve/tools";
import { z } from "zod";
import { loadDataset, runResponseCycle } from "../../src/domain/engine.mjs";

export default defineTool({
  description:
    "Generate a non-persistent malaria response draft for one micro-zone from the latest aggregate data. The result may contain proposed stock movements and outreach messages, but it never approves, sends, procures, or dispatches anything.",
  inputSchema: z.object({
    zoneId: z.string().min(1)
  }),
  label: {
    start: ({ zoneId }) => `Draft response cycle for ${zoneId}`,
    complete: ({ zoneId }) => `Response draft ready for ${zoneId}`
  },
  execute({ zoneId }) {
    const cycle = runResponseCycle(loadDataset(), { zoneId });
    return {
      ...cycle,
      persistence: "not-saved",
      executionStatus: "draft-only",
      requiredReview:
        "County surveillance, pharmacy/logistics, clinical, community-health, and language leads must verify the evidence and authorize any external action."
    };
  }
});
