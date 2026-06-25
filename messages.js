/**
 * js/messages.js
 * Message thread viewer and manual send.
 * NOTE: activeGroupId / activeGroupName declared here (not in app.js).
 */

let activeGroupId   = null;
let activeGroupName = null;

function renderMsgGroupList(groups) {
  const el = document.getElementById("msg-group-list");
  if (!el) return;

  if (!groups.length) {
    el.innerHTML = "<p style='color:var(--text2);font-size:13px'>No groups selected yet. Go to Groups and select some.</p>";
    return;
  }

  el.innerHTML = groups.map(g => `
    <div class="msg-group-item" id="msg-grp-${CSS.escape(g.group_id)}"
      onclick="setActiveGroup('${escAttr(g.group_id)}', '${escAttr(g.name)}')">
      ${escHtml(g.name)}
    </div>
  `).join("");
}

async function setActiveGroup(groupId, name) {
  activeGroupId   = groupId;
  activeGroupName = name;

  document.querySelectorAll(".msg-group-item").forEach(el => el.classList.remove("active"));
  const item = document.getElementById(`msg-grp-${CSS.escape(groupId)}`);
  if (item) item.classList.add("active");

  await loadMessages(groupId);
}

async function loadMessages(groupId) {
  const thread = document.getElementById("message-thread");
  if (!thread) return;
  thread.innerHTML = "<p class='placeholder'>Loading…</p>";

  try {
    const messages = await API.getMessages(groupId);

    if (!messages.length) {
      thread.innerHTML = "<p class='placeholder'>No messages in this group yet.</p>";
      return;
    }

    thread.innerHTML = messages
      .slice()
      .reverse()
      .map(m => `
        <div class="message-bubble ${escHtml(m.direction)}">
          ${m.direction === "incoming"
            ? `<div class="msg-sender">${escHtml(m.sender)}</div>`
            : m.ai_generated
              ? `<div class="msg-sender"><span class="ai-tag">AI</span></div>`
              : ""}
          ${escHtml(m.content)}
          <div class="msg-time">${escHtml(m.timestamp)}</div>
        </div>
      `).join("");

    thread.scrollTop = thread.scrollHeight;
  } catch (e) {
    thread.innerHTML = `<p class='placeholder' style='color:var(--red)'>Error: ${e.message}</p>`;
  }
}

async function sendManualMessage() {
  const input = document.getElementById("send-message-input");
  if (!input) return;
  const text = input.value.trim();

  if (!text)          { showToast("⚠️ Type a message first"); return; }
  if (!activeGroupId) { showToast("⚠️ Select a group first"); return; }

  try {
    await API.sendMessage(activeGroupId, text);
    input.value = "";
    showToast("✅ Sent");
    await loadMessages(activeGroupId);
  } catch (e) {
    showToast("❌ Send failed: " + e.message);
  }
}

// Enter key to send
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("send-message-input")?.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendManualMessage();
    }
  });
});