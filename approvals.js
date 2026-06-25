/**
 * js/approvals.js
 * Approval queue: show pending, approve / reject replies.
 */

async function loadApprovals() {
  const el = document.getElementById("approvals-list");
  if (!el) return;

  try {
    const approvals = await API.listApprovals();
    renderApprovals(approvals);
  } catch (e) {
    el.innerHTML = `<p style="color:var(--red)">Failed to load approvals: ${e.message}</p>`;
  }
}

function renderApprovals(approvals) {
  const el = document.getElementById("approvals-list");
  if (!el) return;

  if (!approvals.length) {
    el.innerHTML = `<div class="empty-state">
      <div class="empty-icon">✅</div>
      <p>No pending approvals — all caught up!</p>
    </div>`;
    return;
  }

  el.innerHTML = approvals.map(a => `
    <div class="approval-card" id="approval-${a.id}">
      <div class="approval-meta">
        <span>📱 ${escHtml(a.group_id)}</span>
        <span>👤 ${escHtml(a.sender)}</span>
        <span>🕐 ${escHtml(a.created_at)}</span>
      </div>
      <div class="approval-original">
        <strong style="font-size:11px;color:var(--text2)">RECEIVED</strong><br>
        ${escHtml(a.original_msg)}
      </div>
      <div class="approval-suggested">
        <label>AI SUGGESTED REPLY (edit if needed)</label>
        <textarea id="reply-text-${a.id}">${escHtml(a.suggested_reply)}</textarea>
      </div>
      <div class="approval-actions">
        <button class="btn btn-primary btn-sm" onclick="approveReply(${a.id})">✅ Send Reply</button>
        <button class="btn btn-danger btn-sm"  onclick="rejectReply(${a.id})">✕ Reject</button>
      </div>
    </div>
  `).join("");
}

async function approveReply(id) {
  const textarea = document.getElementById(`reply-text-${id}`);
  const reply    = textarea ? textarea.value.trim() : "";
  try {
    await API.approve(id, reply);
    showToast("✅ Reply sent!");
    document.getElementById(`approval-${id}`)?.remove();
    loadDashboard();
  } catch (e) {
    showToast("❌ Send failed: " + e.message);
  }
}

async function rejectReply(id) {
  try {
    await API.reject(id);
    showToast("Approval rejected");
    document.getElementById(`approval-${id}`)?.remove();
    loadDashboard();
  } catch (e) {
    showToast("❌ Reject failed");
  }
}