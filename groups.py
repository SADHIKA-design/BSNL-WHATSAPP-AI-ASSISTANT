from flask import Blueprint, jsonify, request
from database.schema import get_connection
import requests as http_requests

groups_bp = Blueprint("groups", __name__)

BRIDGE_URL = "http://localhost:3000"


# ── GET ALL GROUPS ────────────────────────────────────────────────────────────
@groups_bp.route("/api/groups/", methods=["GET"])
@groups_bp.route("/api/groups", methods=["GET"])
def get_groups():
    con = get_connection()
    rows = con.execute("SELECT * FROM groups ORDER BY name").fetchall()
    con.close()
    return jsonify([
        {
            "id":         row["group_id"],
            "name":       row["name"],
            "enabled":    bool(row["ai_enabled"]),   # master switch
            "ai_enabled": bool(row["ai_enabled"]),
            "ai_mode":    row["ai_mode"],
            "auto_reply": bool(row["auto_reply"]),
            "style":      row["ai_mode"] or "casual",
        }
        for row in rows
    ])


# ── SYNC GROUPS ───────────────────────────────────────────────────────────────
@groups_bp.route("/api/groups/sync", methods=["POST"])
def sync_groups():
    # Accept push from bridge (POST body) OR pull from bridge directly
    data = request.get_json(silent=True) or {}
    groups = data.get("groups")

    if not groups:
        # Pull from bridge
        try:
            resp = http_requests.get(f"{BRIDGE_URL}/groups", timeout=10)
            resp.raise_for_status()
            bridge_data = resp.json()
            groups = bridge_data if isinstance(bridge_data, list) else bridge_data.get("groups", [])
        except http_requests.exceptions.ConnectionError:
            return jsonify({"error": "Cannot reach WhatsApp bridge"}), 503
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if not groups:
        return jsonify({"error": "No groups returned"}), 400

    con = get_connection()
    for g in groups:
        gid  = g.get("id") or g.get("group_id")
        name = g.get("name", "")
        if gid:
            con.execute("""
                INSERT INTO groups (group_id, name)
                VALUES (?, ?)
                ON CONFLICT(group_id) DO UPDATE SET name = excluded.name
            """, (gid, name))
    con.commit()
    con.close()

    return jsonify({"status": "success", "synced": len(groups), "message": f"{len(groups)} groups synced"})


# ── TOGGLE MASTER (enabled) ───────────────────────────────────────────────────
@groups_bp.route("/api/groups/<path:group_id>/enabled", methods=["POST"])
def set_enabled(group_id):
    data    = request.get_json() or {}
    enabled = int(bool(data.get("enabled", True)))
    con     = get_connection()
    con.execute("UPDATE groups SET ai_enabled=? WHERE group_id=?", (enabled, group_id))
    con.commit()
    con.close()
    return jsonify({"group_id": group_id, "enabled": bool(enabled)})


# ── TOGGLE AI ─────────────────────────────────────────────────────────────────
@groups_bp.route("/api/groups/<path:group_id>/toggle", methods=["POST"])
@groups_bp.route("/api/groups/<path:group_id>/toggle-ai", methods=["POST"])
def toggle_ai(group_id):
    con = get_connection()
    row = con.execute("SELECT ai_enabled FROM groups WHERE group_id=?", (group_id,)).fetchone()
    if not row:
        con.close()
        return jsonify({"error": "Group not found"}), 404
    new_val = 0 if row["ai_enabled"] else 1
    con.execute("UPDATE groups SET ai_enabled=? WHERE group_id=?", (new_val, group_id))
    con.commit()
    con.close()
    return jsonify({"group_id": group_id, "ai_enabled": bool(new_val)})


# ── SET MODE / STYLE ──────────────────────────────────────────────────────────
@groups_bp.route("/api/groups/<path:group_id>/mode", methods=["POST"])
@groups_bp.route("/api/groups/<path:group_id>/style", methods=["POST"])
def set_mode(group_id):
    data = request.get_json() or {}
    mode = data.get("mode") or data.get("style", "casual")
    con  = get_connection()
    con.execute("UPDATE groups SET ai_mode=? WHERE group_id=?", (mode, group_id))
    con.commit()
    con.close()
    return jsonify({"group_id": group_id, "ai_mode": mode})


# ── AUTO REPLY ────────────────────────────────────────────────────────────────
@groups_bp.route("/api/groups/<path:group_id>/auto_reply", methods=["POST"])
@groups_bp.route("/api/groups/<path:group_id>/autoreply", methods=["POST"])
def set_auto_reply(group_id):
    data    = request.get_json() or {}
    con     = get_connection()
    row     = con.execute("SELECT auto_reply FROM groups WHERE group_id=?", (group_id,)).fetchone()
    if not row:
        con.close()
        return jsonify({"error": "Group not found"}), 404
    if "enabled" in data:
        new_val = int(bool(data["enabled"]))
    else:
        new_val = 0 if row["auto_reply"] else 1
    con.execute("UPDATE groups SET auto_reply=? WHERE group_id=?", (new_val, group_id))
    con.commit()
    con.close()
    return jsonify({"group_id": group_id, "auto_reply": bool(new_val)})


# ── GROUP STATUS ──────────────────────────────────────────────────────────────
@groups_bp.route("/api/groups/<path:group_id>/status", methods=["GET"])
def group_status(group_id):
    con = get_connection()
    row = con.execute(
        "SELECT ai_enabled, ai_mode, auto_reply FROM groups WHERE group_id=?", (group_id,)
    ).fetchone()
    con.close()
    if not row:
        return jsonify({"enabled": False})
    return jsonify({
        "enabled":    bool(row["ai_enabled"]),
        "ai_mode":    row["ai_mode"],
        "auto_reply": bool(row["auto_reply"]),
    })


# ── SELECT ────────────────────────────────────────────────────────────────────
@groups_bp.route("/api/groups/<path:group_id>/select", methods=["POST"])
def select_group(group_id):
    data     = request.get_json() or {}
    selected = int(bool(data.get("selected", True)))
    con      = get_connection()
    try:
        con.execute("UPDATE groups SET selected=? WHERE group_id=?", (selected, group_id))
    except Exception:
        con.execute("ALTER TABLE groups ADD COLUMN selected INTEGER DEFAULT 0")
        con.execute("UPDATE groups SET selected=? WHERE group_id=?", (selected, group_id))
    con.commit()
    con.close()
    return jsonify({"group_id": group_id, "selected": bool(selected)})