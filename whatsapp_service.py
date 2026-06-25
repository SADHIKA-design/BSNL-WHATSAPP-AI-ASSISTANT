"""
services/whatsapp_service.py
Handles sending messages to WhatsApp via the Node.js bridge.
"""

import os
import json
import urllib.request
import urllib.error
from database.schema import get_connection

BRIDGE_URL = os.getenv("WHATSAPP_BRIDGE_URL", "http://localhost:3000")


# ─────────────────────────────────────────────────────────────────────────────
# HTTP HELPER (no requests library needed)
# ─────────────────────────────────────────────────────────────────────────────

def _post(url: str, data: dict) -> dict:
    """Simple HTTP POST using urllib (stdlib only)."""
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return {"error": str(e), "bridge_down": True}


def _get(url: str) -> dict:
    """Simple HTTP GET using urllib."""
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return {"error": str(e), "bridge_down": True}


# ─────────────────────────────────────────────────────────────────────────────
# SEND MESSAGE
# ─────────────────────────────────────────────────────────────────────────────

def send_message(group_id: str, message: str) -> dict:
    """Send a message to a WhatsApp group via the Node bridge."""
    result = _post(f"{BRIDGE_URL}/send", {
        "groupId": group_id,
        "message": message,
    })

    # Log to DB
    if "error" not in result:
        conn = get_connection()
        conn.execute(
            """INSERT INTO messages (group_id, sender, content, direction, ai_generated)
               VALUES (?, 'owner_ai', ?, 'outgoing', 1)""",
            (group_id, message)
        )
        conn.commit()
        conn.close()

    return result


# ─────────────────────────────────────────────────────────────────────────────
# GET GROUPS FROM BRIDGE
# ─────────────────────────────────────────────────────────────────────────────

def fetch_groups_from_bridge() -> list:
    """Fetch all WhatsApp groups from Node.js bridge."""
    result = _get(f"{BRIDGE_URL}/groups")
    if "error" in result:
        return []
    return result.get("groups", [])


# ─────────────────────────────────────────────────────────────────────────────
# SYNC GROUPS INTO DB
# ─────────────────────────────────────────────────────────────────────────────

def sync_groups() -> list:
    """Fetch groups from WhatsApp and upsert them into the database."""
    groups = fetch_groups_from_bridge()
    conn = get_connection()

    for g in groups:
        conn.execute("""
            INSERT INTO groups (group_id, name)
            VALUES (?, ?)
            ON CONFLICT(group_id) DO UPDATE SET name = excluded.name
        """, (g["id"], g["name"]))

    conn.commit()

    all_groups = conn.execute("SELECT * FROM groups ORDER BY name").fetchall()
    conn.close()

    return [dict(g) for g in all_groups]


# ─────────────────────────────────────────────────────────────────────────────
# BRIDGE STATUS
# ─────────────────────────────────────────────────────────────────────────────

def get_bridge_status() -> dict:
    """Check if WhatsApp bridge is connected."""
    result = _get(f"{BRIDGE_URL}/status")
    if "error" in result:
        return {"connected": False, "error": result["error"]}
    return result
