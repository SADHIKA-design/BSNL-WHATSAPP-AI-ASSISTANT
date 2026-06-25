/**
 * js/app.js
 * Core only: init, navigation, toast, status check.
 * All page logic lives in their own files (groups.js, messages.js, etc.)
 */

// ── Globals (declared ONCE here, used everywhere) ────────────────────────────
let toastTimer = null;
let allGroups  = [];   // shared between groups.js and messages.js

// ── Escape helpers ────────────────────────────────────────────────────────────
function escHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escAttr(str) {
  return escHtml(str);
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, duration = 3000) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), duration);
}

// ── Page Navigation ───────────────────────────────────────────────────────────
function showPage(pageName) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));

  const page = document.getElementById("page-" + pageName);
  if (page) page.classList.add("active");

  const nav = document.querySelector(`[data-page="${pageName}"]`);
  if (nav) nav.classList.add("active");

  try {
    switch (pageName) {
      case "dashboard":  loadDashboard && loadDashboard();  break;
      case "groups":     loadGroups    && loadGroups();     break;
      case "approvals":  loadApprovals && loadApprovals();  break;
      case "alerts":     loadAlerts    && loadAlerts();     break;
      case "knowledge":  loadKnowledge && loadKnowledge();  break;
      case "messages":   loadMsgGroups && loadMsgGroups();  break;
    }
  } catch (err) {
    console.error("Page load error:", err);
  }
}

// ── WhatsApp Bridge Status (proxied through Flask) ────────────────────────────
async function checkStatus() {
  const strip = document.getElementById("wa-status-strip");

  try {
    const res  = await fetch("/wa/status");
    const data = await res.json();

    if (data.connected) {
      const phone = data.number || data.phone || "";
      if (strip) {
        strip.innerHTML = `<span class="status-dot online"></span> Connected${phone ? ": " + escHtml(phone) : ""}`;
      }
      if (phone) localStorage.setItem("owner_phone", phone);
    } else {
      if (strip) strip.innerHTML = `<span class="status-dot offline"></span> Not connected`;
    }
  } catch {
    if (strip) strip.innerHTML = `<span class="status-dot offline"></span> Bridge offline`;
  }
}

// ── Approval polling ──────────────────────────────────────────────────────────
async function pollApprovals() {
  try {
    const data    = await API.listApprovals();
    const pending = Array.isArray(data) ? data.length : 0;
    const badge   = document.getElementById("approval-badge");
    if (badge) badge.textContent = pending || "";
  } catch {/* silent */}
}

// ── Init ──────────────────────────────────────────────────────────────────────
async function initApp() {
  console.log("Frontend loaded");

  if (typeof API === "undefined") {
    console.error("API object missing — check api.js loaded correctly");
    return;
  }

  loadDashboard();
  checkStatus();

  setInterval(checkStatus,   15000);
  setInterval(pollApprovals, 20000);
}

document.addEventListener("DOMContentLoaded", initApp);