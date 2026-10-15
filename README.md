# MalariaPulse

MalariaPulse is a safety-gated, multi-agent malaria early-warning and response MVP for county health teams, clinics, and community health workers. It combines aggregated clinical trends, environmental signals, and inventory telemetry to surface micro-zone risk, draft resource plans, and prepare localized outreach.

The repository contains three compatible surfaces backed by the same operational JSON data:

- a Streamlit operations dashboard for uploads, tabbed data entry, response review, and live AI analysis;
- a legacy zero-dependency Node operations console;
- an [Eve](https://eve.dev/docs) durable agent with three isolated specialists, a six-hour surveillance schedule, and human approval for operational release.

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

Use these sample credentials for the local demo:

```text
Username: admin@malariapulse.demo
Password: DemoPulse!2026
```

These defaults are for demonstration only. Override both values in `.env.local` before sharing or deploying the app:

```bash
DEMO_USERNAME=your_demo_username
DEMO_PASSWORD=use_a_new_strong_password
```

The dashboard and existing Node/Eve implementation read and write the same ignored `data/operational.json` file, so data entered through either interface remains available to the others. Uploaded CSV, TSV, TXT, JSON, XLSX, and HTML/HTM files are limited to 1,000 aggregate rows and 2 MB. TXT files may use comma, tab, semicolon, or pipe delimiters. Excel imports use the first sheet and HTML imports use the first table. One invalid row blocks the entire import.

The Gemini key stays on the Streamlit server. Create one in [Google AI Studio](https://aistudio.google.com/apikey). As an alternative to `.env.local`, create an ignored `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "your_key_here"
GEMINI_MODEL = "gemini-3.8-flash"
DEMO_USERNAME = "your_demo_username"
DEMO_PASSWORD = "use_a_new_strong_password"
```

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
  subagents/surveillance/     Risk specialist and tool
  subagents/supply/           Inventory specialist and tool
  subagents/community_action/ Outreach specialist and tool
  schedules/                  Six-hour surveillance sweep
  tools/                      Human approval gate
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

