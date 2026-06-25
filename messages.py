"""
routes/messages.py
Message webhook (Node bridge calls this) + send endpoint.
"""

from flask import Blueprint, request, jsonify
from database.schema import get_connection
from services.ai_service import generate_reply, detect_urgency
from services.whatsapp_service import send_message

messages_bp = Blueprint("messages", __name__, url_prefix="/api/messages")


# ─────────────────────────────────────────────────────────────────────────────
# WEBHOOK — Node.js bridge POSTs every incoming WhatsApp message here
# ─────────────────────────────────────────────────────────────────────────────

@messages_bp.route("/webhook", methods=["POST"])
def webhook():
    """
    Called by Node.js bridge when a new WhatsApp message arrives.
    Body: { groupId, groupName, sender, message }
    """
    data = request.get_json()
    group_id   = data.get("groupId", "")
    group_name = data.get("groupName", "Unknown")
    sender     = data.get("sender", "")
    content    = data.get("message", "")

    if not content or not group_id:
        return jsonify({"error": "Missing fields"}), 400

    conn = get_connection()

    # Save incoming message
    conn.execute(
        """INSERT INTO messages (group_id, sender, content, direction)
           VALUES (?, ?, ?, 'incoming')""",
        (group_id, sender, content)
    )

    # Save as style sample (all group messages help train the AI)
    conn.execute(
        """INSERT INTO style_samples (group_id, message, is_owner)
           VALUES (?, ?, 0)""",
        (group_id, content)
    )

    # Get group settings
    group = conn.execute(
        "SELECT * FROM groups WHERE group_id = ?", (group_id,)
    ).fetchone()

    if not group:
        # Auto-register unknown group
        conn.execute(
            "INSERT OR IGNORE INTO groups (group_id, name) VALUES (?, ?)",
            (group_id, group_name)
        )
        conn.commit()
        conn.close()
        return jsonify({"status": "group_registered", "ai_action": "none"})

    group = dict(group)

    # Check urgency regardless of AI mode
    urgency = detect_urgency(content)

    # Save alert if important/urgent
    if urgency["level"] in ("important", "urgent"):
        conn.execute(
            """INSERT INTO alerts (group_id, sender, message, urgency, score)
               VALUES (?, ?, ?, ?, ?)""",
            (group_id, sender, content, urgency["level"], urgency["score"])
        )

    conn.commit()

    # If AI is disabled for this group, stop here
    if not group["ai_enabled"]:
        conn.close()
        return jsonify({
            "status": "ai_disabled",
            "urgency": urgency["level"],
        })

    # Silent mode — no auto-reply
    if group["ai_mode"] == "silent":
        conn.close()
        return jsonify({"status": "silent_mode", "urgency": urgency["level"]})

    # Generate AI reply
    result = generate_reply(content, group_id, group_name, group["ai_mode"])

    if result["needs_approval"]:
        # Store for owner approval
        conn.execute(
            """INSERT INTO approvals (group_id, sender, original_msg, suggested_reply)
               VALUES (?, ?, ?, ?)""",
            (group_id, sender, content, result["reply"])
        )
        conn.commit()
        conn.close()
        return jsonify({
            "status":    "pending_approval",
            "urgency":   urgency["level"],
            "suggested": result["reply"],
        })

    # Auto send if auto_reply is enabled
    if group["auto_reply"]:
        send_result = send_message(group_id, result["reply"])
        conn.execute(
            """INSERT INTO messages (group_id, sender, content, direction, ai_generated)
               VALUES (?, 'ai', ?, 'outgoing', 1)""",
            (group_id, result["reply"])
        )
        conn.commit()
        conn.close()
        return jsonify({"status": "replied", "reply": result["reply"]})

    # Store as pending (owner reviews from dashboard)
    conn.execute(
        """INSERT INTO approvals (group_id, sender, original_msg, suggested_reply)
           VALUES (?, ?, ?, ?)""",
        (group_id, sender, content, result["reply"])
    )
    conn.commit()
    conn.close()

    return jsonify({
        "status":    "queued_for_review",
        "urgency":   urgency["level"],
        "suggested": result["reply"],
    })


# ─────────────────────────────────────────────────────────────────────────────
# GET MESSAGES
# ─────────────────────────────────────────────────────────────────────────────

@messages_bp.route("/<group_id>", methods=["GET"])
def get_messages(group_id):
    """Get recent messages for a group."""
    limit = request.args.get("limit", 50, type=int)
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM messages WHERE group_id = ?
           ORDER BY timestamp DESC LIMIT ?""",
        (group_id, limit)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ─────────────────────────────────────────────────────────────────────────────
# MANUAL SEND
# ─────────────────────────────────────────────────────────────────────────────

@messages_bp.route("/send", methods=["POST"])
def manual_send():
    """Owner manually sends a message from dashboard."""
    data = request.get_json()
    group_id = data.get("groupId")
    message  = data.get("message")

    if not group_id or not message:
        return jsonify({"error": "groupId and message required"}), 400

    result = send_message(group_id, message)
    return jsonify(result)
