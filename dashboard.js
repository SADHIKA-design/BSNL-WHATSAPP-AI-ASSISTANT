/**
 * js/dashboard.js
 * Loads and renders dashboard stats, WA status strip, and recent alerts.
 * Relies on app:ready event from app.js — no direct WA calls here.
 */

// ── Constants ─────────────────────────────────────────────────────────────────
const REFRESH_INTERVAL_MS = 30_000;
let _refreshTimer = null;

// ── Guard: escHtml (if loaded standalone) ────────────────────────────────────
if (typeof escHtml !== "function") {
  window.escHtml = (str) =>
    String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
}

// ── Alert icon ────────────────────────────────────────────────────────────────
function alertIcon(level) {
  return { urgent: "🚨", important: "⚠️", normal: "ℹ️" }[level] ?? "🔔";
}

// ── WA status strip ───────────────────────────────────────────────────────────
function renderStatusStrip(status) {
  const el = document.getElementById("wa-status-strip");
  if (!el) return;

  if (status?.connected && status.phone) {
    el.className = "status-strip status-strip--connected";
    el.innerHTML = `<span class="status-dot"></span>
      Connected · <strong>${escHtml(status.phone)}</strong>`;
  } else {
    el.className = "status-strip status-strip--disconnected";
    el.innerHTML = `<span class="status-dot"></span>
      WhatsApp disconnected —
      <a href="#" onclick="showPage('page-login');return false;">Reconnect</a>`;
  }
}

// ── Stats ─────────────────────────────────────────────────────────────────────
function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function setBadge(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value || "";
}

async function loadStats() {
  try {
    const stats = await API.getStats();

    setText("stat-groups",   stats.total_groups   ?? "—");
    setText("stat-ai-on",    stats.ai_on_groups   ?? "—");
    setText("stat-messages", stats.total_messages ?? "—");
    setText("stat-pending",  stats.pending        ?? "—");
    setText("stat-urgent",   stats.urgent_alerts  ?? "—");

    setBadge("approval-badge", stats.pending);
    setBadge("alert-badge",    stats.urgent_alerts);
  } catch (e) {
    console.error("[dashboard] stats failed:", e);
  }
}

// ── Alerts preview ────────────────────────────────────────────────────────────
function renderDashAlerts(alerts) {
  const el = document.getElementById("dash-alerts-list");
  if (!el) return;

  if (!alerts.length) {
    el.innerHTML = `<div class="empty-state">
      <div class="empty-icon">🔕</div>
      <p>No new alerts</p>
    </div>`;
    return;
  }

  el.innerHTML = alerts.map(a => `
    <div class="alert-item ${escHtml(a.urgency)}">
      <div class="alert-icon">${alertIcon(a.urgency)}</div>
      <div class="alert-body">
        <div class="alert-msg">${escHtml(a.message)}</div>
        <div class="alert-meta">From: ${escHtml(a.sender)} · ${escHtml(a.created_at)}</div>
      </div>
      <span class="alert-level ${escHtml(a.urgency)}">${escHtml(a.urgency)}</span>
    </div>
  `).join("");
}

async function loadAlerts() {
  try {
    const data = await API.listAlerts();
    const alerts = Array.isArray(data) ? data : (data.alerts ?? []);
    renderDashAlerts(alerts.slice(0, 5));
  } catch (e) {
    console.error("[dashboard] alerts failed:", e);
  }
}

// ── Main load ─────────────────────────────────────────────────────────────────
async function loadDashboard(status) {
  renderStatusStrip(status);
  await Promise.all([loadStats(), loadAlerts()]);
}

// ── Auto-refresh ──────────────────────────────────────────────────────────────
function startRefresh(status) {
  clearInterval(_refreshTimer);
  _refreshTimer = setInterval(() => loadDashboard(status), REFRESH_INTERVAL_MS);
}

// ── Entry point — fired by app.js ─────────────────────────────────────────────
document.addEventListener("app:ready", ({ detail }) => {
  loadDashboard(detail.status);
  startRefresh(detail.status);
});

// Stop polling when user leaves the dashboard page (optional UX nicety)
document.addEventListener("page:change", ({ detail }) => {
  if (detail?.page !== "page-dashboard") {
    clearInterval(_refreshTimer);
  }
});