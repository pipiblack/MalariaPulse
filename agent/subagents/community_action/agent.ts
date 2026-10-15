import { defineAgent } from "eve";
import { geminiModel } from "../../model.js";

export default defineAgent({
  description:
    "Draft concise, hyper-local malaria prevention and prompt-testing messages for residents and community health workers in English and Kiswahili.",
  model: geminiModel,
  modelContextWindowTokens: 128_000,
  reasoning: "high",
  limits: {
    maxOutputTokensPerSession: 6_000,
    sessionTimeoutMs: 24 * 60 * 60 * 1_000
  }
});

