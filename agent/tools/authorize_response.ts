import { defineTool } from "eve/tools";
import { always } from "eve/tools/approval";
import { z } from "zod";

export default defineTool({
  availableInSubagents: false,
  description:
    "Record a human authorization for a drafted stock movement or public outreach release. This records approval only; no downstream dispatch adapter is connected in the MVP.",
  inputSchema: z.object({
    zoneId: z.string().min(1),
    actionType: z.enum(["stock-movement", "outreach-release", "combined-response"]),
    summary: z.string().min(10).max(2_000),
    sourceTimestamp: z.string().min(1)
  }),
  approval: {
    request: always(),
    prompt: ({ input }) => `Authorize the ${input.actionType} draft for ${input.zoneId}? Verify source data, stock counts, route feasibility, and message wording first.`
  },
  label: {
    start: ({ zoneId, actionType }) => `Request ${actionType} approval for ${zoneId}`,
    complete: ({ zoneId }) => `Approval recorded for ${zoneId}`
  },
  execute(input, ctx) {
    return {
      authorizationId: `${ctx.callId}:${input.zoneId}`,
      status: "approved",
      recordedAt: new Date().toISOString(),
      downstreamDispatch: "not-connected",
      ...input
    };
  }
});

