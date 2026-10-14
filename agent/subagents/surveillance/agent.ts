import { defineAgent } from "eve";
import { openai } from "eve/models/openai";

export default defineAgent({
  description:
    "Assess current malaria risk by micro-zone from aggregated clinical and environmental signals, explain drivers, and identify zones crossing action thresholds.",
  model: openai("gpt-6-astra"),
  modelContextWindowTokens: 128_000,
  reasoning: "high",
  limits: {
    maxOutputTokensPerSession: 6_000,
    sessionTimeoutMs: 24 * 60 * 60 * 1_000
  }
});

