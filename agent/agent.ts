import { defineAgent } from "eve";
import { geminiModel } from "./model.js";

export default defineAgent({
  model: geminiModel,
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

