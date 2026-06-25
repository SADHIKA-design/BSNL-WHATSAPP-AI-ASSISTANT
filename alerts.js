/**
 * js/alerts.js
 * Render and manage alerts.
 */

// ── Helpers (safe to re-declare if not already in scope) ─────────────────────

if (typeof escHtml !== "function") {
  window.escHtml = function(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  };
}

if (typeof escAttr !== "function") {
  window.escAttr = window.escHtml;
}

if (typeof alertIcon !== "function") {
  window.alertIcon = function(level) {
    return { urgent: "🚨", important: "⚠️", normal: "ℹ️" }[level] || "🔔";
  };
}

// ── Load ──────────────────────────────────────────────────────────────────────

async function loadAlerts() {
  const el = document.getElementById("alerts-list");
  if (!el) return;

  el.innerHTML = `<div class="empty-state"><p>Loading alerts…</p></div>`;

  try {
    // FIX: handle both [] and { alerts: [] } response shapes
    const data = await API.listAlerts();
    const alerts = Array.isArray(data) ? data : (data.alerts ?? []);
    renderAlerts(alerts);
  } catch (e) {
    el.innerHTML = `<p style="color:var(--red)">Failed to load alerts: ${e.message}</p>`;
  }
}

// ── Render ────────────────────────────────────────────────────────────────────

function renderAlerts(alerts) {
  const el = document.getElementById("alerts-list");
  if (!el) return;

  if (!alerts.length) {
    el.innerHTML = `<div class="empty-state">
      <div class="empty-icon">🔕</div>
      <p>No new alerts</p>
    </div>`;
    return;
  }

  el.innerHTML = alerts.map(a => `
    <div class="alert-item ${escHtml(a.urgency)}" id="alert-${a.id}">
      <div class="alert-icon">${alertIcon(a.urgency)}</div>
      <div class="alert-body">
        <div class="alert-msg">${escHtml(a.message)}</div>
        <div class="alert-meta">
          From: <strong>${escHtml(a.sender)}</strong>
          in group: ${escHtml(a.group_id)}
          · Score: ${a.score != null ? (a.score * 100).toFixed(0) + "%" : "—"}
          · ${escHtml(a.created_at)}
        </div>
      </div>
      <div style="display:flex;flex-direction:column;gap:6px;align-items:flex-end">
        <span class="alert-level ${escHtml(a.urgency)}">${escHtml(a.urgency)}</span>
        <button class="btn btn-outline btn-sm" onclick="dismissAlert(${a.id})">Dismiss</button>
      </div>
    </div>
  `).join("");
}

// ── Dismiss ───────────────────────────────────────────────────────────────────

async function dismissAlert(id) {
  try {
    await API.markSeen(id);
    const el = document.getElementById(`alert-${id}`);
    if (el) el.remove();
    // Refresh dashboard badge counts if available
    if (typeof loadDashboard === "function") loadDashboard();
  } catch (e) {
    if (typeof showToast === "function") showToast("❌ Failed to dismiss alert");
    else console.error("Dismiss failed:", e.message);
  }
}