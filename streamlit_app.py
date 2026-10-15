"""MalariaPulse Streamlit operations console."""

from __future__ import annotations

import hmac
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from malariapulse.ai import AIAnalystError, create_ai_review, get_ai_status, get_setting
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
      --mp-ink: #15233a;
      --mp-muted: #647188;
      --mp-blue: #246bfd;
      --mp-blue-deep: #1555d7;
      --mp-blue-soft: #e9f0ff;
      --mp-green: #14865f;
      --mp-amber: #e49b24;
      --mp-red: #e6534c;
      --mp-border: #e5e9ef;
    }
    .stApp { background: #f5f7fa; color: var(--mp-ink); }
    [data-testid="stSidebar"] { background: #101f34; }
    [data-testid="stSidebar"] * { color: #d8e2f1; }
    [data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.14); }
    .mp-brand { font-size: 1.35rem; font-weight: 760; letter-spacing: -.03em; margin-bottom: .1rem; }
    .mp-brand span { color: #6ea1ff; }
    .mp-side-label { color: #75849b; font-size: .67rem; font-weight: 800; text-transform: uppercase; letter-spacing: .11em; margin: 1.25rem 0 .5rem; }
    .mp-header { padding: .35rem 0 .9rem; border-bottom: 1px solid var(--mp-border); margin-bottom: 1rem; }
    .mp-title { font-size: 2rem; font-weight: 760; letter-spacing: -.045em; line-height: 1.05; margin: 0; }
    .mp-subtitle { color: var(--mp-muted); margin: .4rem 0 0; font-size: .95rem; }
    .mp-chip { display: inline-block; padding: .22rem .55rem; border-radius: 999px; font-size: .73rem; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }
    .mp-chip-low { background: #e7f7ef; color: #0b6b4b; }
    .mp-chip-watch { background: #fff1cf; color: #8c5b00; }
    .mp-chip-high { background: #ffe2c4; color: #a34700; }
    .mp-chip-critical { background: #ffe1e5; color: #a32134; }
    .mp-panel { background: white; border: 1px solid var(--mp-border); border-radius: 14px; padding: 1rem; }
    .mp-eyebrow { color: var(--mp-blue); font-size: .74rem; font-weight: 750; letter-spacing: .07em; text-transform: uppercase; }
    .mp-headline { font-size: 1.28rem; font-weight: 730; letter-spacing: -.02em; margin: .25rem 0; }
    .mp-muted { color: var(--mp-muted); }
    .mp-finding { background: white; border-left: 4px solid var(--mp-blue); border-radius: 4px 12px 12px 4px; padding: .85rem 1rem; margin-bottom: .75rem; }
    div[data-testid="stMetric"] { background: white; border: 1px solid var(--mp-border); border-radius: 14px; padding: .85rem 1rem; }
    div[data-testid="stMetricLabel"] { color: var(--mp-muted); }
    div[data-testid="stMetricValue"] { color: var(--mp-ink); }
    .stTabs [data-baseweb="tab-list"] { gap: .25rem; border-bottom: 1px solid var(--mp-border); }
    .stTabs [data-baseweb="tab"] { height: 2.8rem; border-radius: 9px 9px 0 0; padding: 0 .9rem; }
    .stTabs [aria-selected="true"] { background: var(--mp-blue-soft); color: var(--mp-blue); }
    .stButton > button[kind="primary"] { background: var(--mp-blue); border-color: var(--mp-blue); }
    .stButton > button[kind="primary"]:hover { background: var(--mp-blue-deep); border-color: var(--mp-blue-deep); }
    .mp-login-brand { text-align: center; color: var(--mp-ink); font-size: 1.65rem; font-weight: 780; letter-spacing: -.04em; margin-bottom: .1rem; }
    .mp-login-brand span { color: var(--mp-blue); }
    .mp-login-subtitle { text-align: center; color: var(--mp-muted); font-size: .86rem; margin-bottom: 1.25rem; }
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] { gap: .2rem; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label { border-left: 3px solid transparent; border-radius: 8px; padding: .58rem .65rem; transition: .16s ease; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background: rgba(255,255,255,.055); }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) { background: #1d3659; border-left-color: #5d91ff; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label p { color: #9eacc1; font-size: .84rem; font-weight: 650; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) p { color: #fff; }
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


def _authentication_config() -> tuple[str, str, bool]:
    username_override = _secret("DEMO_USERNAME") or get_setting("DEMO_USERNAME")
    password_override = _secret("DEMO_PASSWORD") or get_setting("DEMO_PASSWORD")
    return (
        username_override or "admin@malariapulse.demo",
        password_override or "DemoPulse!2026",
        bool(username_override or password_override),
    )


def _render_login() -> None:
    configured_username, configured_password, credentials_overridden = _authentication_config()
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="stHeader"] { background: transparent; }
        .block-container { max-width: 64rem; padding-top: 5rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _, login_column, _ = st.columns([1, 1.05, 1])
    with login_column:
        st.markdown(
            '<div class="mp-login-brand">Malaria<span>Pulse</span></div>'
            '<div class="mp-login-subtitle">County early warning & response</div>',
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            st.subheader("Sign in")
            st.caption("Enter your credentials to continue.")
            with st.form("login-form"):
                username = st.text_input(
                    "Email or username",
                    placeholder="name@county-health.example",
                    key="login-username",
                )
                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Enter your password",
                    key="login-password",
                )
                submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
                if submitted:
                    username_matches = hmac.compare_digest(username.strip(), configured_username)
                    password_matches = hmac.compare_digest(password, configured_password)
                    if username_matches and password_matches:
                        st.session_state["authenticated"] = True
                        st.session_state["authenticated_user"] = configured_username
                        st.rerun()
                    else:
                        st.error("The username or password is incorrect. Check the demo credentials and try again.")

        if credentials_overridden:
            st.caption("Login credentials are configured by the server.")
        else:
            st.caption("Demo credentials")
            st.code("admin@malariapulse.demo\nDemoPulse!2026", language=None)


def _zone_names(dataset: dict[str, Any]) -> dict[str, str]:
    return {zone["id"]: zone["name"] for zone in dataset["zones"]}


def _clinic_names(dataset: dict[str, Any]) -> dict[str, str]:
    return {clinic["id"]: clinic["name"] for clinic in dataset["clinics"]}


def _risk_chip(level: str) -> str:
    safe_level = level if level in {"low", "watch", "high", "critical"} else "watch"
    return f'<span class="mp-chip mp-chip-{safe_level}">{safe_level}</span>'


def _set_flash(page: str, message: str) -> None:
    """Keep save/import feedback visible after Streamlit reloads the dataset."""
    st.session_state["data-flash"] = {"page": page, "message": message}
    st.session_state.pop("ai_result", None)


def _render_flash(page: str) -> None:
    flash = st.session_state.get("data-flash")
    if flash and flash.get("page") == page:
        st.success(flash["message"], icon="✅")
        del st.session_state["data-flash"]


def _render_file_upload(kind: str, dataset: dict[str, Any], *, key_prefix: str, return_page: str) -> None:
    kind_labels = {
        "clinical": "Clinical surveillance",
        "environment": "Environmental observations",
        "supply": "Facility supply telemetry",
    }
    label = kind_labels[kind]
    st.write(f"Upload aggregate {label.lower()} data. Every row is validated before anything is saved.")
    template_col, note_col = st.columns([1, 3])
    with template_col:
        st.download_button(
            "Download current CSV template",
            data=import_template(kind, dataset),
            file_name=f"malariapulse-{kind}-template.csv",
            mime="text/csv",
            width="stretch",
            key=f"{key_prefix}-template",
        )
    with note_col:
        st.caption(
            "Accepted: CSV, TSV, TXT, JSON, XLSX, HTML/HTM · first Excel sheet or HTML table · "
            "maximum 1,000 rows / 2 MB · invalid files are never partially applied"
        )
    uploaded = st.file_uploader(
        f"Choose {label.lower()} file",
        type=["csv", "tsv", "txt", "json", "xlsx", "html", "htm"],
        key=f"{key_prefix}-uploader",
    )
    if uploaded is None:
        st.info("Download the template first if you need the accepted IDs and column names.")
        return

    try:
        preview = parse_data_import(kind, uploaded.name, uploaded.getvalue(), dataset)
    except ValueError as error:
        st.error(str(error))
        return

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
    if not preview["canApply"]:
        st.info("Correct every error and upload the file again before applying it.")
        return

    if st.button(
        f"Apply {preview['rowCount']} validated row(s)",
        type="primary",
        width="stretch",
        key=f"{key_prefix}-apply",
    ):
        apply_data_import(preview)
        _set_flash(
            return_page,
            f"{label} import saved successfully. All dashboard calculations now use the updated data.",
        )
        st.rerun()


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


if not st.session_state.get("authenticated", False):
    _render_login()
    st.stop()


dataset = load_dataset()
snapshot = build_network_snapshot(dataset)
zone_names = _zone_names(dataset)
clinic_names = _clinic_names(dataset)
api_key = _secret("OPENAI_API_KEY")
api_model = _secret("OPENAI_MODEL")
ai_status = get_ai_status(api_key=api_key, model=api_model)

page_copy = {
    "Overview": ("Malaria operations command view", "Surveillance signals, county priorities, and multi-agent response drafts."),
    "Bulk data upload": ("Bulk data upload", "Validate and apply aggregate clinical, environmental, or supply files."),
    "Clinical data": ("Clinical surveillance entry", "Correct one micro-zone or use bulk upload for routine reporting."),
    "Environmental data": ("Environmental observation entry", "Update rainfall, temperature, and humidity by micro-zone."),
    "Supply data": ("Facility supply entry", "Review and update facility stock and average weekly use."),
    "AI analyst": ("AI operations analyst", "Generate an evidence-grounded review from the latest saved data."),
}

with st.sidebar:
    st.markdown('<div class="mp-brand">Malaria<span>Pulse</span></div>', unsafe_allow_html=True)
    st.caption("County early warning & response")
    st.markdown('<div class="mp-side-label">Signed in</div>', unsafe_allow_html=True)
    st.caption(st.session_state.get("authenticated_user", "Demo operator"))
    if st.button("Log out", key="logout", width="stretch"):
        st.session_state.clear()
        st.rerun()
    st.markdown('<div class="mp-side-label">Workspace</div>', unsafe_allow_html=True)
    active_page = st.radio(
        "Workspace",
        list(page_copy),
        label_visibility="collapsed",
        key="workspace-page",
    )
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

page_title, page_subtitle = page_copy[active_page]
st.markdown(
    f"""
    <div class="mp-header">
      <div class="mp-title">{page_title}</div>
      <div class="mp-subtitle">{page_subtitle}</div>
    </div>
    """,
    unsafe_allow_html=True,
)
_render_flash(active_page)

if active_page == "Overview":
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
        st.line_chart(trend, color="#246bfd")
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

elif active_page == "Bulk data upload":
    kind_labels = {"clinical": "Clinical surveillance", "environment": "Environmental observations", "supply": "Facility supply telemetry"}
    upload_kind = st.selectbox("Data type", list(kind_labels), format_func=kind_labels.get, key="upload-kind")
    _render_file_upload(upload_kind, dataset, key_prefix=f"bulk-{upload_kind}", return_page="Bulk data upload")

elif active_page == "Clinical data":
    clinical_manual_tab, clinical_upload_tab = st.tabs(["Manual entry", "File upload"])
    with clinical_manual_tab:
        st.caption("Use this form for a single-zone correction.")
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
            submitted = st.form_submit_button("Save clinical data", type="primary", width="stretch")
            if submitted:
                try:
                    update_clinical(clinical_zone_id, weekly_cases, tests, positive_tests, reporting_week)
                    _set_flash(
                        "Clinical data",
                        f"Clinical data for {zone_names[clinical_zone_id]} saved successfully. The dashboard and AI analyst now use these values.",
                    )
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
    with clinical_upload_tab:
        _render_file_upload("clinical", dataset, key_prefix="clinical-inline", return_page="Clinical data")

elif active_page == "Environmental data":
    environment_manual_tab, environment_upload_tab = st.tabs(["Manual entry", "File upload"])
    with environment_manual_tab:
        st.caption("Use this form for a single-zone correction.")
        environment_zone_id = st.selectbox("Micro-zone", list(zone_names), format_func=zone_names.get, key="environment-zone")
        environment_zone = next(zone for zone in dataset["zones"] if zone["id"] == environment_zone_id)
        environment = environment_zone["environment"]
        with st.form(f"environment-form-{environment_zone_id}"):
            rain_col, temp_col, humidity_col = st.columns(3)
            rainfall = rain_col.number_input("Rainfall, last 7 days (mm)", min_value=0.0, max_value=2000.0, value=float(environment["rainfall7dMm"]), step=1.0)
            temperature = temp_col.number_input("Mean temperature (°C)", min_value=-10.0, max_value=60.0, value=float(environment["temperatureC"]), step=0.1)
            humidity = humidity_col.number_input("Mean humidity (%)", min_value=0.0, max_value=100.0, value=float(environment["humidityPct"]), step=1.0)
            submitted = st.form_submit_button("Save environmental data", type="primary", width="stretch")
            if submitted:
                try:
                    update_environment(environment_zone_id, rainfall, temperature, humidity)
                    _set_flash(
                        "Environmental data",
                        f"Environmental data for {zone_names[environment_zone_id]} saved successfully. The dashboard and AI analyst now use these values.",
                    )
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
    with environment_upload_tab:
        _render_file_upload("environment", dataset, key_prefix="environment-inline", return_page="Environmental data")

elif active_page == "Supply data":
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
        submitted = st.form_submit_button("Save supply data", type="primary", width="stretch")
        if submitted:
            try:
                update_supply(supply_clinic_id, stock, weekly_use)
                _set_flash(
                    "Supply data",
                    f"Supply data for {clinic_names[supply_clinic_id]} saved successfully. The dashboard and AI analyst now use these values.",
                )
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

elif active_page == "AI analyst":
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
