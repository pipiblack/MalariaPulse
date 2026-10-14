import { defineAgent } from "eve";
import { openai } from "eve/models/openai";

export default defineAgent({
  description:
    "Draft concise, hyper-local malaria prevention and prompt-testing messages for residents and community health workers in English and Kiswahili.",
  model: openai("gpt-6-astra"),
  modelContextWindowTokens: 128_000,
  reasoning: "high",
  limits: {
    maxOutputTokensPerSession: 6_000,
    sessionTimeoutMs: 24 * 60 * 60 * 1_000
  }
});

