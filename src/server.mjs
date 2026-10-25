import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { config } from "./config.mjs";
import { createAIIncidentBrief, getAIStatus } from "./ai.mjs";
import {
  applyDataImport,
  createCycle,
  decideCycle,
  getDashboardState,
  getOperationalData,
  previewDataImport,
  updateClinicalData,
  updateEnvironmentData,
  updateSupplyData
} from "./domain/store.mjs";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const PUBLIC_DIR = resolve(ROOT, "public");
const PORT = config.port;
const MAX_JSON_REQUEST_BYTES = 64 * 1024 * 1024;
const CONTENT_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml"
};

function json(response, status, body) {
  response.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" });
  response.end(JSON.stringify(body));
}

async function readJson(request) {
  const chunks = [];
  let bytes = 0;
  for await (const chunk of request) {
    bytes += chunk.length;
    if (bytes > MAX_JSON_REQUEST_BYTES) throw new Error("Request body is too large. Keep upload files at or below 15 MB.");
    chunks.push(chunk);
  }
  if (chunks.length === 0) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

function serveStatic(requestPath, response) {
  const relative = requestPath === "/" ? "index.html" : decodeURIComponent(requestPath).replace(/^\/+/, "");
  const filePath = resolve(PUBLIC_DIR, relative);
  if (filePath !== PUBLIC_DIR && !filePath.startsWith(`${PUBLIC_DIR}${sep}`)) return false;
  if (!existsSync(filePath) || !statSync(filePath).isFile()) return false;
  response.writeHead(200, {
    "content-type": CONTENT_TYPES[extname(filePath)] ?? "application/octet-stream",
    "cache-control": extname(filePath) === ".html" ? "no-cache" : "public, max-age=300"
  });
  createReadStream(filePath).pipe(response);
  return true;
}

export function createAppServer() {
  return createServer(async (request, response) => {
    const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);
    try {
      if (request.method === "GET" && url.pathname === "/api/dashboard") {
        return json(response, 200, getDashboardState());
      }

      if (request.method === "GET" && url.pathname === "/api/data") {
        return json(response, 200, getOperationalData());
      }

      if (request.method === "GET" && url.pathname === "/api/ai/status") {
        return json(response, 200, getAIStatus());
      }

      if (request.method === "POST" && url.pathname === "/api/ai/brief") {
        const input = await readJson(request);
        const scope = typeof input.scope === "string" && input.scope ? input.scope : typeof input.zoneId === "string" && input.zoneId ? input.zoneId : "network";
        const brief = await createAIIncidentBrief({
          dataset: getOperationalData(),
          zoneId: scope.slice(0, 100),
          question: typeof input.question === "string" ? input.question.slice(0, 1_000) : ""
        });
        return json(response, 200, brief);
      }

      if (request.method === "POST" && url.pathname === "/api/cycles") {
        const input = await readJson(request);
        const cycle = createCycle({ zoneId: typeof input.zoneId === "string" && input.zoneId ? input.zoneId : undefined });
        return json(response, 201, cycle);
      }

      if (request.method === "POST" && url.pathname === "/api/import/preview") {
        const input = await readJson(request);
        return json(response, 200, previewDataImport(input));
      }

      if (request.method === "POST" && url.pathname === "/api/import/apply") {
        const input = await readJson(request);
        return json(response, 200, applyDataImport(input));
      }

      const clinicalMatch = url.pathname.match(/^\/api\/data\/clinical\/([^/]+)$/);
      if (request.method === "PUT" && clinicalMatch) {
        return json(response, 200, updateClinicalData(decodeURIComponent(clinicalMatch[1]), await readJson(request)));
      }

      const environmentMatch = url.pathname.match(/^\/api\/data\/environment\/([^/]+)$/);
      if (request.method === "PUT" && environmentMatch) {
        return json(response, 200, updateEnvironmentData(decodeURIComponent(environmentMatch[1]), await readJson(request)));
      }

      const supplyMatch = url.pathname.match(/^\/api\/data\/supply\/([^/]+)$/);
      if (request.method === "PUT" && supplyMatch) {
        return json(response, 200, updateSupplyData(decodeURIComponent(supplyMatch[1]), await readJson(request)));
      }

      const decisionMatch = url.pathname.match(/^\/api\/cycles\/([^/]+)\/(approve|reject)$/);
      if (request.method === "POST" && decisionMatch) {
        const input = await readJson(request);
        const cycle = decideCycle(decodeURIComponent(decisionMatch[1]), decisionMatch[2], input.reviewer || "Operations reviewer");
        return cycle ? json(response, 200, cycle) : json(response, 404, { error: "Cycle not found." });
      }

      if (request.method === "GET" && serveStatic(url.pathname, response)) return;
      return json(response, 404, { error: "Not found." });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unexpected error";
      const status = message.startsWith("Unknown zone") || message.startsWith("Unknown clinic") ? 404 : error?.code === "AI_NOT_CONFIGURED" ? 503 : 400;
      return json(response, status, { error: message });
    }
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  createAppServer().listen(PORT, "0.0.0.0", () => {
    console.log(`MalariaPulse operations console: http://localhost:${PORT}`);
  });
}

