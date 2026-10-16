import { httpBasic, localDev } from "eve/channels/auth";
import { mcpChannel } from "eve/channels/mcp";

declare const process: { env: Record<string, string | undefined> };

const username = process.env.MCP_USERNAME?.trim();
const password = process.env.MCP_PASSWORD;

if (Boolean(username) !== Boolean(password)) {
  throw new Error("Set both MCP_USERNAME and MCP_PASSWORD, or leave both unset for local development only.");
}

const auth = username && password
  ? [httpBasic({ username, password }, { realm: "MalariaPulse MCP" }), localDev()]
  : [localDev()];

export default mcpChannel({
  auth,
  route: "/eve/v1/mcp",
  tools: true
});
