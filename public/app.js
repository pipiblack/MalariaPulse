const state = { dashboard: null, dataset: null, aiStatus: null, selectedCycle: null };
const $ = (selector) => document.querySelector(selector);

const tones = { critical: "#ca3d3a", high: "#e9665d", watch: "#dc9b2f", low: "#3e9b75" };
const positions = {
  "seme-central": [22, 36],
  "kisumu-west": [39, 28],
  "kisumu-central": [51, 48],
  "kano-plains": [68, 42],
  "nyakach-north": [65, 74],
  "muhoroni-east": [84, 30]
};
const viewCopy = {
  overview: ["Operations overview", "Kisumu County · Public health intelligence"],
  clinical: ["Clinical data entry", "Surveillance inputs · Aggregated reporting"],
  environment: ["Environmental data entry", "Surveillance inputs · Transmission conditions"],
  supply: ["Supply telemetry", "Resource inputs · Facility stock"],
  ai: ["AI incident analyst", "Live intelligence · OpenAI Responses API"]
};

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#039;", '"': "&quot;" })[character]);
}

function riskStyle(level) {
  return `--tone:${tones[level] ?? tones.low}`;
}

function formatTime(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-KE", { hour: "2-digit", minute: "2-digit", day: "numeric", month: "short", timeZone: "Africa/Nairobi" }).format(new Date(value));
}

function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.add("show");
  setTimeout(() => element.classList.remove("show"), 2800);
}

async function api(path, options) {
  const response = await fetch(path, { headers: { "content-type": "application/json" }, ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

function renderMetrics(data) {
  $("#metric-zones").textContent = data.summary.zonesMonitored;
  $("#metric-risk").textContent = data.summary.highRiskZones;
  $("#metric-risk-copy").textContent = data.summary.highRiskZones ? "Action threshold crossed" : "No action threshold crossed";
  $("#metric-facilities").textContent = data.summary.facilitiesReporting;
  $("#metric-readiness").textContent = `${data.summary.supplyReadinessPct}%`;
  $("#last-sync").textContent = formatTime(data.metadata.updatedAt);
}

function renderMap(assessments) {
  const stage = $("#risk-map");
  const nodes = assessments.map((assessment) => {
    const [left, top] = positions[assessment.zoneId] ?? [50, 50];
    const size = 24 + assessment.score * 0.22;
    return `<button class="zone-node" data-zone="${escapeHtml(assessment.zoneId)}" style="left:${left}%;top:${top}%;--size:${size}px;${riskStyle(assessment.riskLevel)}" aria-label="${escapeHtml(assessment.zoneName)} risk score ${assessment.score}">
      <span class="zone-pulse">${assessment.score}</span><span class="zone-label">${escapeHtml(assessment.zoneName)}</span>
    </button>`;
  }).join("");
  stage.innerHTML = `<div class="map-water"></div><div class="map-road" style="left:28%;top:35%;width:58%;transform:rotate(7deg)"></div><div class="map-road" style="left:49%;top:49%;width:35%;transform:rotate(51deg)"></div>${nodes}`;
  stage.querySelectorAll(".zone-node").forEach((button) => button.addEventListener("click", () => openZone(button.dataset.zone)));
}

function renderAlerts(assessments) {
  const alerts = assessments.filter((item) => ["critical", "high"].includes(item.riskLevel));
  $("#alert-count").textContent = alerts.length;
  $("#alerts-list").innerHTML = alerts.length ? alerts.map((alert) => `<article class="alert-card" style="${riskStyle(alert.riskLevel)}">
    <span class="alert-bar"></span><div><div class="alert-top"><strong>${escapeHtml(alert.zoneName)}</strong><span class="alert-score">${escapeHtml(alert.riskLevel)} · ${alert.score}</span></div>
    <p>${escapeHtml(alert.recommendation)}</p><div class="alert-meta"><span>Cases ${alert.currentCases} → ${alert.expectedCasesNextWeek}</span><span>${alert.positivityPct}% positivity</span><span>${Math.round(alert.confidence * 100)}% confidence</span></div>
    <button class="text-button" data-zone="${escapeHtml(alert.zoneId)}">Review response →</button></div></article>`).join("") : `<p class="subtle">No zones have crossed the action threshold.</p>`;
  $("#alerts-list").querySelectorAll("button[data-zone]").forEach((button) => button.addEventListener("click", () => openZone(button.dataset.zone)));
}

function renderTable(assessments, query = "") {
  const filtered = assessments.filter((item) => `${item.zoneName} ${item.subcounty}`.toLowerCase().includes(query.toLowerCase()));
  $("#zone-table").innerHTML = filtered.map((item) => {
    const trendClass = item.growthPct > 8 ? "trend-up" : item.growthPct < -8 ? "trend-down" : "trend-flat";
    const trend = `${item.growthPct > 0 ? "+" : ""}${item.growthPct}%`;
    return `<tr><td class="zone-cell"><strong>${escapeHtml(item.zoneName)}</strong><span>${escapeHtml(item.subcounty)} sub-county</span></td>
      <td><span class="risk-badge" style="${riskStyle(item.riskLevel)}">${escapeHtml(item.riskLevel)}</span></td>
      <td><div class="score-meter" style="${riskStyle(item.riskLevel)}"><span>${item.score}</span><span class="score-track"><i style="--score:${item.score}%"></i></span></div></td>
      <td>${item.currentCases}</td><td class="${trendClass}">${trend}</td><td>${item.positivityPct}%</td><td>${Math.round(item.confidence * 100)}%</td>
      <td><button class="row-action" data-zone="${escapeHtml(item.zoneId)}" aria-label="Review ${escapeHtml(item.zoneName)}">›</button></td></tr>`;
  }).join("");
  $("#zone-table").querySelectorAll("button[data-zone]").forEach((button) => button.addEventListener("click", () => openZone(button.dataset.zone)));
}

function renderInventory(summary) {
  const items = [
    ["Rapid diagnostic tests", summary.stock.rdt, 1800],
    ["ACT treatment courses", summary.stock.act, 1350],
    ["Treated bed nets", summary.stock.nets, 900]
  ];
  $("#inventory-grid").innerHTML = items.map(([label, value, target]) => `<div class="inventory-item"><span>${label}</span><strong>${value.toLocaleString()}</strong><div class="inventory-track"><i style="width:${Math.min(100, Math.round(value / target * 100))}%"></i></div></div>`).join("");
}

function renderTimeline(cycle) {
  const timeline = $("#agent-timeline");
  if (!cycle) {
    $("#cycle-status").textContent = "No active cycle";
    timeline.innerHTML = `<div class="timeline-item"><span class="timeline-dot">✓</span><div class="timeline-copy"><strong>Feeds synchronized</strong><span>Ready for a new assessment cycle</span></div><span class="timeline-time">${formatTime(state.dashboard.metadata.updatedAt)}</span></div>`;
    return;
  }
  $("#cycle-status").textContent = cycle.status.replaceAll("_", " ");
  timeline.innerHTML = cycle.audit.slice(-5).map((item) => `<div class="timeline-item"><span class="timeline-dot ${escapeHtml(item.status)}">${item.status === "waiting" ? "…" : item.status === "rejected" ? "×" : "✓"}</span><div class="timeline-copy"><strong>${escapeHtml(item.agent)}</strong><span>${escapeHtml(item.detail)}</span></div><span class="timeline-time">${formatTime(item.at)}</span></div>`).join("");
}

function renderDashboard(data) {
  state.dashboard = data;
  renderMetrics(data);
  renderMap(data.assessments);
  renderAlerts(data.assessments);
  renderTable(data.assessments, $("#zone-search").value);
  renderInventory(data.summary);
  renderTimeline(data.latestCycle);
  $("#data-mode-badge").textContent = data.metadata.mode === "operator-entry" ? "Live operator data" : "Demonstration data";
}

function switchView(name) {
  document.querySelectorAll("[data-view-panel]").forEach((panel) => panel.classList.toggle("active", panel.dataset.viewPanel === name));
  document.querySelectorAll("[data-view]").forEach((button) => button.classList.toggle("active", button.dataset.view === name));
  const [title, eyebrow] = viewCopy[name] ?? viewCopy.overview;
  $("#page-title").textContent = title;
  $("#page-eyebrow").textContent = eyebrow;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function fillSelect(selector, items, label, preferredValue) {
  const select = $(selector);
  const current = preferredValue || select.value;
  select.innerHTML = items.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(label(item))}</option>`).join("");
  if (items.some((item) => item.id === current)) select.value = current;
}

function selectedZone(selector) {
  return state.dataset?.zones.find((zone) => zone.id === $(selector).value);
}

function selectedClinic() {
  return state.dataset?.clinics.find((clinic) => clinic.id === $("#supply-clinic").value);
}

function renderClinicalForm() {
  const zone = selectedZone("#clinical-zone");
  if (!zone) return;
  $("#reporting-week").value = state.dataset.metadata.reportingWeek;
  $("#clinical-weeks").innerHTML = zone.weeklyCases.map((value, index) => `<label class="week-input"><small>W-${5 - index}</small><input class="clinical-week" type="number" min="0" step="1" value="${value}" aria-label="Week ${index + 1} cases" required /></label>`).join("");
  $("#clinical-tests").value = zone.tests;
  $("#clinical-positive").value = zone.positiveTests;
}

function renderEnvironmentForm() {
  const zone = selectedZone("#environment-zone");
  if (!zone) return;
  $("#environment-rainfall").value = zone.environment.rainfall7dMm;
  $("#environment-temperature").value = zone.environment.temperatureC;
  $("#environment-humidity").value = zone.environment.humidityPct;
  $("#environment-zone-name").textContent = zone.name;
  $("#signal-rainfall").textContent = `${zone.environment.rainfall7dMm} mm`;
  $("#signal-temperature").textContent = `${zone.environment.temperatureC} °C`;
  $("#signal-humidity").textContent = `${zone.environment.humidityPct}%`;
}

function updateCoverage() {
  for (const resource of ["rdt", "act", "nets"]) {
    const stock = Number($("#stock-" + resource).value);
    const use = Number($("#use-" + resource).value);
    $("#coverage-" + resource).textContent = use > 0 ? `${(stock / use).toFixed(1)} weeks` : "No usage";
  }
}

function renderSupplyForm() {
  const clinic = selectedClinic();
  if (!clinic) return;
  $("#supply-facility-title").textContent = clinic.name;
  for (const resource of ["rdt", "act", "nets"]) {
    $("#stock-" + resource).value = clinic.stock[resource];
    $("#use-" + resource).value = clinic.weeklyUse[resource];
  }
  updateCoverage();
}

function hydrateDataForms() {
  if (!state.dataset) return;
  const zoneLabel = (zone) => `${zone.name} · ${zone.subcounty}`;
  fillSelect("#clinical-zone", state.dataset.zones, zoneLabel);
  fillSelect("#environment-zone", state.dataset.zones, zoneLabel);
  fillSelect("#ai-zone", state.dataset.zones, zoneLabel, state.dashboard?.assessments?.[0]?.zoneId);
  fillSelect("#supply-clinic", state.dataset.clinics, (clinic) => `${clinic.name} · ${state.dataset.zones.find((zone) => zone.id === clinic.zoneId)?.name ?? clinic.zoneId}`);
  const updated = `Updated ${formatTime(state.dataset.metadata.updatedAt)}`;
  $("#clinical-updated").textContent = updated;
  $("#environment-updated").textContent = updated;
  $("#supply-updated").textContent = updated;
  renderClinicalForm();
  renderEnvironmentForm();
  renderSupplyForm();
}

async function loadOperationalData() {
  state.dataset = await api("/api/data");
  hydrateDataForms();
}

async function loadAIStatus() {
  try {
    state.aiStatus = await api("/api/ai/status");
    const status = $("#ai-connection");
    status.classList.toggle("connected", state.aiStatus.configured);
    status.innerHTML = `<i></i>${state.aiStatus.configured ? "API connected" : "API key not configured"}`;
    $("#ai-model").textContent = state.aiStatus.model;
    $("#key-guidance").classList.toggle("hidden", state.aiStatus.configured);
    $("#ai-submit").disabled = !state.aiStatus.configured;
  } catch (error) {
    toast(error.message);
  }
}

function zoneReviewHtml(assessment) {
  return `<div class="review-banner"><strong>Decision support</strong><span>${escapeHtml(assessment.recommendation)} Verify recent facility reports before operational action.</span></div>
    <section class="review-section"><h3>Risk assessment</h3><article class="review-card"><div class="review-card-header"><strong>${escapeHtml(assessment.zoneName)}</strong><span class="risk-badge" style="${riskStyle(assessment.riskLevel)}">${escapeHtml(assessment.riskLevel)} · ${assessment.score}</span></div><div class="review-card-body"><div class="driver-list">${assessment.drivers.map((driver) => `<span class="driver-chip">${escapeHtml(driver.label)} · ${driver.contribution} pts</span>`).join("")}</div></div></article></section>`;
}

function cycleReviewHtml(cycle) {
  if (!cycle.interventions.length) return `<div class="review-banner"><strong>Monitoring only</strong><span>No selected zone crossed the high-risk threshold. Continue routine surveillance and data validation.</span></div>`;
  return `<div class="review-banner"><strong>Human approval required</strong><span>This cycle contains operational drafts. Confirm facility stock counts, route feasibility, and message wording before approval.</span></div>${cycle.interventions.map((item) => `<section class="review-section"><h3>${escapeHtml(item.zoneName)} · risk ${item.assessment.score}</h3>
    <article class="review-card"><div class="review-card-header"><strong>Supply redistribution draft</strong><span>${item.supplyPlan.readinessPct}% readiness</span></div><div class="review-card-body">${item.supplyPlan.recommendations.length ? item.supplyPlan.recommendations.map((move) => `<div class="transfer"><strong>${move.quantity} ${escapeHtml(move.resourceLabel)}</strong><div class="transfer-route">${escapeHtml(move.fromClinic)} → ${escapeHtml(move.toClinic)}<span>${escapeHtml(move.rationale)}</span></div><span class="transfer-eta">${move.distanceKm} km<br>~${move.etaMinutes} min</span></div>`).join("") : `<span class="subtle">No transfers needed.</span>`}${item.supplyPlan.restockRequests.map((request) => `<div class="transfer"><strong>${request.quantity} ${escapeHtml(request.resourceLabel)}</strong><div class="transfer-route">County restock → ${escapeHtml(request.clinic)}<span>Network surplus could not fully cover this safety-stock gap.</span></div><span class="transfer-eta">${escapeHtml(request.priority)}</span></div>`).join("")}</div></article>
    <article class="review-card" id="outreach"><div class="review-card-header"><strong>Localized message drafts</strong><span>${item.advisories.messages.length} variants</span></div><div class="review-card-body">${item.advisories.messages.map((message) => `<div class="message-card"><header><span>${escapeHtml(message.audience)} · ${escapeHtml(message.language)}</span><span>${message.characters} chars · ${message.segments} SMS</span></header><p>${escapeHtml(message.text)}</p></div>`).join("")}</div></article></section>`).join("")}`;
}

function showDialog(title, eyebrow, body, footer = "") {
  $("#dialog-title").textContent = title;
  $("#dialog-eyebrow").textContent = eyebrow;
  $("#dialog-body").innerHTML = body;
  $("#dialog-footer").innerHTML = footer || `<button class="button button-secondary" data-close>Close</button>`;
  $("#dialog-footer").querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => $("#cycle-dialog").close()));
  $("#cycle-dialog").showModal();
}

function openZone(zoneId) {
  const assessment = state.dashboard.assessments.find((item) => item.zoneId === zoneId);
  if (!assessment) return;
  showDialog(assessment.zoneName, "Surveillance detail", zoneReviewHtml(assessment), `<button class="button button-secondary" data-close>Close</button><button class="button button-primary" data-run-zone="${escapeHtml(zoneId)}">Run zone cycle</button>`);
  $("[data-run-zone]").addEventListener("click", () => runCycle(zoneId));
}

async function loadDashboard(showToast = false) {
  try {
    const data = await api("/api/dashboard");
    renderDashboard(data);
    if (showToast) toast("Dashboard refreshed");
  } catch (error) {
    toast(error.message);
  }
}

async function saveForm(form, request, successMessage) {
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  const original = button.textContent;
  button.textContent = "Saving…";
  try {
    await request();
    await Promise.all([loadOperationalData(), loadDashboard()]);
    toast(successMessage);
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function runCycle(zoneId) {
  const button = $("#run-button");
  button.disabled = true;
  button.textContent = "Agents working…";
  try {
    const cycle = await api("/api/cycles", { method: "POST", body: JSON.stringify(zoneId ? { zoneId } : {}) });
    state.selectedCycle = cycle;
    const footer = cycle.status === "pending_approval" ? `<button class="button button-danger" data-decision="reject">Reject draft</button><button class="button button-primary" data-decision="approve">Approve response</button>` : `<button class="button button-secondary" data-close>Close</button>`;
    showDialog("Review response cycle", `Cycle ${cycle.id}`, cycleReviewHtml(cycle), footer);
    $("#dialog-footer").querySelectorAll("[data-decision]").forEach((decisionButton) => decisionButton.addEventListener("click", () => decideCycle(decisionButton.dataset.decision)));
    await loadDashboard();
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
    button.innerHTML = '<span aria-hidden="true">▶</span> Run response cycle';
  }
}

async function decideCycle(decision) {
  try {
    const updated = await api(`/api/cycles/${encodeURIComponent(state.selectedCycle.id)}/${decision}`, { method: "POST", body: JSON.stringify({ reviewer: "Nyanza Operations" }) });
    state.selectedCycle = updated;
    $("#cycle-dialog").close();
    toast(decision === "approve" ? "Response draft approved and recorded" : "Response draft rejected");
    await loadDashboard();
  } catch (error) {
    toast(error.message);
  }
}

$("#run-button").addEventListener("click", () => runCycle());
$("#refresh-button").addEventListener("click", () => loadDashboard(true));
$("#dialog-close").addEventListener("click", () => $("#cycle-dialog").close());
$("#notice-dismiss").addEventListener("click", (event) => event.currentTarget.closest(".notice").remove());
$("#zone-search").addEventListener("input", (event) => renderTable(state.dashboard.assessments, event.target.value));
$("#view-method").addEventListener("click", () => showDialog("How risk is scored", "Transparent method", `<section class="review-section"><h3>Weighted signals</h3><div class="driver-list"><span class="driver-chip">Case acceleration · 40%</span><span class="driver-chip">Test positivity · 23%</span><span class="driver-chip">Rainfall · 16%</span><span class="driver-chip">Humidity · 11%</span><span class="driver-chip">Temperature · 10%</span></div></section><p class="subtle" style="font-size:10px;line-height:1.6;margin-top:18px">This interpretable demonstration score is not a clinically validated prediction model. Before production use, calibrate thresholds on local historical surveillance data, quantify sensitivity and specificity, monitor drift, and obtain epidemiology approval.</p>`));

document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
$("#clinical-zone").addEventListener("change", renderClinicalForm);
$("#environment-zone").addEventListener("change", renderEnvironmentForm);
$("#supply-clinic").addEventListener("change", renderSupplyForm);
for (const resource of ["rdt", "act", "nets"]) {
  $("#stock-" + resource).addEventListener("input", updateCoverage);
  $("#use-" + resource).addEventListener("input", updateCoverage);
}

$("#clinical-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const zoneId = $("#clinical-zone").value;
  saveForm(event.currentTarget, () => api(`/api/data/clinical/${encodeURIComponent(zoneId)}`, {
    method: "PUT",
    body: JSON.stringify({
      reportingWeek: $("#reporting-week").value,
      weeklyCases: [...document.querySelectorAll(".clinical-week")].map((input) => Number(input.value)),
      tests: Number($("#clinical-tests").value),
      positiveTests: Number($("#clinical-positive").value)
    })
  }), "Clinical report saved and risk scores refreshed");
});

$("#environment-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const zoneId = $("#environment-zone").value;
  saveForm(event.currentTarget, () => api(`/api/data/environment/${encodeURIComponent(zoneId)}`, {
    method: "PUT",
    body: JSON.stringify({
      rainfall7dMm: Number($("#environment-rainfall").value),
      temperatureC: Number($("#environment-temperature").value),
      humidityPct: Number($("#environment-humidity").value)
    })
  }), "Environmental observations saved and risk scores refreshed");
});

$("#supply-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const clinicId = $("#supply-clinic").value;
  saveForm(event.currentTarget, () => api(`/api/data/supply/${encodeURIComponent(clinicId)}`, {
    method: "PUT",
    body: JSON.stringify({
      stock: Object.fromEntries(["rdt", "act", "nets"].map((resource) => [resource, Number($("#stock-" + resource).value)])),
      weeklyUse: Object.fromEntries(["rdt", "act", "nets"].map((resource) => [resource, Number($("#use-" + resource).value)]))
    })
  }), "Supply telemetry saved and readiness recalculated");
});

$("#ai-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("#ai-submit");
  const answer = $("#ai-answer");
  button.disabled = true;
  answer.className = "ai-answer loading";
  answer.textContent = "Loading";
  try {
    const brief = await api("/api/ai/brief", {
      method: "POST",
      body: JSON.stringify({ zoneId: $("#ai-zone").value, question: $("#ai-question").value })
    });
    answer.className = "ai-answer";
    answer.textContent = brief.text;
    $("#ai-generated").textContent = `${brief.model} · ${formatTime(brief.generatedAt)}`;
  } catch (error) {
    answer.className = "ai-answer empty";
    answer.innerHTML = `<div class="ai-empty-mark">!</div><strong>Analysis unavailable</strong><p>${escapeHtml(error.message)}</p>`;
  } finally {
    button.disabled = !state.aiStatus?.configured;
  }
});

Promise.all([loadDashboard(), loadOperationalData(), loadAIStatus()]).catch((error) => toast(error.message));

