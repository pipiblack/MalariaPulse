import { defineAgent } from "eve";
import { openai } from "eve/models/openai";

export default defineAgent({
  model: openai("gpt-6-astra"),
  modelContextWindowTokens: 128_000,
  reasoning: "high",
  tool: false,
  limits: {
    maxInputTokensPerSession: 120_000,
    maxOutputTokensPerSession: 16_000,
    maxTokenCostUsdPerSession: 1,
    sessionTimeoutMs: 7 * 24 * 60 * 60 * 1_000
  }
});

