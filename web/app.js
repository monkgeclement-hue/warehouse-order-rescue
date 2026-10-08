const casesNode = document.querySelector("#cases");
const countNode = document.querySelector("#active-count");
const connectionNode = document.querySelector("#connection-state");
const runButton = document.querySelector("#run-demo");
const toastNode = document.querySelector("#toast");
let toastTimer;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}
function formatCutoff(value) {
  if (!value) return "Cutoff time unavailable";
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(new Date(value));
}
function renderCases(cases) {
  const rank = { HIGH: 0, MEDIUM: 1, LOW: 2 };
  const visible = [...cases].sort((a, b) => rank[a.risk_level] - rank[b.risk_level]);
  countNode.textContent = visible.filter((item) => item.status !== "RESOLVED").length;
  if (!visible.length) {
    casesNode.innerHTML = '<div class="empty-state"><div class="empty-icon" aria-hidden="true">↗</div><h3>No exception cases yet</h3><p>Run the demo to send a synthetic order through the event pipeline.</p></div>';
    return;
  }
  casesNode.innerHTML = visible.map((item) => {
    const evidence = item.evidence || {};
    const shorts = (evidence.short_lines || []).map((line) => `${line.sku}: ${line.picked_qty ?? 0}/${line.requested_qty ?? "?"} picked · ${line.reserve_qty ?? 0} in reserve`);
    const facts = [
      `${evidence.picked_line_count ?? 0}/${evidence.expected_line_count ?? "?"} lines picked`,
      `${evidence.minutes_until_cutoff ?? "?"} min to cutoff (${formatCutoff(evidence.carrier_cutoff_at)})`,
      ...shorts,
    ];
    return `<article class="case-card">
      <div class="case-head"><div><div class="case-title"><h3>${escapeHtml(item.order_id)}</h3><span class="case-id">${escapeHtml(item.case_id)}</span></div><p class="case-summary">${escapeHtml(item.summary)}</p></div>
      <div class="badges"><span class="badge ${escapeHtml(item.risk_level.toLowerCase())}">${escapeHtml(item.risk_level)} RISK</span><span class="badge status">${escapeHtml(item.status.replaceAll("_", " "))}</span></div></div>
      <div class="details"><div class="detail-panel"><h4>WHY THIS CASE OPENED</h4><p>Evidence from the event history:</p><div class="evidence">${facts.map((fact) => `<span>${escapeHtml(fact)}</span>`).join("")}</div></div>
      <div class="detail-panel recommendation"><h4>SUGGESTED NEXT STEP</h4><p>${escapeHtml(item.recommendation)}</p></div></div>
      <div class="source-note">Warehouse ${escapeHtml(item.warehouse_id)} · Source: ${escapeHtml(item.source)} · Suggestions require supervisor review</div>
    </article>`;
  }).join("");
}
function showToast(message) {
  toastNode.textContent = message;
  toastNode.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastNode.classList.remove("show"), 3200);
}
async function refreshCases() {
  const response = await fetch("/api/v1/cases");
  if (!response.ok) throw new Error("Could not load cases");
  renderCases((await response.json()).cases);
}

runButton.addEventListener("click", async () => {
  runButton.disabled = true;
  runButton.textContent = "Sending events…";
  try {
    const response = await fetch("/api/v1/demo/run", { method: "POST" });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Demo scenario failed");
    if (result.case) showToast(`Scenario sent. Case ${result.case.case_id} is ${result.case.risk_level.toLowerCase()} risk.`);
    await refreshCases();
  } catch (error) {
    showToast(error.message || "Could not reach the service");
  } finally {
    runButton.disabled = false;
    runButton.innerHTML = 'Run demo scenario <span aria-hidden="true">→</span>';
  }
});

refreshCases().catch(() => showToast("Could not load cases. Is the API running?"));
const stream = new EventSource("/api/v1/stream/cases");
stream.addEventListener("open", () => {
  connectionNode.textContent = "Live updates connected";
  connectionNode.parentElement.classList.remove("offline");
});
stream.addEventListener("error", () => {
  connectionNode.textContent = "Reconnecting to live updates…";
  connectionNode.parentElement.classList.add("offline");
});
stream.addEventListener("snapshot", (message) => renderCases(JSON.parse(message.data).cases));
stream.addEventListener("case.updated", (message) => {
  const incoming = JSON.parse(message.data).case;
  fetch("/api/v1/cases").then((response) => response.json()).then((data) => renderCases(data.cases));
  showToast(`Order ${incoming.order_id} updated: ${incoming.risk_level.toLowerCase()} risk`);
});
