/**
 * js/api.js — All backend API calls
 */

async function apiGet(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}
async function apiPost(path, body = {}) {
  const r = await fetch(path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}
async function apiPut(path, body = {}) {
  const r = await fetch(path, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}
async function apiDelete(path) {
  const r = await fetch(path, { method: "DELETE" });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

window.API = {
  // Owner / Setup
  getOwner:        ()           => apiGet("/api/owner"),
  saveOwner:       (data)       => apiPost("/api/owner", data),

  // Status
  getStatus:       ()           => apiGet("/wa/status"),
  getStats:        ()           => apiGet("/api/stats"),

  // Groups
  listGroups:      ()           => apiGet("/api/groups/"),
  syncGroups:      ()           => apiPost("/api/groups/sync"),
  selectGroup:     (id, sel)    => apiPost(`/api/groups/${encodeURIComponent(id)}/select`, { selected: sel }),
  toggleGroup:     (id, val)    => apiPost(`/api/groups/${encodeURIComponent(id)}/enabled`, { enabled: val }),
  toggleAI:        (id)         => apiPost(`/api/groups/${encodeURIComponent(id)}/toggle`),
  setMode:         (id, mode)   => apiPost(`/api/groups/${encodeURIComponent(id)}/mode`, { mode }),
  setAutoReply:    (id, val)    => apiPost(`/api/groups/${encodeURIComponent(id)}/auto_reply`, { enabled: val }),
  setGroupStyle:   (id, style)  => apiPost(`/api/groups/${encodeURIComponent(id)}/style`, { style }),
  learnStyle:      (id)         => apiPost(`/api/groups/${encodeURIComponent(id)}/learn`),
  getProfile:      (id)         => apiGet(`/api/groups/${encodeURIComponent(id)}/profile`),
  addSample:       (id, msg)    => apiPost(`/api/groups/${encodeURIComponent(id)}/add_sample`, { message: msg }),

  // Messages
  getMessages:     (id, lim=50) => apiGet(`/api/messages/${encodeURIComponent(id)}?limit=${lim}`),
  sendMessage:     (gId, msg)   => apiPost("/api/messages/send", { groupId: gId, message: msg }),

  // Approvals
  listApprovals:   ()           => apiGet("/api/approvals"),
  approve:         (id, reply)  => apiPost(`/api/approvals/${id}/approve`, { reply }),
  reject:          (id)         => apiPost(`/api/approvals/${id}/reject`),

  // Alerts
  listAlerts:      ()           => apiGet("/api/alerts"),
  dismissAlert:    (id)         => apiPost(`/api/alerts/${id}/dismiss`),

  // Knowledge
  listKnowledge:   ()           => apiGet("/api/knowledge"),
  addKnowledge:    (data)       => apiPost("/api/knowledge", data),
  updateKnowledge: (id, data)   => apiPut(`/api/knowledge/${id}`, data),
  deleteKnowledge: (id)         => apiDelete(`/api/knowledge/${id}`),
};