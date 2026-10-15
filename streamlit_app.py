"""MalariaPulse Streamlit operations console."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from malariapulse.ai import AIAnalystError, create_ai_review, get_ai_status
from malariapulse.core import (
    RESOURCE_LABELS,
    apply_data_import,
    assess_zone,
    build_network_snapshot,
    create_cycle,
    decide_cycle,
    import_template,
    latest_cycle,
    load_dataset,
    parse_data_import,
    update_clinical,
    update_environment,
    update_supply,
)

st.set_page_config(
    page_title="MalariaPulse",
    page_icon="🟢",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
      --mp-ink: #142923;
      --mp-muted: #60746d;
      --mp-green: #087f5b;
      --mp-mint: #dff7ec;
      --mp-amber: #f4a261;
      --mp-red: #d1495b;
      --mp-border: #dce8e3;
    }
    .stApp { background: #f7faf8; color: var(--mp-ink); }
    [data-testid="stSidebar"] { background: #102d27; }
    [data-testid="stSidebar"] * { color: #eef9f4; }
    [data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.14); }
    .mp-brand { font-size: 1.35rem; font-weight: 760; letter-spacing: -.03em; margin-bottom: .1rem; }
    .mp-brand span { color: #6ee7b7; }
    .mp-side-label { color: #b9d4c9; font-size: .76rem; text-transform: uppercase; letter-spacing: .08em; margin-top: 1.25rem; }
    .mp-header { padding: .35rem 0 .9rem; border-bottom: 1px solid var(--mp-border); margin-bottom: 1rem; }
    .mp-title { font-size: 2rem; font-weight: 760; letter-spacing: -.045em; line-height: 1.05; margin: 0; }
    .mp-subtitle { color: var(--mp-muted); margin: .4rem 0 0; font-size: .95rem; }
    .mp-chip { display: inline-block; padding: .22rem .55rem; border-radius: 999px; font-size: .73rem; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }
    .mp-chip-low { background: #e7f7ef; color: #0b6b4b; }
    .mp-chip-watch { background: #fff1cf; color: #8c5b00; }
    .mp-chip-high { background: #ffe2c4; color: #a34700; }
    .mp-chip-critical { background: #ffe1e5; color: #a32134; }
    .mp-panel { background: white; border: 1px solid var(--mp-border); border-radius: 14px; padding: 1rem; }
    .mp-eyebrow { color: var(--mp-green); font-size: .74rem; font-weight: 750; letter-spacing: .07em; text-transform: uppercase; }
    .mp-headline { font-size: 1.28rem; font-weight: 730; letter-spacing: -.02em; margin: .25rem 0; }
    .mp-muted { color: var(--mp-muted); }
    .mp-finding { background: white; border-left: 4px solid var(--mp-green); border-radius: 4px 12px 12px 4px; padding: .85rem 1rem; margin-bottom: .75rem; }
    div[data-testid="stMetric"] { background: white; border: 1px solid var(--mp-border); border-radius: 14px; padding: .85rem 1rem; }
    div[data-testid="stMetricLabel"] { color: var(--mp-muted); }
    div[data-testid="stMetricValue"] { color: var(--mp-ink); }
    .stTabs [data-baseweb="tab-list"] { gap: .25rem; border-bottom: 1px solid var(--mp-border); }
    .stTabs [data-baseweb="tab"] { height: 2.8rem; border-radius: 9px 9px 0 0; padding: 0 .9rem; }
    .stTabs [aria-selected="true"] { background: #e8f6ef; color: var(--mp-green); }
    .stButton > button[kind="primary"] { background: var(--mp-green); border-color: var(--mp-green); }
    @media (max-width: 800px) { .mp-title { font-size: 1.55rem; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def _format_time(value: str | None) -> str:
    if not value:
        return "Unknown"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.strftime("%d %b %Y, %H:%M UTC")
    except ValueError:
        return value


def _secret(name: str) -> str | None:
    try:
        value = st.secrets.get(name)
        return str(value) if value else None
    except Exception:  # Streamlit raises its own missing-secrets exception when no file exists.
        return None


def _zone_names(dataset: dict[str, Any]) -> dict[str, str]:
    return {zone["id"]: zone["name"] for zone in dataset["zones"]}


def _clinic_names(dataset: dict[str, Any]) -> dict[str, str]:
    return {clinic["id"]: clinic["name"] for clinic in dataset["clinics"]}


def _risk_chip(level: str) -> str:
    safe_level = level if level in {"low", "watch", "high", "critical"} else "watch"
    return f'<span class="mp-chip mp-chip-{safe_level}">{safe_level}</span>'


def _render_cycle(cycle: dict[str, Any] | None) -> None:
    if not cycle:
        st.info("No response cycle has been run yet.")
        return
    status_col, time_col, scope_col = st.columns(3)
    status_col.metric("Cycle status", cycle["status"].replace("_", " ").title())
    time_col.metric("Created", _format_time(cycle.get("createdAt")))
    scope_label = cycle["assessments"][0]["zoneName"] if len(cycle["assessments"]) == 1 else "County network"
    scope_col.metric("Scope", scope_label)

    if cycle["interventions"]:
        for intervention in cycle["interventions"]:
            with st.expander(f"{intervention['zoneName']} response draft", expanded=True):
                assessment = intervention["assessment"]
                st.markdown(
                    f"{_risk_chip(assessment['riskLevel'])} &nbsp; Risk score **{assessment['score']}/100** · "
                    f"projected next-week cases **{assessment['expectedCasesNextWeek']}**",
                    unsafe_allow_html=True,
                )
                supply_plan = intervention["supplyPlan"]
                st.caption(supply_plan["note"])
                if supply_plan["recommendations"]:
                    moves = pd.DataFrame(
                        [
                            {
                                "Resource": move["resourceLabel"],
                                "Quantity": move["quantity"],
                                "From": move["fromClinic"],
                                "To": move["toClinic"],
                                "ETA (min)": move["etaMinutes"],
                            }
                            for move in supply_plan["recommendations"]
                        ]
                    )
                    st.dataframe(moves, hide_index=True, width="stretch")
                if supply_plan["restockRequests"]:
                    st.warning(f"{len(supply_plan['restockRequests'])} unresolved county restock request(s) require review.")
                message_tabs = st.tabs(
                    [f"{message['audience'].title()} · {message['language']}" for message in intervention["advisories"]["messages"]]
                )
                for message_tab, message in zip(message_tabs, intervention["advisories"]["messages"]):
                    with message_tab:
                        st.write(message["text"])
                        st.caption(f"{message['characters']} characters · {message['segments']} SMS segment(s) · draft only")
    else:
        st.success("No high or critical threshold was crossed. Continue surveillance.")

    st.dataframe(
        pd.DataFrame(
            [
                {"Agent": item["agent"], "Status": item["status"], "Detail": item["detail"]}
                for item in cycle["audit"]
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    if cycle["status"] == "pending_approval":
        reviewer = st.text_input("Reviewer name or role", value="County operations reviewer", key=f"reviewer-{cycle['id']}")
        approve_col, reject_col, _ = st.columns([1, 1, 4])
        if approve_col.button("Approve drafts", type="primary", key=f"approve-{cycle['id']}"):
            decide_cycle(cycle["id"], "approve", reviewer)
            st.rerun()
        if reject_col.button("Reject drafts", key=f"reject-{cycle['id']}"):
            decide_cycle(cycle["id"], "reject", reviewer)
            st.rerun()


def _render_ai_review(result: dict[str, Any]) -> None:
    review = result["review"]
    with st.container(border=True):
        st.caption("AI OPERATIONS REVIEW")
        st.subheader(review["headline"])
        st.markdown(_risk_chip(review["overallRisk"]), unsafe_allow_html=True)
    st.subheader("Executive summary")
    st.write(review["executiveSummary"])
    st.subheader("Key findings")
    for finding in review["keyFindings"]:
        with st.container(border=True):
            st.markdown(f"**{finding['title']}**")
            st.write(finding["evidence"])
            st.caption(finding["implication"])
    st.subheader("Ranked priorities")
    priority_rows = [
        {
            "Rank": item["rank"],
            "Action": item["action"],
            "Owner": item["owner"],
            "Timeframe": item["timeframe"],
            "Approval": "Required" if item["requiresApproval"] else "Not required",
            "Rationale": item["rationale"],
        }
        for item in review["priorities"]
    ]
    if priority_rows:
        st.dataframe(pd.DataFrame(priority_rows).sort_values("Rank"), hide_index=True, width="stretch")
    else:
        st.info("The review did not identify any ranked priorities.")
    quality_col, limits_col = st.columns(2)
    with quality_col:
        st.subheader("Data quality")
        st.write(f"**Freshness:** {review['dataQuality']['freshness']}")
        st.write(f"**Completeness:** {review['dataQuality']['completeness']}")
        for concern in review["dataQuality"]["concerns"]:
            st.write(f"• {concern}")
    with limits_col:
        st.subheader("Limitations")
        for limitation in review["limitations"]:
            st.write(f"• {limitation}")
    st.caption(
        f"Generated {_format_time(result['generatedAt'])} with {result['model']} · "
        f"source updated {_format_time(result.get('sourceUpdatedAt'))} · OpenAI response {result.get('responseId') or 'not supplied'}"
    )


dataset = load_dataset()
snapshot = build_network_snapshot(dataset)
zone_names = _zone_names(dataset)
clinic_names = _clinic_names(dataset)
api_key = _secret("OPENAI_API_KEY")
api_model = _secret("OPENAI_MODEL")
ai_status = get_ai_status(api_key=api_key, model=api_model)

with st.sidebar:
    st.markdown('<div class="mp-brand">Malaria<span>Pulse</span></div>', unsafe_allow_html=True)
    st.caption("County early warning & response")
    st.markdown('<div class="mp-side-label">Reporting context</div>', unsafe_allow_html=True)
    st.write(f"**{dataset['metadata']['county']}, {dataset['metadata']['country']}**")
    st.write(f"Week {dataset['metadata']['reportingWeek']}")
    st.caption(f"Updated {_format_time(dataset['metadata'].get('updatedAt'))}")
    st.divider()
    st.markdown('<div class="mp-side-label">AI analyst</div>', unsafe_allow_html=True)
    if ai_status["configured"]:
        st.success(f"Connected · {ai_status['model']}")
    else:
        st.warning("API key not configured")
        st.caption("Add OPENAI_API_KEY to .env.local or .streamlit/secrets.toml, then restart.")
    st.divider()
    st.caption("Aggregate operational data only. Never upload names, phone numbers, patient IDs, or addresses.")

st.markdown(
    """
    <div class="mp-header">
      <div class="mp-title">Malaria operations command view</div>
      <div class="mp-subtitle">Surveillance, resource readiness, intervention drafts, and an evidence-grounded AI analyst in one workspace.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

overview_tab, upload_tab, clinical_tab, environment_tab, supply_tab, ai_tab = st.tabs(
    ["Overview", "Bulk upload", "Clinical", "Environment", "Supply", "AI analyst"]
)

with overview_tab:
    summary = snapshot["summary"]
    first, second, third, fourth = st.columns(4)
    first.metric("Zones monitored", summary["zonesMonitored"])
    second.metric("High / critical", summary["highRiskZones"], help="Zones scoring 60 or higher")
    third.metric("Facilities reporting", summary["facilitiesReporting"])
    fourth.metric("Supply readiness", f"{summary['supplyReadinessPct']}%", help="Average three-week stock coverage, capped at 100%")

    focus_col, action_col = st.columns([2, 1])
    with focus_col:
        selected_zone_id = st.selectbox(
            "Micro-zone detail",
            list(zone_names),
            format_func=zone_names.get,
            key="overview-zone",
        )
    with action_col:
        cycle_scope = st.selectbox(
            "Response-cycle scope",
            ["network", *zone_names],
            format_func=lambda item: "County network" if item == "network" else zone_names[item],
            key="cycle-scope",
        )
        if st.button("Run agent response cycle", type="primary", width="stretch"):
            create_cycle(None if cycle_scope == "network" else cycle_scope)
            st.rerun()

    selected_zone = next(zone for zone in dataset["zones"] if zone["id"] == selected_zone_id)
    assessment = assess_zone(selected_zone, dataset["metadata"])
    chart_col, signal_col = st.columns([3, 2])
    with chart_col:
        st.subheader(f"Six-week cases · {selected_zone['name']}")
        trend = pd.DataFrame(
            {
                "Week": ["W-5", "W-4", "W-3", "W-2", "W-1", "Current"],
                "Reported cases": selected_zone["weeklyCases"],
            }
        ).set_index("Week")
        st.line_chart(trend, color="#087f5b")
        st.caption(
            f"{selected_zone['tests']} tests · {selected_zone['positiveTests']} positive · "
            f"{assessment['positivityPct']}% positivity · {assessment['incidencePerThousand']} cases per 1,000"
        )
    with signal_col:
        st.subheader("Risk signal")
        st.markdown(f"{_risk_chip(assessment['riskLevel'])}", unsafe_allow_html=True)
        st.metric("Risk score", f"{assessment['score']} / 100", f"{assessment['growthPct']}% case acceleration")
        st.write(assessment["recommendation"])
        st.caption(f"Expected next week: {assessment['expectedCasesNextWeek']} cases · confidence {assessment['confidence']:.0%}")
        for driver in assessment["drivers"]:
            st.progress(min(driver["contribution"] / 40, 1.0), text=f"{driver['label']} · {driver['contribution']} points")

    st.subheader("County risk watchlist")
    risk_rows = pd.DataFrame(
        [
            {
                "Micro-zone": item["zoneName"],
                "Sub-county": item["subcounty"],
                "Risk": item["riskLevel"].title(),
                "Score": item["score"],
                "Latest cases": item["currentCases"],
                "Projected": item["expectedCasesNextWeek"],
                "Growth": f"{item['growthPct']}%",
                "Positivity": f"{item['positivityPct']}%",
            }
            for item in snapshot["assessments"]
        ]
    )
    st.dataframe(risk_rows, hide_index=True, width="stretch")

    with st.expander("Latest multi-agent response cycle", expanded=latest_cycle() is not None):
        _render_cycle(latest_cycle())

    with st.expander("Data source and scoring notes"):
        st.write(
            "The displayed risk score is a deterministic operational signal combining six-week case acceleration (40%), "
            "test positivity (23%), 7-day rainfall (16%), humidity (11%), and temperature suitability (10%)."
        )
        st.write(
            f"Source mode: **{dataset['metadata'].get('mode', 'unknown')}** · reporting week: "
            f"**{dataset['metadata']['reportingWeek']}** · stated completeness: "
            f"**{dataset['metadata'].get('dataCompleteness', 0):.0%}**."
        )
        st.warning("This is an uncalibrated MVP signal, not a confirmed outbreak, diagnostic system, or autonomous dispatch decision.")

with upload_tab:
    st.subheader("Bulk data upload")
    st.write("Upload aggregate clinical, environmental, or supply data. The full file is validated before any row is saved.")
    kind_labels = {"clinical": "Clinical surveillance", "environment": "Environmental observations", "supply": "Facility supply telemetry"}
    upload_kind = st.selectbox("Data type", list(kind_labels), format_func=kind_labels.get, key="upload-kind")
    template_col, note_col = st.columns([1, 3])
    with template_col:
        st.download_button(
            "Download current CSV template",
            data=import_template(upload_kind, dataset),
            file_name=f"malariapulse-{upload_kind}-template.csv",
            mime="text/csv",
            width="stretch",
        )
    with note_col:
        st.caption("Accepted formats: CSV, TSV, and JSON · maximum 1,000 rows / 2 MB · invalid files are never partially applied")
    uploaded = st.file_uploader(
        f"Choose {kind_labels[upload_kind].lower()} file",
        type=["csv", "tsv", "json"],
        key=f"uploader-{upload_kind}",
    )
    if uploaded is not None:
        try:
            preview = parse_data_import(upload_kind, uploaded.name, uploaded.getvalue(), dataset)
            status_first, status_second, status_third = st.columns(3)
            status_first.metric("Rows", preview["rowCount"])
            status_second.metric("Valid", preview["validCount"])
            status_third.metric("Invalid", preview["invalidCount"])
            for message in preview["fileErrors"]:
                st.error(message)
            for message in preview["warnings"]:
                st.warning(message)
            table_rows = [
                {
                    "Row": row["rowNumber"],
                    "ID": row["identifier"],
                    "Status": "Valid" if row["valid"] else "Invalid",
                    "Preview": row["preview"],
                    "Errors": " ".join(row["errors"]),
                }
                for row in preview["rows"]
            ]
            st.dataframe(pd.DataFrame(table_rows), hide_index=True, width="stretch")
            if preview["canApply"]:
                if st.button(f"Apply {preview['rowCount']} validated row(s)", type="primary", key="apply-upload"):
                    apply_data_import(preview)
                    st.success("Import applied. All dashboard calculations now use the updated dataset.")
                    st.rerun()
            else:
                st.info("Correct every error and upload the file again before applying it.")
        except ValueError as error:
            st.error(str(error))
    else:
        st.info("Download the template first if you need the accepted IDs and column names.")

with clinical_tab:
    st.subheader("Clinical surveillance entry")
    st.caption("Use bulk upload for routine reporting; this form is for a single-zone correction.")
    clinical_zone_id = st.selectbox("Micro-zone", list(zone_names), format_func=zone_names.get, key="clinical-zone")
    clinical_zone = next(zone for zone in dataset["zones"] if zone["id"] == clinical_zone_id)
    with st.form(f"clinical-form-{clinical_zone_id}"):
        reporting_week = st.text_input("Reporting week", value=dataset["metadata"]["reportingWeek"], help="Format: YYYY-Www")
        week_columns = st.columns(3)
        weekly_cases: list[int] = []
        for index, value in enumerate(clinical_zone["weeklyCases"]):
            with week_columns[index % 3]:
                weekly_cases.append(
                    st.number_input(f"Week {index + 1} cases", min_value=0, value=int(value), step=1, key=f"clinical-{clinical_zone_id}-{index}")
                )
        tests_col, positive_col = st.columns(2)
        tests = tests_col.number_input("Tests performed", min_value=0, value=int(clinical_zone["tests"]), step=1)
        positive_tests = positive_col.number_input("Positive tests", min_value=0, value=int(clinical_zone["positiveTests"]), step=1)
        submitted = st.form_submit_button("Save clinical data", type="primary")
        if submitted:
            try:
                update_clinical(clinical_zone_id, weekly_cases, tests, positive_tests, reporting_week)
                st.success("Clinical data saved.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))

with environment_tab:
    st.subheader("Environmental observation entry")
    st.caption("Use bulk upload for routine feeds; this form is for a single-zone correction.")
    environment_zone_id = st.selectbox("Micro-zone", list(zone_names), format_func=zone_names.get, key="environment-zone")
    environment_zone = next(zone for zone in dataset["zones"] if zone["id"] == environment_zone_id)
    environment = environment_zone["environment"]
    with st.form(f"environment-form-{environment_zone_id}"):
        rain_col, temp_col, humidity_col = st.columns(3)
        rainfall = rain_col.number_input("Rainfall, last 7 days (mm)", min_value=0.0, max_value=2000.0, value=float(environment["rainfall7dMm"]), step=1.0)
        temperature = temp_col.number_input("Mean temperature (°C)", min_value=-10.0, max_value=60.0, value=float(environment["temperatureC"]), step=0.1)
        humidity = humidity_col.number_input("Mean humidity (%)", min_value=0.0, max_value=100.0, value=float(environment["humidityPct"]), step=1.0)
        submitted = st.form_submit_button("Save environmental data", type="primary")
        if submitted:
            try:
                update_environment(environment_zone_id, rainfall, temperature, humidity)
                st.success("Environmental data saved.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))

with supply_tab:
    st.subheader("Facility supply entry")
    st.caption("Update stock on hand and average weekly use. Quantities are whole units.")
    supply_clinic_id = st.selectbox("Facility", list(clinic_names), format_func=clinic_names.get, key="supply-clinic")
    supply_clinic = next(clinic for clinic in dataset["clinics"] if clinic["id"] == supply_clinic_id)
    with st.form(f"supply-form-{supply_clinic_id}"):
        st.markdown("**Stock on hand**")
        stock_columns = st.columns(3)
        stock = {
            resource: stock_columns[index].number_input(
                RESOURCE_LABELS[resource], min_value=0, value=int(supply_clinic["stock"][resource]), step=1, key=f"stock-{supply_clinic_id}-{resource}"
            )
            for index, resource in enumerate(RESOURCE_LABELS)
        }
        st.markdown("**Average weekly use**")
        use_columns = st.columns(3)
        weekly_use = {
            resource: use_columns[index].number_input(
                RESOURCE_LABELS[resource], min_value=0, value=int(supply_clinic["weeklyUse"][resource]), step=1, key=f"use-{supply_clinic_id}-{resource}"
            )
            for index, resource in enumerate(RESOURCE_LABELS)
        }
        submitted = st.form_submit_button("Save supply data", type="primary")
        if submitted:
            try:
                update_supply(supply_clinic_id, stock, weekly_use)
                st.success("Supply data saved.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))

    st.subheader("County inventory coverage")
    inventory_rows = []
    for clinic in dataset["clinics"]:
        def coverage(resource: str) -> float | None:
            weekly = clinic["weeklyUse"][resource]
            return round(clinic["stock"][resource] / weekly, 1) if weekly > 0 else None

        inventory_rows.append(
            {
                "Facility": clinic["name"],
                "Micro-zone": zone_names[clinic["zoneId"]],
                "RDT stock": clinic["stock"]["rdt"],
                "RDT weeks": coverage("rdt"),
                "ACT stock": clinic["stock"]["act"],
                "ACT weeks": coverage("act"),
                "Net stock": clinic["stock"]["nets"],
                "Net weeks": coverage("nets"),
            }
        )
    st.dataframe(pd.DataFrame(inventory_rows), hide_index=True, width="stretch")

with ai_tab:
    st.subheader("AI operations analyst")
    st.write("Generate a high-level management review from the latest aggregate clinical, environmental, and supply data.")
    if ai_status["configured"]:
        st.success(f"OpenAI Responses API connected · {ai_status['model']} · key remains server-side")
    else:
        st.warning("The analyst needs OPENAI_API_KEY in .env.local or .streamlit/secrets.toml. Restart Streamlit after adding it.")
        st.code("OPENAI_API_KEY=your_key_here\nOPENAI_MODEL=gpt-6-astra", language="bash")

    ai_scope = st.selectbox(
        "Review scope",
        ["network", *zone_names],
        format_func=lambda item: "County network" if item == "network" else zone_names[item],
        key="ai-scope",
    )
    prompts = {
        "Executive situation review": "Give a high-level situation review and identify what the county response team should prioritize next.",
        "Outbreak signal review": "Compare the risk signals and explain which possible outbreak signals require verification first.",
        "Supply readiness review": "Review supply readiness against the current risk picture and identify the most urgent gaps.",
        "Data quality review": "Assess whether the available data are strong enough for operational decisions and identify the most important gaps.",
    }
    prompt_name = st.selectbox("Suggested review", list(prompts), key="ai-preset")
    question = st.text_area("Question for the analyst", value=prompts[prompt_name], height=100, key=f"ai-question-{prompt_name}")
    if st.button("Generate live AI review", type="primary", disabled=not ai_status["configured"], key="generate-ai"):
        try:
            with st.spinner("Reviewing current surveillance, environmental, and supply evidence…"):
                st.session_state["ai_result"] = create_ai_review(
                    load_dataset(),
                    scope_id=ai_scope,
                    question=question,
                    api_key=api_key,
                    model=api_model,
                )
        except AIAnalystError as error:
            st.error(str(error))
        except Exception as error:  # Keep operational failures visible without exposing credentials.
            st.error(f"The AI review could not be generated: {error}")

    ai_result = st.session_state.get("ai_result")
    if ai_result:
        if ai_result.get("sourceUpdatedAt") != dataset["metadata"].get("updatedAt"):
            st.warning("The dataset changed after this review was generated. Generate a new review for current evidence.")
        _render_ai_review(ai_result)
    else:
        st.info("No live review has been generated in this session.")
