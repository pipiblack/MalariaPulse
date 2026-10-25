"""MalariaPulse Streamlit operations console."""

from __future__ import annotations

import json
import hmac
from datetime import datetime
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from malariapulse.ai import AIAnalystError, create_ai_review, get_ai_status, get_setting
from malariapulse.auth import (
    REMEMBER_LIFETIME_SECONDS,
    create_remember_token,
    validate_remember_token,
)
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
    update_interventions,
    update_supply,
)
from malariapulse.report import ai_report_filename, build_ai_report_pdf, report_jurisdiction

st.set_page_config(
    page_title="MalariaPulse",
    page_icon="🟢",
    layout="wide",
    initial_sidebar_state="expanded",
)

REMEMBER_COOKIE_NAME = "malariapulse_remember"
REMEMBER_QUERY_PARAM = "_mp_remember"
FORGET_QUERY_PARAM = "_mp_forget"
LOGOUT_QUERY_PARAM = "_mp_logout"

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
    .mp-side-label { color: #9fb0c8; font-size: .67rem; font-weight: 800; text-transform: uppercase; letter-spacing: .11em; margin: 1.25rem 0 .5rem; }
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
    [data-testid="stSidebar"] .st-key-logout { margin: .55rem 0 .2rem; }
    [data-testid="stSidebar"] .st-key-logout button {
      min-height: 2.7rem;
      background: var(--mp-red) !important;
      border: 1px solid #ff8b86 !important;
      border-radius: 10px !important;
      box-shadow: 0 8px 20px rgba(230,83,76,.24);
    }
    [data-testid="stSidebar"] .st-key-logout button:hover {
      background: #c83f39 !important;
      border-color: #ffaaa6 !important;
      transform: translateY(-1px);
    }
    [data-testid="stSidebar"] .st-key-logout button:focus-visible {
      outline: 3px solid rgba(255,255,255,.82) !important;
      outline-offset: 2px;
    }
    [data-testid="stSidebar"] .st-key-logout button p {
      color: #fff !important;
      font-weight: 800 !important;
    }
    [data-testid="stExpander"] summary [data-testid="stIconMaterial"] {
      display: none !important;
    }
    [data-testid="stExpander"] details > summary {
      position: relative;
      padding-left: 2rem;
    }
    [data-testid="stExpander"] details > summary::before {
      content: "›";
      position: absolute;
      left: .72rem;
      top: 50%;
      color: var(--mp-muted);
      font-family: Arial, sans-serif;
      font-size: 1.35rem;
      font-weight: 700;
      line-height: 1;
      transform: translateY(-50%);
      transition: transform .16s ease;
    }
    [data-testid="stExpander"] details[open] > summary::before {
      transform: translateY(-50%) rotate(90deg);
    }
    [data-testid="stExpander"] summary p {
      line-height: 1.35;
      overflow-wrap: anywhere;
    }
    [data-testid="stDataFrame"] { overflow: hidden; }
    [data-testid="stDataFrame"] * { text-rendering: optimizeLegibility; }
    .mp-login-options { margin-top: -.25rem; }
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


def _query_param(name: str) -> str | None:
    value = st.query_params.get(name)
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value) if value else None


def _remember_secret(configured_password: str) -> str:
    return _secret("REMEMBER_ME_SECRET") or get_setting("REMEMBER_ME_SECRET") or f"malariapulse-demo:{configured_password}"


def _clear_auth_query_params() -> None:
    """Remove transient login tokens through Streamlit's top-level URL state."""
    for name in (REMEMBER_QUERY_PARAM, FORGET_QUERY_PARAM, LOGOUT_QUERY_PARAM):
        if name in st.query_params:
            del st.query_params[name]


def _render_remember_cookie_bridge(*, token: str | None = None, clear: bool = False, reload_after: bool = False) -> None:
    """Set or clear the signed browser token without storing the password."""
    cookie_name = json.dumps(REMEMBER_COOKIE_NAME)
    token_value = json.dumps(token or "")
    max_age = REMEMBER_LIFETIME_SECONDS
    st.html(
        f"""
        <script>
        (() => {{
          const cookieName = {cookie_name};
          const token = {token_value};
          const secure = window.location.protocol === "https:" ? "; Secure" : "";
          if ({str(clear).lower()}) {{
            window.document.cookie = `${{cookieName}}=; Max-Age=0; Path=/; SameSite=Lax${{secure}}`;
          }} else if (token) {{
            window.document.cookie = `${{cookieName}}=${{encodeURIComponent(token)}}; Max-Age={max_age}; Path=/; SameSite=Lax${{secure}}`;
          }}
          if ({str(reload_after).lower()}) {{
            window.location.replace(window.location.pathname);
          }}
        }})();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def _render_login(
    configured_username: str,
    configured_password: str,
    credentials_overridden: bool,
    remember_secret: str,
) -> None:
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
            show_password = bool(st.session_state.get("login-show-password", False))
            username = st.text_input(
                "Email or username",
                placeholder="name@county-health.example",
                key="login-username",
            )
            password = st.text_input(
                "Password",
                type="default" if show_password else "password",
                placeholder="Enter your password",
                key="login-password",
            )
            remember_login = st.checkbox(
                "Remember me for 14 days",
                key="login-remember",
            )
            st.checkbox("Show password", key="login-show-password")
            st.caption("Leave Remember me unchecked on a shared device.")
            submitted = st.button("Sign in", type="primary", width="stretch", key="login-submit")
            if submitted:
                username_matches = hmac.compare_digest(username.strip(), configured_username)
                password_matches = hmac.compare_digest(password, configured_password)
                if username_matches and password_matches:
                    st.session_state["authenticated"] = True
                    st.session_state["authenticated_user"] = configured_username
                    if remember_login:
                        st.query_params[REMEMBER_QUERY_PARAM] = create_remember_token(
                            configured_username,
                            remember_secret,
                        )
                    else:
                        st.query_params[FORGET_QUERY_PARAM] = "1"
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


def _horizontal_bar_chart(
    frame: pd.DataFrame,
    *,
    category: str,
    value: str,
    color: str,
    value_title: str,
    height_per_row: int = 34,
    label_limit: int = 260,
) -> alt.Chart:
    return (
        alt.Chart(frame)
        .mark_bar(color=color, cornerRadiusEnd=4)
        .encode(
            x=alt.X(
                f"{value}:Q",
                title=value_title,
                scale=alt.Scale(zero=True),
                axis=alt.Axis(labelColor="#526179", titleColor="#526179", labelFontSize=12, titleFontSize=12),
            ),
            y=alt.Y(
                f"{category}:N",
                title=None,
                sort=alt.SortField(field=value, order="ascending"),
                axis=alt.Axis(labelColor="#526179", labelFontSize=12, labelLimit=label_limit),
            ),
            tooltip=[
                alt.Tooltip(f"{category}:N", title=category),
                alt.Tooltip(f"{value}:Q", title=value_title, format=".1f"),
            ],
        )
        .properties(height=max(220, len(frame) * height_per_row))
        .configure_axis(gridColor="#e5e9ef", domainColor="#cbd3df", tickColor="#cbd3df")
        .configure_view(strokeWidth=0)
    )


def _case_trend_chart(frame: pd.DataFrame, *, series_names: list[str], height: int = 310) -> alt.Chart:
    week_order = ["W-5", "W-4", "W-3", "W-2", "W-1", "Current"]
    long_frame = frame.reset_index(names="Week").melt(
        id_vars="Week",
        value_vars=series_names,
        var_name="Micro-zone",
        value_name="Case count",
    )
    palette = ["#246bfd", "#62b5ff", "#e6534c", "#ff9f9a", "#18a58a", "#76d99a"]
    return (
        alt.Chart(long_frame)
        .mark_line(point=alt.OverlayMarkDef(size=42, filled=True), strokeWidth=2.2)
        .encode(
            x=alt.X(
                "Week:N",
                sort=week_order,
                title=None,
                axis=alt.Axis(labelAngle=0, labelColor="#526179", labelFontSize=12),
            ),
            y=alt.Y(
                "Case count:Q",
                title="Reported cases",
                scale=alt.Scale(zero=True),
                axis=alt.Axis(labelColor="#526179", titleColor="#526179", labelFontSize=12, titleFontSize=12),
            ),
            color=alt.Color(
                "Micro-zone:N",
                scale=alt.Scale(domain=series_names, range=palette[: len(series_names)]),
                legend=alt.Legend(
                    title=None,
                    orient="bottom",
                    columns=3,
                    labelColor="#526179",
                    labelFontSize=11,
                    labelLimit=180,
                ) if len(series_names) > 1 else None,
            ),
            tooltip=[
                alt.Tooltip("Week:N"),
                alt.Tooltip("Micro-zone:N"),
                alt.Tooltip("Case count:Q", format=".0f", title="Reported cases"),
            ],
        )
        .properties(height=height)
        .configure_axis(gridColor="#e5e9ef", domainColor="#cbd3df", tickColor="#cbd3df")
        .configure_view(strokeWidth=0)
    )


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
        "intervention": "Intervention coverage",
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
            "no row-count limit · maximum 15 MB · invalid files are never partially applied"
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
    preview_row_limit = 200
    table_rows = [
        {
            "Row": row["rowNumber"],
            "ID": row["identifier"],
            "Status": "Valid" if row["valid"] else "Invalid",
            "Preview": row["preview"],
            "Errors": " ".join(row["errors"]),
        }
        for row in preview["rows"][:preview_row_limit]
    ]
    st.dataframe(pd.DataFrame(table_rows), hide_index=True, width="stretch")
    if preview["rowCount"] > preview_row_limit:
        st.caption(
            f"Showing the first {preview_row_limit:,} rows. All {preview['rowCount']:,} rows were validated."
        )
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
                st.markdown("**1. Why this draft was generated**")
                st.write(
                    f"The surveillance agent detected a {assessment['riskLevel']} operational signal: "
                    f"cases changed by {assessment['growthPct']}%, test positivity is {assessment['positivityPct']}%, "
                    f"and the model projects {assessment['expectedCasesNextWeek']} cases next week. "
                    "These values require verification; they do not by themselves confirm an outbreak."
                )
                if assessment.get("priorityFlags"):
                    for flag in assessment["priorityFlags"]:
                        st.warning(flag, icon="⚠️")

                supply_plan = intervention["supplyPlan"]
                st.markdown("**2. Supply and redistribution draft**")
                readiness_col, movement_col, request_col = st.columns(3)
                readiness_col.metric("Projected readiness", f"{supply_plan['readinessPct']}%")
                movement_col.metric("Proposed movements", len(supply_plan["recommendations"]))
                request_col.metric("Unresolved restocks", len(supply_plan["restockRequests"]))
                st.write(supply_plan.get("method", "The plan estimates a three-week safety-stock requirement."))
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
                                "Receiver before": move.get("receiverWeeksBefore"),
                                "Receiver after": move.get("receiverWeeksAfter"),
                                "Donor after": move.get("donorWeeksAfter"),
                                "Reason": move.get("rationale", "Restore safety stock."),
                            }
                            for move in supply_plan["recommendations"]
                        ]
                    )
                    st.dataframe(
                        moves,
                        hide_index=True,
                        width="stretch",
                        column_config={
                            "Receiver before": st.column_config.NumberColumn(format="%.1f weeks"),
                            "Receiver after": st.column_config.NumberColumn(format="%.1f weeks"),
                            "Donor after": st.column_config.NumberColumn(format="%.1f weeks"),
                        },
                    )
                if supply_plan["restockRequests"]:
                    st.warning(f"{len(supply_plan['restockRequests'])} unresolved county restock request(s) require review.")
                    restocks = pd.DataFrame(
                        [
                            {
                                "Facility": request["clinic"],
                                "Resource": request["resourceLabel"],
                                "Quantity still needed": request["quantity"],
                                "Stock on hand": request.get("stockOnHand"),
                                "Weekly use": request.get("weeklyUse"),
                                "Coverage": request.get("coverageWeeks"),
                                "Priority": request["priority"].title(),
                            }
                            for request in supply_plan["restockRequests"]
                        ]
                    )
                    st.dataframe(
                        restocks,
                        hide_index=True,
                        width="stretch",
                        column_config={"Coverage": st.column_config.NumberColumn(format="%.1f weeks")},
                    )

                advisories = intervention["advisories"]
                st.markdown("**3. Community communication drafts**")
                st.write(advisories.get("summary", "Draft messages are prepared for local review."))
                st.caption(advisories["clinicalSafety"])
                message_tabs = st.tabs(
                    [f"{message['audience'].title()} · {message['language']}" for message in advisories["messages"]]
                )
                for message_tab, message in zip(message_tabs, advisories["messages"]):
                    with message_tab:
                        st.write(f"**Purpose:** {message.get('purpose', 'Provide approved prevention and referral guidance.')}" )
                        st.write(f"**Why this audience:** {message.get('reason', advisories.get('summary', 'Targeted operational alert.'))}")
                        st.info(message["text"])
                        st.write(f"**Delivery note:** {message.get('deliveryNotes', 'Release only after county approval.')}" )
                        with st.expander("Reviewer checklist"):
                            for check in message.get("reviewChecklist", ["Confirm wording, audience, timing, and approver."]):
                                st.write(f"• {check}")
                        st.caption(
                            f"{message['channel']} · {message['characters']} characters · "
                            f"{message['segments']} SMS segment(s) · draft only"
                        )
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


def _render_ai_review(result: dict[str, Any], dataset: dict[str, Any]) -> None:
    review = result["review"]
    jurisdiction = report_jurisdiction(result, dataset)
    report_pdf = build_ai_report_pdf(result, dataset)
    with st.container(border=True):
        summary_col, download_col = st.columns([3.2, 1.15], vertical_alignment="center")
        with summary_col:
            st.caption("AI OPERATIONS REVIEW")
            st.subheader(review["headline"])
            st.markdown(_risk_chip(review["overallRisk"]), unsafe_allow_html=True)
        with download_col:
            st.download_button(
                "Download AI report",
                data=report_pdf,
                file_name=ai_report_filename(result, dataset),
                mime="application/pdf",
                type="primary",
                width="stretch",
                key="download-ai-report",
            )
            st.caption(f"PDF · {jurisdiction} letterhead")
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
        f"source updated {_format_time(result.get('sourceUpdatedAt'))} · Gemini response {result.get('responseId') or 'not supplied'}"
    )


configured_username, configured_password, credentials_overridden = _authentication_config()
remember_secret = _remember_secret(configured_password)
logout_requested = _query_param(LOGOUT_QUERY_PARAM) == "1"
remember_query_token = _query_param(REMEMBER_QUERY_PARAM)
forget_requested = _query_param(FORGET_QUERY_PARAM) == "1"

if logout_requested:
    st.session_state.clear()
    _clear_auth_query_params()
    _render_remember_cookie_bridge(clear=True, reload_after=True)
elif forget_requested:
    _clear_auth_query_params()
    _render_remember_cookie_bridge(clear=True)
elif remember_query_token:
    _clear_auth_query_params()
    if validate_remember_token(remember_query_token, configured_username, remember_secret):
        st.session_state["authenticated"] = True
        st.session_state["authenticated_user"] = configured_username
        _render_remember_cookie_bridge(token=remember_query_token)
elif not st.session_state.get("authenticated", False):
    remembered_token = st.context.cookies.get(REMEMBER_COOKIE_NAME)
    if validate_remember_token(remembered_token, configured_username, remember_secret):
        st.session_state["authenticated"] = True
        st.session_state["authenticated_user"] = configured_username

if not st.session_state.get("authenticated", False):
    _render_login(configured_username, configured_password, credentials_overridden, remember_secret)
    st.stop()


dataset = load_dataset()
snapshot = build_network_snapshot(dataset)
zone_names = _zone_names(dataset)
clinic_names = _clinic_names(dataset)
api_key = _secret("GOOGLE_API_KEY") or _secret("GEMINI_API_KEY")
api_model = _secret("GEMINI_MODEL")
ai_status = get_ai_status(api_key=api_key, model=api_model)

page_copy = {
    "Overview": ("Malaria operations command view", "Surveillance signals, county priorities, and multi-agent response drafts."),
    "Bulk data upload": ("Bulk data upload", "Validate and apply aggregate clinical, environmental, intervention, or supply files."),
    "Clinical data": ("Clinical surveillance entry", "Correct one micro-zone or use bulk upload for routine reporting."),
    "Environmental data": ("Environmental observation entry", "Update rainfall, temperature, flooding, and standing-water signals by micro-zone."),
    "Intervention data": ("Intervention coverage entry", "Track the latest prevention coverage context by micro-zone."),
    "Supply data": ("Facility supply entry", "Review and update facility stock and average weekly use."),
    "AI analyst": ("AI operations analyst", "Generate an evidence-grounded review from the latest saved data."),
}

with st.sidebar:
    st.markdown('<div class="mp-brand">Malaria<span>Pulse</span></div>', unsafe_allow_html=True)
    st.caption("County early warning & response")
    st.markdown('<div class="mp-side-label">Signed in</div>', unsafe_allow_html=True)
    st.caption(st.session_state.get("authenticated_user", "Demo operator"))
    if st.button("Log out", key="logout", type="primary", width="stretch"):
        st.session_state.clear()
        st.query_params[LOGOUT_QUERY_PARAM] = "1"
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
        st.success(f"Configured · {ai_status['model']}")
        st.caption("The key is verified only when a live review succeeds.")
    else:
        st.warning("Gemini key not configured")
        st.caption("Cloud: Manage app → Settings → Secrets. Local: add the key to .env.local.")
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
    first.metric(
        "Latest reported cases",
        summary["currentCases"],
        f"{summary['caseChangePct']}% vs previous week",
        delta_color="inverse",
        help="Sum of the latest weekly aggregate case count across monitored micro-zones.",
    )
    second.metric(
        "Network test positivity",
        f"{summary['positivityPct']}%",
        f"{summary['positiveTests']} of {summary['tests']} tests",
        delta_color="off",
        help="Confirmed positive tests divided by all malaria tests in the current reporting period.",
    )
    third.metric("High / critical zones", summary["highRiskZones"], help="Zones with an operational score of 60 or higher.")
    fourth.metric(
        "Facilities below 3 weeks",
        summary["facilitiesBelowThreeWeeks"],
        help="Facilities where at least one tracked malaria commodity has less than three weeks of coverage.",
    )
    if dataset["metadata"].get("mode") == "demonstration":
        st.caption("Demonstration data are shown. Replace them through the sidebar entry pages or validated file uploads before operational use.")

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

    st.subheader("County transmission pattern")
    county_trend = pd.DataFrame(
        {
            zone["name"]: zone["weeklyCases"]
            for zone in dataset["zones"]
        },
        index=["W-5", "W-4", "W-3", "W-2", "W-1", "Current"],
    )
    trend_col, rank_col = st.columns([3, 2])
    with trend_col:
        st.altair_chart(
            _case_trend_chart(county_trend, series_names=list(county_trend.columns), height=310),
            width="stretch",
        )
        st.caption("Six-week reported case trajectories. Compare direction and persistence, not only the latest total.")
    with rank_col:
        risk_rank = pd.DataFrame(
            {
                "Micro-zone": [item["zoneName"] for item in snapshot["assessments"]],
                "Risk score": [item["score"] for item in snapshot["assessments"]],
            }
        )
        st.altair_chart(
            _horizontal_bar_chart(
                risk_rank,
                category="Micro-zone",
                value="Risk score",
                color="#246bfd",
                value_title="Risk score (0–100)",
                height_per_row=42,
                label_limit=190,
            ),
            width="stretch",
        )
        st.caption("Operational score from 0–100. Scores at or above 60 enter the high/critical response queue.")

    selected_zone = next(zone for zone in dataset["zones"] if zone["id"] == selected_zone_id)
    assessment = assess_zone(selected_zone, dataset["metadata"])
    st.subheader(f"Micro-zone detail · {selected_zone['name']}")
    chart_col, signal_col = st.columns([3, 2])
    with chart_col:
        trend = pd.DataFrame(
            {
                "Week": ["W-5", "W-4", "W-3", "W-2", "W-1", "Current"],
                "Reported cases": selected_zone["weeklyCases"],
            }
        ).set_index("Week")
        st.altair_chart(
            _case_trend_chart(trend, series_names=["Reported cases"], height=300),
            width="stretch",
        )
        st.caption(
            f"{selected_zone['tests']} tests · {selected_zone['positiveTests']} positive · "
            f"{assessment['positivityPct']}% positivity · {assessment['testingCoveragePct']}% of suspected cases tested · "
            f"{assessment['incidencePerThousand']} cases per 1,000"
        )
    with signal_col:
        st.markdown(f"{_risk_chip(assessment['riskLevel'])}", unsafe_allow_html=True)
        st.metric("Risk score", f"{assessment['score']} / 100", f"{assessment['growthPct']}% case acceleration")
        st.write(assessment["recommendation"])
        st.caption(f"Expected next week: {assessment['expectedCasesNextWeek']} cases · confidence {assessment['confidence']:.0%}")
        for driver in assessment["drivers"]:
            st.progress(min(driver["contribution"] / 40, 1.0), text=f"{driver['label']} · {driver['contribution']} points")

    clinical = assessment["clinicalContext"]
    environment = assessment["environmentContext"]
    context_first, context_second, context_third, context_fourth = st.columns(4)
    context_first.metric("Severe cases", clinical["severeCases"], f"{clinical['admissions']} admitted", delta_color="off")
    context_second.metric("Priority-group cases", clinical["under5ConfirmedCases"] + clinical["pregnancyConfirmedCases"], f"{clinical['under5ConfirmedCases']} under 5 · {clinical['pregnancyConfirmedCases']} pregnancy", delta_color="off")
    context_third.metric("Reporting completeness", f"{clinical['reportingCompletenessPct']}%", help="Facilities expected to report versus reports received for this zone.")
    context_fourth.metric("30-day rainfall", f"{environment['rainfall30dMm']} mm", f"Standing water {environment['standingWaterIndex']}/100", delta_color="off")
    if assessment["priorityFlags"]:
        st.write("**Attention flags**")
        st.write(" · ".join(assessment["priorityFlags"]))

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
                "Growth (%)": item["growthPct"],
                "Positivity (%)": item["positivityPct"],
                "Testing (%)": item["testingCoveragePct"],
                "Reporting (%)": item["clinicalContext"]["reportingCompletenessPct"],
                "Attention flags": "; ".join(item["priorityFlags"]) or "Routine monitoring",
            }
            for item in snapshot["assessments"]
        ]
    )
    st.dataframe(
        risk_rows,
        hide_index=True,
        width="stretch",
        column_config={
            "Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
            "Growth (%)": st.column_config.NumberColumn(format="%.1f%%"),
            "Positivity (%)": st.column_config.NumberColumn(format="%.1f%%"),
            "Testing (%)": st.column_config.NumberColumn(format="%.1f%%"),
            "Reporting (%)": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%"),
        },
    )

    st.subheader("Clinical severity and priority groups")
    clinical_rows = pd.DataFrame(
        [
            {
                "Micro-zone": item["zoneName"],
                "Suspected": item["clinicalContext"]["suspectedCases"],
                "Tested": next(zone["tests"] for zone in dataset["zones"] if zone["id"] == item["zoneId"]),
                "Latest cases": item["currentCases"],
                "Severe": item["clinicalContext"]["severeCases"],
                "Admissions": item["clinicalContext"]["admissions"],
                "Deaths": item["clinicalContext"]["deaths"],
                "Under 5": item["clinicalContext"]["under5ConfirmedCases"],
                "Pregnancy": item["clinicalContext"]["pregnancyConfirmedCases"],
                "CHW referrals": item["clinicalContext"]["chwFeverReferrals"],
            }
            for item in snapshot["assessments"]
        ]
    )
    st.dataframe(clinical_rows, hide_index=True, width="stretch")
    st.caption("Aggregate counts only. Severe cases, admissions, deaths, and priority-group cases support response planning but are not currently included in the risk score.")

    st.subheader("Climate and prevention context")
    climate_col, prevention_col = st.columns(2)
    with climate_col:
        climate_chart = pd.DataFrame(
            {
                "Micro-zone": [zone["name"] for zone in dataset["zones"]],
                "30-day rainfall (mm)": [zone["environment"]["rainfall30dMm"] for zone in dataset["zones"]],
            }
        )
        st.altair_chart(
            _horizontal_bar_chart(
                climate_chart,
                category="Micro-zone",
                value="30-day rainfall (mm)",
                color="#246bfd",
                value_title="Rainfall (mm)",
                height_per_row=42,
                label_limit=190,
            ),
            width="stretch",
        )
        climate_rows = pd.DataFrame(
            [
                {
                    "Micro-zone": zone["name"],
                    "Rainfall 7d (mm)": zone["environment"]["rainfall7dMm"],
                    "Rainfall 30d (mm)": zone["environment"]["rainfall30dMm"],
                    "Humidity (%)": zone["environment"]["humidityPct"],
                    "Standing water": zone["environment"]["standingWaterIndex"],
                    "Flooded sites": zone["environment"]["floodedSites"],
                }
                for zone in dataset["zones"]
            ]
        )
        st.dataframe(climate_rows, hide_index=True, width="stretch")
    with prevention_col:
        prevention_chart = pd.DataFrame(
            {
                "Micro-zone": [zone["name"] for zone in dataset["zones"]],
                "LLIN use": [zone["interventions"]["llinUsePct"] for zone in dataset["zones"]],
                "IPTp3": [zone["interventions"]["iptp3CoveragePct"] for zone in dataset["zones"]],
                "Vaccine dose 4": [zone["interventions"]["vaccineDose4CoveragePct"] for zone in dataset["zones"]],
                "Larval sites managed": [zone["interventions"]["larvalSitesManagedPct"] for zone in dataset["zones"]],
            }
        ).set_index("Micro-zone")
        prevention_long = prevention_chart.reset_index().melt(
            id_vars="Micro-zone",
            var_name="Indicator",
            value_name="Coverage",
        )
        prevention_plot = (
            alt.Chart(prevention_long)
            .mark_bar(cornerRadiusEnd=3)
            .encode(
                x=alt.X(
                    "Coverage:Q",
                    title="Coverage (%)",
                    scale=alt.Scale(domain=[0, 100]),
                    axis=alt.Axis(labelColor="#526179", titleColor="#526179", labelFontSize=12, titleFontSize=12),
                ),
                y=alt.Y(
                    "Micro-zone:N",
                    title=None,
                    sort=alt.EncodingSortField(field="Coverage", op="mean", order="descending"),
                    axis=alt.Axis(labelColor="#526179", labelFontSize=12, labelLimit=190),
                ),
                yOffset="Indicator:N",
                color=alt.Color(
                    "Indicator:N",
                    scale=alt.Scale(
                        domain=["LLIN use", "IPTp3", "Vaccine dose 4", "Larval sites managed"],
                        range=["#246bfd", "#14865f", "#e49b24", "#647188"],
                    ),
                    legend=alt.Legend(
                        title=None,
                        orient="bottom",
                        columns=2,
                        labelColor="#526179",
                        labelFontSize=11,
                        labelLimit=180,
                    ),
                ),
                tooltip=[
                    alt.Tooltip("Micro-zone:N"),
                    alt.Tooltip("Indicator:N"),
                    alt.Tooltip("Coverage:Q", format=".1f", title="Coverage (%)"),
                ],
            )
            .properties(height=300)
            .configure_axis(gridColor="#e5e9ef", domainColor="#cbd3df", tickColor="#cbd3df")
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(prevention_plot, width="stretch")
        st.dataframe(
            prevention_chart.reset_index(),
            hide_index=True,
            width="stretch",
            column_config={
                column: st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%")
                for column in prevention_chart.columns
            },
        )
    st.caption("Coverage indicators have different eligible denominators and update cycles. Compare each indicator across zones; do not add or average them together.")

    st.subheader("Commodity readiness")
    supply_rows = []
    for clinic in dataset["clinics"]:
        coverage = {
            resource: round(clinic["stock"][resource] / clinic["weeklyUse"][resource], 1)
            if clinic["weeklyUse"][resource] > 0
            else None
            for resource in ("rdt", "act", "nets")
        }
        supply_rows.append(
            {
                "Facility": clinic["name"],
                "Micro-zone": zone_names[clinic["zoneId"]],
                "RDT weeks": coverage["rdt"],
                "ACT weeks": coverage["act"],
                "Net weeks": coverage["nets"],
                "Lowest coverage": min(value for value in coverage.values() if value is not None),
            }
        )
    supply_frame = pd.DataFrame(supply_rows).sort_values("Lowest coverage")
    supply_chart = supply_frame[["Facility", "Lowest coverage"]]
    st.altair_chart(
        _horizontal_bar_chart(
            supply_chart,
            category="Facility",
            value="Lowest coverage",
            color="#e6534c",
            value_title="Lowest commodity coverage (weeks)",
            height_per_row=36,
            label_limit=420,
        ),
        width="stretch",
    )
    st.dataframe(
        supply_frame,
        hide_index=True,
        width="stretch",
        column_config={
            "RDT weeks": st.column_config.NumberColumn(format="%.1f weeks"),
            "ACT weeks": st.column_config.NumberColumn(format="%.1f weeks"),
            "Net weeks": st.column_config.NumberColumn(format="%.1f weeks"),
            "Lowest coverage": st.column_config.NumberColumn(format="%.1f weeks"),
        },
    )

    with st.expander("Latest multi-agent response cycle", expanded=latest_cycle() is not None):
        _render_cycle(latest_cycle())

    with st.expander("Indicator definitions, sources, and scoring notes"):
        st.write(
            "The displayed risk score is a deterministic operational signal combining six-week case acceleration (40%), "
            "test positivity (23%), 7-day rainfall (16%), humidity (11%), and temperature suitability (10%)."
        )
        st.write(
            "Additional Western Kenya decision context now includes severe cases, admissions, malaria deaths, cases in children under 5 and pregnancy, "
            "CHW fever referrals, reporting completeness, 30-day rainfall, standing-water observations, flooded sites, LLIN use, IPTp3 coverage, "
            "malaria vaccine dose 4 coverage, and larval-site management. These contextual fields are displayed separately and are not scored until calibrated."
        )
        st.write(
            "Recommended future feeds, when governed sources become available: vector density and species, human biting rate, insecticide susceptibility/resistance, "
            "IRS coverage in targeted areas, diagnostic quality assurance, facility reporting timeliness, population movement, and geospatial land-cover or water-body indicators."
        )
        st.write(
            f"Source mode: **{dataset['metadata'].get('mode', 'unknown')}** · reporting week: "
            f"**{dataset['metadata']['reportingWeek']}** · stated completeness: "
            f"**{dataset['metadata'].get('dataCompleteness', 0):.0%}**."
        )
        st.warning("This is an uncalibrated MVP signal, not a confirmed outbreak, diagnostic system, or autonomous dispatch decision.")
        st.markdown(
            "Sources: [Kenya Malaria Strategy 2023–2027](https://extranet.who.int/cpcd/sites/default/files/public_file_repository/KEN_Kenya_National-Malaria-Strategy_2023-2027.pdf) · "
            "[WHO malaria surveillance indicators](https://www.who.int/publications/m/item/core-indicators-for-malaria-surveillance-monitoring-and-evaluation) · "
            "[Kenya DHS 2022](https://www.knbs.or.ke/reports/kdhs-2022/) · "
            "[WHO Kenya malaria profile 2025](https://cdn.who.int/media/docs/default-source/malaria/country-profiles/2025/malaria-2025-ken.pdf)"
        )

elif active_page == "Bulk data upload":
    kind_labels = {
        "clinical": "Clinical surveillance",
        "environment": "Environmental observations",
        "intervention": "Intervention coverage",
        "supply": "Facility supply telemetry",
    }
    upload_kind = st.selectbox("Data type", list(kind_labels), format_func=kind_labels.get, key="upload-kind")
    _render_file_upload(upload_kind, dataset, key_prefix=f"bulk-{upload_kind}", return_page="Bulk data upload")

elif active_page == "Clinical data":
    clinical_manual_tab, clinical_upload_tab = st.tabs(["Manual entry", "File upload"])
    with clinical_manual_tab:
        st.caption("Use this form for a single-zone correction.")
        clinical_zone_id = st.selectbox("Micro-zone", list(zone_names), format_func=zone_names.get, key="clinical-zone")
        clinical_zone = next(zone for zone in dataset["zones"] if zone["id"] == clinical_zone_id)
        clinical_context = clinical_zone["clinical"]
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
            st.markdown("**Severity, priority groups, and surveillance performance**")
            severity_columns = st.columns(4)
            suspected_cases = severity_columns[0].number_input(
                "Suspected malaria cases",
                min_value=0,
                value=int(clinical_context["suspectedCases"]),
                step=1,
                help="Fever or suspected-malaria presentations used as the testing-coverage denominator.",
            )
            severe_cases = severity_columns[1].number_input(
                "Severe cases", min_value=0, value=int(clinical_context["severeCases"]), step=1
            )
            admissions = severity_columns[2].number_input(
                "Malaria admissions", min_value=0, value=int(clinical_context["admissions"]), step=1
            )
            deaths = severity_columns[3].number_input(
                "Malaria deaths", min_value=0, value=int(clinical_context["deaths"]), step=1
            )
            priority_columns = st.columns(4)
            under5_cases = priority_columns[0].number_input(
                "Confirmed cases, under 5",
                min_value=0,
                value=int(clinical_context["under5ConfirmedCases"]),
                step=1,
            )
            pregnancy_cases = priority_columns[1].number_input(
                "Confirmed cases, pregnancy",
                min_value=0,
                value=int(clinical_context["pregnancyConfirmedCases"]),
                step=1,
            )
            chw_referrals = priority_columns[2].number_input(
                "CHW fever referrals",
                min_value=0,
                value=int(clinical_context["chwFeverReferrals"]),
                step=1,
            )
            reporting_completeness = priority_columns[3].number_input(
                "Reporting completeness (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(clinical_context["reportingCompletenessPct"]),
                step=1.0,
            )
            submitted = st.form_submit_button("Save clinical data", type="primary", width="stretch")
            if submitted:
                try:
                    update_clinical(
                        clinical_zone_id,
                        weekly_cases,
                        tests,
                        positive_tests,
                        reporting_week,
                        {
                            "suspectedCases": suspected_cases,
                            "severeCases": severe_cases,
                            "admissions": admissions,
                            "deaths": deaths,
                            "under5ConfirmedCases": under5_cases,
                            "pregnancyConfirmedCases": pregnancy_cases,
                            "chwFeverReferrals": chw_referrals,
                            "reportingCompletenessPct": reporting_completeness,
                        },
                    )
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
            exposure_columns = st.columns(3)
            rainfall_30d = exposure_columns[0].number_input(
                "Rainfall, last 30 days (mm)",
                min_value=0.0,
                max_value=4000.0,
                value=float(environment["rainfall30dMm"]),
                step=1.0,
                help="A longer rainfall window provides context for lagged mosquito breeding and transmission conditions.",
            )
            standing_water = exposure_columns[1].number_input(
                "Standing-water index (0–100)",
                min_value=0.0,
                max_value=100.0,
                value=float(environment["standingWaterIndex"]),
                step=1.0,
                help="Locally defined observation index; document and use the same field method across zones.",
            )
            flooded_sites = exposure_columns[2].number_input(
                "Flooded or waterlogged sites",
                min_value=0,
                value=int(environment["floodedSites"]),
                step=1,
            )
            submitted = st.form_submit_button("Save environmental data", type="primary", width="stretch")
            if submitted:
                try:
                    update_environment(
                        environment_zone_id,
                        rainfall,
                        temperature,
                        humidity,
                        rainfall_30d,
                        standing_water,
                        flooded_sites,
                    )
                    _set_flash(
                        "Environmental data",
                        f"Environmental data for {zone_names[environment_zone_id]} saved successfully. The dashboard and AI analyst now use these values.",
                    )
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
    with environment_upload_tab:
        _render_file_upload("environment", dataset, key_prefix="environment-inline", return_page="Environmental data")

elif active_page == "Intervention data":
    intervention_manual_tab, intervention_upload_tab = st.tabs(["Manual entry", "File upload"])
    with intervention_manual_tab:
        st.caption("Enter the latest available coverage estimates. These indicators may update monthly, quarterly, or annually rather than weekly.")
        intervention_zone_id = st.selectbox(
            "Micro-zone", list(zone_names), format_func=zone_names.get, key="intervention-zone"
        )
        intervention_zone = next(zone for zone in dataset["zones"] if zone["id"] == intervention_zone_id)
        intervention = intervention_zone["interventions"]
        with st.form(f"intervention-form-{intervention_zone_id}"):
            coverage_date = st.text_input(
                "Coverage reference date", value=intervention["coverageDate"], help="Format: YYYY-MM-DD"
            )
            coverage_columns = st.columns(4)
            llin_use = coverage_columns[0].number_input(
                "LLIN use (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(intervention["llinUsePct"]),
                step=1.0,
                help="Population in the malaria-risk area who slept under a long-lasting insecticidal net.",
            )
            iptp3_coverage = coverage_columns[1].number_input(
                "IPTp3 coverage (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(intervention["iptp3CoveragePct"]),
                step=1.0,
                help="Eligible pregnant women receiving at least three doses of intermittent preventive treatment.",
            )
            vaccine_dose4 = coverage_columns[2].number_input(
                "Malaria vaccine dose 4 (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(intervention["vaccineDose4CoveragePct"]),
                step=1.0,
                help="Age-eligible children receiving the fourth malaria-vaccine dose.",
            )
            larval_sites_managed = coverage_columns[3].number_input(
                "Larval sites managed (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(intervention["larvalSitesManagedPct"]),
                step=1.0,
                help="Locally identified, eligible larval sites covered by the approved management programme.",
            )
            submitted = st.form_submit_button("Save intervention data", type="primary", width="stretch")
            if submitted:
                try:
                    update_interventions(
                        intervention_zone_id,
                        coverage_date,
                        llin_use,
                        iptp3_coverage,
                        vaccine_dose4,
                        larval_sites_managed,
                    )
                    _set_flash(
                        "Intervention data",
                        f"Intervention data for {zone_names[intervention_zone_id]} saved successfully. The dashboard and AI analyst now use these values.",
                    )
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

        st.subheader("Current prevention coverage context")
        intervention_rows = pd.DataFrame(
            [
                {
                    "Micro-zone": zone["name"],
                    "Reference date": zone["interventions"]["coverageDate"],
                    "LLIN use (%)": zone["interventions"]["llinUsePct"],
                    "IPTp3 (%)": zone["interventions"]["iptp3CoveragePct"],
                    "Vaccine dose 4 (%)": zone["interventions"]["vaccineDose4CoveragePct"],
                    "Larval sites managed (%)": zone["interventions"]["larvalSitesManagedPct"],
                }
                for zone in dataset["zones"]
            ]
        )
        st.dataframe(
            intervention_rows,
            hide_index=True,
            width="stretch",
            column_config={
                column: st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%")
                for column in ("LLIN use (%)", "IPTp3 (%)", "Vaccine dose 4 (%)", "Larval sites managed (%)")
            },
        )
        st.info("These measures use different eligible denominators and reporting periods. Review each measure separately and retain its source date.")
    with intervention_upload_tab:
        _render_file_upload(
            "intervention", dataset, key_prefix="intervention-inline", return_page="Intervention data"
        )

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
        st.success(f"Google Gemini configured · {ai_status['model']} · key remains server-side")
    else:
        st.warning("The deployed analyst needs a Gemini key in Streamlit Community Cloud secrets.")
        st.info("Open Manage app → Settings → Secrets, paste the configuration below, save it, then reboot the app. For local use, put the same values in .env.local instead.")
        st.code('GEMINI_API_KEY = "your_new_key_here"\nGEMINI_MODEL = "gemini-3.8-flash"', language="toml")

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
        _render_ai_review(ai_result, dataset)
    else:
        st.info("No live review has been generated in this session.")
