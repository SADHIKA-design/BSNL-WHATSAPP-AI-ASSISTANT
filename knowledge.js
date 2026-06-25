/**
 * js/knowledge.js
 * Knowledge base: list, add, edit, delete.
 */

let editingKnowledgeId = null;

async function loadKnowledge() {
  const el = document.getElementById("knowledge-list");
  if (!el) return;

  try {
    const items = await API.listKnowledge();
    renderKnowledge(items);
  } catch (e) {
    el.innerHTML = `<p style="color:var(--red)">Failed to load knowledge: ${e.message}</p>`;
  }
}

function renderKnowledge(items) {
  const el = document.getElementById("knowledge-list");
  if (!el) return;

  if (!items.length) {
    el.innerHTML = `<div class="empty-state">
      <div class="empty-icon">📚</div>
      <p>No knowledge entries yet. Add your projects, plans, and decisions so the AI can use them.</p>
    </div>`;
    return;
  }

  el.innerHTML = items.map(k => `
    <div class="knowledge-card" id="knowledge-${k.id}">
      <div class="k-cat">${escHtml(k.category)}</div>
      <div class="k-title">${escHtml(k.title)}</div>
      <div class="k-content">${escHtml(k.content)}</div>
      <div class="k-actions">
        <button class="btn btn-outline btn-sm"
          onclick="editKnowledge(${k.id}, '${escAttr(k.category)}', '${escAttr(k.title)}', '${escAttr(k.content)}')">
          ✏️ Edit
        </button>
        <button class="btn btn-danger btn-sm" onclick="deleteKnowledge(${k.id})">
          🗑 Delete
        </button>
      </div>
    </div>
  `).join("");
}

function openKnowledgeModal() {
  editingKnowledgeId = null;
  document.getElementById("modal-title").textContent = "Add Knowledge";
  document.getElementById("k-category").value = "project";
  document.getElementById("k-title").value    = "";
  document.getElementById("k-content").value  = "";
  document.getElementById("knowledge-modal").classList.add("open");
}

function editKnowledge(id, category, title, content) {
  editingKnowledgeId = id;
  document.getElementById("modal-title").textContent = "Edit Knowledge";
  document.getElementById("k-category").value = category;
  document.getElementById("k-title").value    = title;
  document.getElementById("k-content").value  = content;
  document.getElementById("knowledge-modal").classList.add("open");
}

function closeKnowledgeModal() {
  document.getElementById("knowledge-modal").classList.remove("open");
}

async function saveKnowledge() {
  const data = {
    category: document.getElementById("k-category").value,
    title:    document.getElementById("k-title").value.trim(),
    content:  document.getElementById("k-content").value.trim(),
  };

  if (!data.title || !data.content) {
    showToast("⚠️ Title and content are required");
    return;
  }

  try {
    if (editingKnowledgeId) {
      await API.updateKnowledge(editingKnowledgeId, data);
      showToast("✅ Knowledge updated");
    } else {
      await API.addKnowledge(data);
      showToast("✅ Knowledge added");
    }
    closeKnowledgeModal();
    loadKnowledge();
  } catch (e) {
    showToast("❌ Save failed: " + e.message);
  }
}

async function deleteKnowledge(id) {
  if (!confirm("Delete this knowledge entry?")) return;
  try {
    await API.deleteKnowledge(id);
    showToast("Deleted");
    document.getElementById(`knowledge-${id}`)?.remove();
  } catch (e) {
    showToast("❌ Delete failed");
  }
}