"""
routes/dashboard.py
Approval queue, knowledge base, alerts endpoints.
"""

import json
import requests
from flask import Blueprint, request, jsonify
from database.schema import get_connection
from services.whatsapp_service import send_message

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api")


# ─────────────────────────────────────────────────────────────────────────────
# APPROVALS
# ─────────────────────────────────────────────────────────────────────────────

@dashboard_bp.route("/approvals", methods=["GET"])
def list_approvals():
    """List all pending approvals."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM approvals WHERE status = 'pending' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@dashboard_bp.route("/approvals/<int:approval_id>/approve", methods=["POST"])
def approve(approval_id):
    """Approve and send the suggested reply (or a custom one)."""
    data         = request.get_json() or {}
    custom_reply = data.get("reply")  # optional override

    conn = get_connection()
    row  = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404

    row = dict(row)
    final = custom_reply or row["suggested_reply"]

    send_message(row["group_id"], final)

    conn.execute(
        """UPDATE approvals
           SET status = 'approved', final_reply = ?, resolved_at = datetime('now')
           WHERE id = ?""",
        (final, approval_id)
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "sent", "reply": final})


@dashboard_bp.route("/approvals/<int:approval_id>/reject", methods=["POST"])
def reject(approval_id):
    """Reject an approval (no message sent)."""
    conn = get_connection()
    conn.execute(
        "UPDATE approvals SET status = 'rejected', resolved_at = datetime('now') WHERE id = ?",
        (approval_id,)
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "rejected"})


# ─────────────────────────────────────────────────────────────────────────────
# KNOWLEDGE BASE
# ─────────────────────────────────────────────────────────────────────────────

@dashboard_bp.route("/knowledge", methods=["GET"])
def list_knowledge():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM knowledge ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@dashboard_bp.route("/knowledge", methods=["POST"])
def add_knowledge():
    """Add a new knowledge item."""
    data = request.get_json()
    required = ("category", "title", "content")
    if not all(data.get(k) for k in required):
        return jsonify({"error": "category, title, content are required"}), 400

    tags = json.dumps(data.get("tags", []))

    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO knowledge (category, title, content, tags) VALUES (?, ?, ?, ?)",
        (data["category"], data["title"], data["content"], tags)
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()

    return jsonify({"id": new_id, "status": "created"}), 201


@dashboard_bp.route("/knowledge/<int:kid>", methods=["PUT"])
def update_knowledge(kid):
    data = request.get_json()
    conn = get_connection()
    conn.execute(
        "UPDATE knowledge SET title = ?, content = ? WHERE id = ?",
        (data.get("title"), data.get("content"), kid)
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "updated"})


@dashboard_bp.route("/knowledge/<int:kid>", methods=["DELETE"])
def delete_knowledge(kid):
    conn = get_connection()
    conn.execute("DELETE FROM knowledge WHERE id = ?", (kid,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})


# ─────────────────────────────────────────────────────────────────────────────
# ALERTS
# ─────────────────────────────────────────────────────────────────────────────

@dashboard_bp.route("/alerts", methods=["GET"])
def list_alerts():
    """List unseen alerts."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM alerts WHERE seen = 0 ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@dashboard_bp.route("/alerts/<int:alert_id>/seen", methods=["POST"])
def mark_seen(alert_id):
    conn = get_connection()
    conn.execute("UPDATE alerts SET seen = 1 WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "seen"})


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD STATS
# ─────────────────────────────────────────────────────────────────────────────

@dashboard_bp.route("/stats", methods=["GET"])
def stats():
    """Quick stats for the dashboard home page."""
    conn = get_connection()

    total_groups   = conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0]
    ai_on_groups   = conn.execute("SELECT COUNT(*) FROM groups WHERE ai_enabled = 1").fetchone()[0]
    total_messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    pending        = conn.execute("SELECT COUNT(*) FROM approvals WHERE status = 'pending'").fetchone()[0]
    unseen_alerts  = conn.execute("SELECT COUNT(*) FROM alerts WHERE seen = 0").fetchone()[0]
    urgent_alerts  = conn.execute("SELECT COUNT(*) FROM alerts WHERE urgency = 'urgent' AND seen = 0").fetchone()[0]

    conn.close()

    return jsonify({
        "total_groups":   total_groups,
        "ai_on_groups":   ai_on_groups,
        "total_messages": total_messages,
        "pending":        pending,
        "unseen_alerts":  unseen_alerts,
        "urgent_alerts":  urgent_alerts,
    })


# ─────────────────────────────────────────────────────────────────────────────
# WA STATUS PROXY
# ─────────────────────────────────────────────────────────────────────────────

@dashboard_bp.route("/wa/status", methods=["GET"])
def wa_status():
    """Proxy WhatsApp status from the Node bridge so the frontend never
    calls localhost:3000 directly."""
    try:
        r = requests.get("http://localhost:3000/status", timeout=5)
        r.raise_for_status()
        return jsonify(r.json())
    except requests.exceptions.ConnectionError:
        return jsonify({"connected": False, "phone": None, "error": "bridge_offline"}), 503
    except requests.exceptions.Timeout:
        return jsonify({"connected": False, "phone": None, "error": "bridge_timeout"}), 504
    except Exception as e:
        return jsonify({"connected": False, "phone": None, "error": str(e)}), 500