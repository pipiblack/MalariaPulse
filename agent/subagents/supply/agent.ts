import { defineAgent } from "eve";
import { geminiModel } from "../../model.js";

export default defineAgent({
  description:
    "Evaluate facility RDT, ACT, and treated-net telemetry for a flagged zone and draft safety-stock-aware redistribution routes or county restock requests.",
  model: geminiModel,
  modelContextWindowTokens: 128_000,
  reasoning: "high",
  limits: {
    maxOutputTokensPerSession: 6_000,
    sessionTimeoutMs: 24 * 60 * 60 * 1_000
  }
});

