import { createGoogle } from "@ai-sdk/google";

declare const process: { env: Record<string, string | undefined> };

const apiKey = process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY;
const google = createGoogle(apiKey ? { apiKey } : {});

export const geminiModel = google(process.env.GEMINI_MODEL || "gemini-3.8-flash");
