# MalariaPulse

MalariaPulse is a safety-gated, multi-agent malaria early-warning and response MVP for county health teams, clinics, and community health workers. It combines aggregated clinical trends, environmental signals, and inventory telemetry to surface micro-zone risk, draft resource plans, and prepare localized outreach.

The repository contains four compatible surfaces backed by the same operational JSON data:

- a Streamlit operations dashboard for uploads, tabbed data entry, response review, and live AI analysis;
- a legacy zero-dependency Node operations console;
- an [Eve](https://eve.dev/docs) durable agent with three isolated specialists, a six-hour surveillance schedule, and human approval for operational release;
- an authenticated [Model Context Protocol (MCP)](https://modelcontextprotocol.io/docs/2026-07-28/getting-started/intro) endpoint that lets compatible AI clients invoke the durable agent and approved MalariaPulse tools.

## What works now

- Interpretable risk scores for six demo micro-zones from case acceleration, test positivity, rainfall, humidity, and temperature.
- `low`, `watch`, `high`, and `critical` tiers with confidence, projected cases, and explainable drivers.
- Facility-level RDT, ACT, and treated-net safety-stock estimates.
- Draft redistribution routes that preserve donor buffers and produce county restock requests for unresolved gaps.
- English and Kiswahili resident/CHW drafts with character and SMS-segment counts.
- A Streamlit operations dashboard with a risk watchlist, trends, inventory, agent response review, and approve/reject ledger.
- A polished session-based demo login and sidebar logout flow, with credentials that can be overridden from server configuration.
- A primary bulk-upload workspace for CSV, TSV, and JSON clinical, environmental, and supply files, with downloadable templates, full-file validation, and row-level errors.
- Optional single-record tabs for clinical reports, environmental observations, and facility supply telemetry; saved values immediately feed scoring and agent tools.
- A live AI operations analyst backed by the Google Gemini API, with county-wide and micro-zone reviews, structured findings, ranked priorities, and explicit data-quality notes.
- Downloadable PDF AI reports with the selected subcounty letterhead on the first page and clean continuation pages.
- Eve subagents for surveillance, supply, and community action, plus a root orchestrator and recurring schedule.
- A 2026-07-28-compatible MCP Streamable HTTP channel with durable-agent invocation, aggregate surveillance reads, and draft-only response generation.
- An always-on human approval gate before stock or outreach authorization.
- Node tests for scoring, planning, messaging, and orchestration.

## Architecture

```text
Aggregated feeds
      │
      ▼
Surveillance specialist ── risk tier + evidence
      │ high / critical
      ├──────────────┐
      ▼              ▼
Supply specialist   Community action specialist
      │              │
      └──────┬───────┘
             ▼
      Root orchestrator
             │
             ▼
       Human approval gate
             │
             ▼
   Future dispatch adapters (not connected)

MCP-compatible AI clients
             │ authenticated Streamable HTTP
             ▼
       /eve/v1/mcp
             │
             ├── durable agent_start / agent_get / agent_update / agent_cancel
             ├── read_surveillance_snapshot (read-only aggregates)
             └── draft_response_cycle (draft-only; no external action)
```

The browser demo executes the same three stages deterministically so it remains evaluable without an LLM or external service. Eve adds durable sessions, specialist delegation, scheduled runs, and approval semantics.

## Run the Streamlit dashboard

Python 3.11+ is recommended. From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env.local
# Add your GEMINI_API_KEY to .env.local
python3 -m streamlit run streamlit_app.py
```

Open `http://localhost:8501`. The Streamlit sidebar provides the full workflow: overview and agent response cycles, validated bulk upload, single-zone clinical and environmental corrections, facility supply entry, and live AI reviews. Every micro-zone field is a dropdown populated from the current dataset.

Use these sample credentials for the local demo. The login also provides **Show password** and an optional **Remember me** setting for faster return visits:

```text
Username: admin@malariapulse.demo
Password: DemoPulse!2026
```

These defaults are for demonstration only. Override both values in `.env.local` before sharing or deploying the app:

```bash
DEMO_USERNAME=your_demo_username
DEMO_PASSWORD=use_a_new_strong_password
REMEMBER_ME_SECRET=use_a_separate_long_random_value
```

Remember-me sessions last 14 days and store only a signed, expiring browser token—not the password. Leave the option unchecked on a shared device. Logging out clears the remembered browser session. This remains demonstration authentication; replace it with managed identity and server-side session revocation before production use.

The dashboard and existing Node/Eve implementation read and write the same ignored `data/operational.json` file, so data entered through either interface remains available to the others. Uploaded CSV, TSV, TXT, JSON, XLSX, and HTML/HTM files are limited to 1,000 aggregate rows and 2 MB. TXT files may use comma, tab, semicolon, or pipe delimiters. Excel imports use the first sheet and HTML imports use the first table. One invalid row blocks the entire import.

The Streamlit dashboard includes four aggregate data domains:

- Clinical surveillance: six-week cases, suspected cases, testing and positivity, severe cases, admissions, deaths, cases among children under five and pregnancy, CHW fever referrals, and reporting completeness.
- Environmental observations: 7-day and 30-day rainfall, temperature, humidity, standing-water index, and flooded or waterlogged sites.
- Intervention coverage: LLIN use, IPTp3 coverage, malaria-vaccine fourth-dose coverage, and larval-site management coverage with a source date.
- Supply readiness: RDT, ACT, and treated-net stock, weekly use, and weeks of coverage.

These additions reflect the [Kenya Malaria Strategy 2023–2027](https://extranet.who.int/cpcd/sites/default/files/public_file_repository/KEN_Kenya_National-Malaria-Strategy_2023-2027.pdf) and [WHO malaria surveillance indicator framework](https://www.who.int/publications/m/item/core-indicators-for-malaria-surveillance-monitoring-and-evaluation). They are presented as operational context; the uncalibrated risk score still uses only case acceleration, positivity, 7-day rainfall, humidity, and temperature. The bundled values are demonstration fixtures, not current surveillance observations.

The Gemini key stays on the Streamlit server. Create one in [Google AI Studio](https://aistudio.google.com/apikey). As an alternative to `.env.local`, create an ignored `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "your_key_here"
GEMINI_MODEL = "gemini-3.8-flash"
DEMO_USERNAME = "your_demo_username"
DEMO_PASSWORD = "use_a_new_strong_password"
```

For a Streamlit Community Cloud deployment, do not commit either `.env.local` or `.streamlit/secrets.toml`. Open the deployed app, select **Manage app → Settings → Secrets**, paste the TOML block above with a newly issued key, save it, and reboot the app. Community Cloud injects those values into `st.secrets` on the server and keeps them available across source-code redeployments.

If a real key is ever committed, revoke it in Google AI Studio and create a replacement. Removing the value in a later commit does not remove it from Git history.

This lightweight session gate is suitable for a prototype, not production identity management. Replace it with managed authentication, server-side sessions, role-based access, and audit logging before deployment.

The analyst uses the latest saved dataset for each request and returns a structured high-level review with evidence-backed findings, ranked actions, data-quality notes, and limitations. Resource movements and outreach remain drafts until a human reviewer approves them.

Run the Python checks with:

```bash
python3 -m unittest discover -s tests -p 'test_python_*.py'
```

## Run the legacy Node console

Node 24+ is the supported project runtime because Eve 0.79 requires it.

```bash
nvm use
npm install
cp .env.example .env.local
# Add your GEMINI_API_KEY to .env.local
npm run demo
```

Open `http://localhost:3000`. Use **Bulk upload** to choose a clinical, environment, or supply file, download its CSV template, validate the whole file, and apply it. CSV, TSV, and JSON are supported; imports are limited to 1,000 aggregate rows and 2 MB. One invalid row blocks the entire import, so the saved dataset is never partially updated. The single-record tabs remain available for corrections.

Saved values go to `data/operational.json`, which is ignored by Git, and immediately affect the dashboard, response cycles, Eve tools, and AI briefs. The immutable `data/seed.json` remains available as the original demo fixture. Patient-identifying columns are rejected; this MVP accepts aggregate zone and facility records only.

Open **AI analyst** after saving or importing data. The default **County network** scope compares every zone and facility for a high-level management review. You can also select one micro-zone, choose a suggested review, or enter an operational question. Each request reads `data/operational.json` again, so newly applied data are included without copying them into the AI form.

The API key stays on the server. The browser only receives connection status and never receives or stores the key. Restart the server after changing `.env.local`. The analyst returns a structured review containing an overall risk level, executive summary, evidence-backed findings, ranked actions, source-quality notes, and limitations.

The standalone console itself uses only Node built-ins, so its tests can also run in constrained environments before dependencies are installed:

```bash
npm test
npm run check
```

## Run the durable agent

Configure the same Gemini connection used by the dashboards, then start Eve:

```bash
cp .env.example .env.local
npm run dev:agent
```

Example prompts:

```text
Run the current network surveillance sweep and prepare drafts for every high-risk zone.
Assess Nyakach North and explain the top three drivers.
Prepare a response brief for Kano Plains, but do not request release approval yet.
```

Production schedules fire every six hours. During local Eve development, trigger the schedule once with:

```bash
curl -X POST http://localhost:2000/eve/v1/dev/schedules/surveillance_sweep
```

## Connect through MCP

MalariaPulse exposes an MCP Streamable HTTP endpoint through the Eve agent service:

```text
http://localhost:2000/eve/v1/mcp
```

Start the service with Node 24+:

```bash
nvm use
npm install
npm run dev:agent
```

In local Eve development, the endpoint uses Eve's development-only identity, which the production runtime rejects. For any deployed agent, set a separate MCP username and a long random password in the host's secret manager:

```bash
MCP_USERNAME=malariapulse-mcp
MCP_PASSWORD=replace_with_a_long_random_password
```

Never reuse the Streamlit demo login or commit the MCP password. The server fails closed in production when MCP credentials are absent. Replace HTTP Basic with an OIDC/OAuth protected-resource configuration before connecting external organizations or production health data.

The MCP server publishes:

- `agent_start`, `agent_get`, `agent_update`, and `agent_cancel` for durable multi-agent work;
- `read_surveillance_snapshot` for current aggregate network or micro-zone context;
- `draft_response_cycle` for a non-persistent, draft-only response cycle;
- `authorize_response`, which retains its human-approval requirement and has no dispatch adapter.

The endpoint follows MCP's tool-discovery and tool-call conventions. It does not expose uploaded source files, patient-level records, Gemini credentials, or Streamlit session credentials. All operational outputs remain proposals until an authorized human reviews them.

Streamlit Community Cloud runs the Streamlit process only; it does not start the Node/Eve MCP service beside it. Deploy the Eve service separately on a Node 24+ host, protect its public HTTPS endpoint, and configure the MCP client with the resulting `/eve/v1/mcp` URL. The Streamlit dashboard itself and its design are unchanged.

## Safety posture

This MVP is not a medical device, outbreak declaration system, or autonomous dispatch system. The data are synthetic. The score has not been epidemiologically calibrated, and an alert is not a confirmed outbreak. Before field use:

1. Replace seed data with approved, aggregated feeds and a clear data-sharing basis.
2. Calibrate thresholds on local historical surveillance data and report sensitivity, specificity, false-alert cost, uncertainty, and drift.
3. Add authentication, role-based authorization, audit retention, encryption, and tenant/county isolation.
4. Validate inventory units, facility master data, cold-chain or transport constraints, and stock-ledger reconciliation.
5. Have county epidemiology, pharmacy/logistics, clinical, community-health, and language leads approve workflows and templates.
6. Connect outbound SMS/WhatsApp and logistics systems only through idempotent adapters with explicit approval and delivery receipts.

The outreach language follows the prevention, prompt-testing, and care-seeking principles in the [WHO malaria fact sheet](https://www.who.int/news-room/fact-sheets/detail/malaria). Local policy and approved Ministry of Health templates take precedence.

## Repository guide

```text
agent/                         Eve root orchestrator
  channels/mcp.ts             Authenticated MCP Streamable HTTP endpoint
  subagents/surveillance/     Risk specialist and tool
  subagents/supply/           Inventory specialist and tool
  subagents/community_action/ Outreach specialist and tool
  schedules/                  Six-hour surveillance sweep
  tools/                      MCP-safe reads/drafts and human approval gate
data/seed.json                Synthetic county network
public/                       Operations console UI
malariapulse/                 Python domain and AI integration
streamlit_app.py              Primary Streamlit dashboard
requirements.txt              Python dashboard dependencies
src/domain/                   Shared scoring, planning, and message engine
src/server.mjs                Zero-dependency local API and static server
tests/                        Deterministic domain tests
```

## Next production milestones

- Ingestion adapters and data contracts for DHIS2/aggregate clinic reporting, weather observations, and stock systems.
- A time-series database with provenance, late-arriving-data handling, validation, and model monitoring.
- Retrospective backtesting and prospective shadow-mode evaluation with epidemiologists.
- Real geospatial routing and configurable facility safety-stock policies.
- Approved provider integrations for WhatsApp/SMS and logistics, both behind role-scoped approval.
- Authentication, county tenancy, observability, incident review, and disaster-recovery procedures.

