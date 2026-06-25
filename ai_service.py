"""
services/ai_service.py
=======================
Reply generation pipeline — priority order:

  1. knowledge_base.lookup(message)   →  instant answer from training data
  2. _generate_groq_reply()           →  LLM with full KB as context
  3. _generate_fallback_reply()       →  offline rule-based (Groq down / 429)

Flow diagram:
  incoming message
       │
       ▼
  ┌─────────────────────────┐
  │  knowledge_base.lookup  │  ← searches training/data.xlsx + training/bsnl_notes.txt
  └─────────────────────────┘
       │ found?
    yes│                no
       ▼                 ▼
  return answer    Groq available?
  (no API call)     yes│      no
                       ▼       ▼
                  Groq LLM   fallback
                  (KB as      rules
                  context)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
from database.schema import get_connection
from services.knowledge_base import lookup as kb_lookup, get_full_kb_text, load as kb_load

# Load knowledge base into memory on import
kb_load()

# ── Groq setup ────────────────────────────────────────────────────────────────
GROQ_AVAILABLE = False
_groq_client   = None

try:
    from groq import Groq
    _api_key = os.getenv("GROQ_API_KEY", "")
    if _api_key:
        _groq_client   = Groq(api_key=_api_key)
        GROQ_AVAILABLE = True
        print("[AI] ✅ Groq ready (llama-3.3-70b-versatile)")
    else:
        print("[AI] ⚠️  No GROQ_API_KEY — using KB lookup + fallback replies")
except Exception as e:
    print(f"[AI] Groq not available: {e}")

URGENT_KEYWORDS = [
    "emergency","urgent","asap","immediately","critical","help",
    "accident","fire","hospital","death","died","blood","ambulance",
    "police","attack","danger","sos","please call","call me",
]
IMPORTANT_KEYWORDS = [
    "meeting","deadline","important","must","required","confirm",
    "payment","due","tomorrow","today","approval","decision",
]


def detect_urgency(message: str) -> dict:
    text  = message.lower()
    score = sum(3 for kw in URGENT_KEYWORDS if kw in text)
    score += sum(1 for kw in IMPORTANT_KEYWORDS if kw in text)
    if score >= 6:   level = "urgent"
    elif score >= 2: level = "important"
    else:            level = "normal"
    return {"level": level, "score": score}


def learn_style(group_id: str) -> dict:
    conn = get_connection()
    rows = conn.execute(
        "SELECT message FROM style_samples WHERE group_id=? AND is_owner=1 "
        "ORDER BY created_at DESC LIMIT 100", (group_id,)
    ).fetchall()
    if not rows:
        conn.close()
        return {"status": "no_samples"}
    messages   = [r["message"] for r in rows]
    avg_length = sum(len(m.split()) for m in messages) // len(messages)
    text_lower = " ".join(messages).lower()
    casual = sum(1 for w in ["lol","haha","ok","yeah","hey"] if w in text_lower)
    formal = sum(1 for w in ["please","kindly","regards","thank you"] if w in text_lower)
    tone   = "casual" if casual >= formal else "professional"
    conn.execute(
        "INSERT OR REPLACE INTO ai_profiles "
        "(group_id, tone, avg_msg_length, sample_count) VALUES (?,?,?,?)",
        (group_id, tone, avg_length, len(messages))
    )
    conn.commit()
    conn.close()
    return {"status": "learned", "tone": tone, "avg_length": avg_length}


def get_style_profile(group_id: str) -> dict:
    try:
        conn    = get_connection()
        profile = conn.execute(
            "SELECT * FROM ai_profiles WHERE group_id=?", (group_id,)
        ).fetchone()
        if not profile:
            profile = conn.execute(
                "SELECT * FROM ai_profiles WHERE style_data IS NOT NULL LIMIT 1"
            ).fetchone()
        conn.close()
        if not profile: return {}
        result = dict(profile)
        if result.get("style_data"):
            try: result.update(json.loads(result["style_data"]))
            except: pass
        return result
    except:
        return {}


def get_style_samples(group_id: str, limit: int = 8) -> list:
    try:
        conn    = get_connection()
        samples = conn.execute(
            "SELECT message FROM style_samples "
            "WHERE group_id=? AND is_owner=1 ORDER BY RANDOM() LIMIT ?",
            (group_id, limit)
        ).fetchall()
        if len(samples) < 3:
            samples = conn.execute(
                "SELECT message FROM style_samples "
                "WHERE is_owner=1 ORDER BY RANDOM() LIMIT ?", (limit,)
            ).fetchall()
        conn.close()
        return [r["message"] for r in samples]
    except:
        return []


def get_db_knowledge() -> str:
    """Extra knowledge added via admin panel."""
    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT category, title, content FROM knowledge "
            "ORDER BY created_at DESC LIMIT 30"
        ).fetchall()
        conn.close()
        if not rows: return ""
        return "\n".join(f"Q: {r['title']}\nA: {r['content']}" for r in rows)
    except:
        return ""


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def generate_reply(message: str, group_id: str, group_name: str, mode: str) -> dict:
    """
    Priority:
      1. KB lookup  (training data — no API call)
      2. Groq LLM   (if API available)
      3. Fallback   (offline rules)
    """
    # ── Step 1: Knowledge base lookup ─────────────────────────────────────────
    kb_answer = kb_lookup(message)
    if kb_answer:
        print(f"[KB] ✅ Answered from training data: {message[:50]}")
        return {"reply": kb_answer, "needs_approval": False, "source": "kb"}

    # ── Step 2: Groq LLM ──────────────────────────────────────────────────────
    if GROQ_AVAILABLE and _groq_client:
        reply = _generate_groq_reply(message, group_id, group_name, mode)
    else:
        reply = _generate_fallback_reply(message, mode)

    return {"reply": reply, "needs_approval": False, "source": "groq" if GROQ_AVAILABLE else "fallback"}


# ═══════════════════════════════════════════════════════════════════════════════
# GROQ REPLY
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_groq_reply(message: str, group_id: str, group_name: str, mode: str) -> str:
    profile         = get_style_profile(group_id)
    style_samples   = get_style_samples(group_id)
    db_knowledge    = get_db_knowledge()

    tone            = profile.get("tone", mode)
    avg_words       = profile.get("avg_words", profile.get("avg_msg_length", 10))
    emoji_ratio     = profile.get("emoji_ratio", 0)
    common_emojis   = profile.get("common_emojis", [])
    lowercase_ratio = profile.get("lowercase_ratio", 0)

    style_notes = []
    if emoji_ratio > 0.5:
        style_notes.append(f"Uses emojis a lot. Favourites: {' '.join(common_emojis[:3])}")
    elif emoji_ratio > 0.2:
        style_notes.append(f"Uses emojis sometimes: {' '.join(common_emojis[:2])}")
    else:
        style_notes.append("Rarely uses emojis")
    if lowercase_ratio > 0.7:
        style_notes.append("Writes mostly in lowercase")
    if avg_words <= 5:
        style_notes.append("Very short replies, 1-5 words")
    elif avg_words <= 10:
        style_notes.append("Short replies, under 10 words")

    samples_text = ""
    if style_samples:
        samples_text = "\nReal examples of how this person writes:\n"
        samples_text += "\n".join(f'- "{s}"' for s in style_samples[:8])
        samples_text += "\nMatch this exact style.\n"

    # Full KB from training files + any DB additions
    full_knowledge = get_full_kb_text()
    if db_knowledge:
        full_knowledge += "\n\nAdditional knowledge:\n" + db_knowledge

    system_prompt = f"""You are a BSNL TR069 technical expert replying to WhatsApp messages in the group "{group_name}".

Writing style:
{chr(10).join(f'- {n}' for n in style_notes)}
{samples_text}
BSNL / TR069 Knowledge Base (use ONLY this for technical answers):
{full_knowledge}

Rules:
- For ANY technical question about TR069, ACS, ONT, MAC, LDAP, Bridle, DSCM, FMS, BNG, WCT — give the EXACT answer from the knowledge base above.
- Do NOT say "let me check" or "I'll get back to you" for technical questions.
- Reply exactly like a real human expert on WhatsApp — direct, helpful, no fluff.
- For casual/greeting messages reply casually and short.
- Never say you are an AI. Your name is "BSNL Assistant".
- Reply in the SAME LANGUAGE as the message (Malayalam, English, Hinglish, etc.)
- Output the reply text only, nothing else."""

    try:
        response = _groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": message},
            ],
            max_tokens=300,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip().strip('"')
    except Exception as e:
        print(f"[AI] Groq error: {e}")
        return _generate_fallback_reply(message, mode)


# ═══════════════════════════════════════════════════════════════════════════════
# OFFLINE FALLBACK  (Groq unavailable / 429 rate limit)
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_fallback_reply(message: str, mode: str) -> str:
    """
    Pure offline rule-based replies.
    Technical queries → checked against KB again (broader match).
    Casual queries → pattern match.
    """
    text = message.lower().strip()

    # ── Technical — broad keyword check ───────────────────────────────────────
    # These are last-resort strings if KB lookup somehow missed them

    if "bbm" in text and ("map" in text or "exchange" in text or "mapping" in text):
        return "Go to Tools → BBM Exchange Mapping menu and map all unmapped exchanges to concerned BBM codes."

    if "alphion" in text or "aphion" in text or "optivision" in text:
        return ("For Alphion ONTs, only models 1143 and 1443 will get validated. "
                "Firmware update is also required for these models to report to ACS.")

    if "voip" in text or "voice over ip" in text:
        return "VoIP can be configured through NOC user only. Bridle the CPE (click B), then Edit → Service tab."

    if "no inform" in text or "not reporting" in text or "no report" in text:
        return ("Try secondary ACS URL: http://acskl.bsnl.in (no port number). "
                "Also check internet is UP and TR069 WAN = TR069_INTERNET.")

    if "upload no ack" in text or "no ack" in text:
        return ("Change ACS URL to http://acskl.bsnl.in (without port number). "
                "Usually caused by port 7547 blocking in BNG.")

    if "duplicate mac" in text or "mac duplicate" in text:
        return "Duplicate MAC — change the ONT and retry."

    if "invalid mac" in text or "mac invalid" in text or "unauthorized mac" in text:
        return ("Only BBNW approved MAC series are validated. "
                "Check Bridle → Help → Approved MAC (BBNW).")

    if "no open order" in text or "open order" in text:
        return "Different user IDs in LDAP and FMS. Both must match — correct the user IDs."

    if "ldap" in text or "susp" in text:
        return ("Check LDAP status — if SUSP or Unauthorized, internet won't work and "
                "TR069 won't report. Contact BA NOC team to fix LDAP status.")

    if "order not yet accepted" in text or "order not accepted" in text:
        return ("WCT error: order is closed, not accepted, or user ID is wrong. "
                "Verify order is open, accepted, and user ID is correct. If still failing, escalate to ITPC.")

    if "fms" in text or "dscm" in text:
        return ("Configure TR069 in ONT, let it report to ACS. "
                "Approved MAC validated automatically — then proceed with order.")

    if "waiting for mac" in text or "mac validation" in text:
        return ("Check if _sid/_nid_/_eid/_wid suffix is present in username. "
                "WCT server may be slow — check again after some time.")

    if "bridle" in text and ("url" in text or "address" in text or "site" in text):
        return ("Bridle site: https://bridle.bsnl.in/bridle/ (internet) | "
                "LAN: http://10.201.217.69/bridle/ or http://10.44.17.171/bridle/")

    if "acs url" in text or "acs address" in text or "acs server" in text:
        return "Primary ACS: http://acs.bsnl.in:7547 | Secondary: http://acskl.bsnl.in:7547"

    if "bridling" in text or "bridle button" in text:
        return ("Bridling sets inform interval to 30s. BNG must allow port 7547 traffic "
                "to/from 218.248.6.242 & 117.216.41.50 (both in+out). "
                "Once allowed, bridling happens within a minute.")

    if "reverif" in text:
        return "If ONT is currently reporting, trigger reverification from Bridle portal → Tools → Verification Assistant."

    if "43200" in text:
        return "Inform interval 43200 is the ONT default — it has NOT yet reported to ACS."
    if "28800" in text:
        return "Check reporting in Bridle. If not reported, change inform interval from 28800 to 30 and reboot ONT."
    if "36000" in text:
        return "ONT doesn't have standard TR069 parameters — server set interval to 36000. Try firmware upgrade or contact vendor."

    if "tr069_internet" in text or "wan connection" in text or "no tr069 wan" in text:
        return "Configure WAN page: set internet service mode as TR069_INTERNET."

    if "domain name resolution" in text or "dns failed" in text:
        return "Check DNS configured in ONT. All public and BSNL DNS should resolve the ACS URL."

    if "ipv6" in text or "dual stack" in text:
        return "IPV6/dual stack issues: raise docket to BBNW NOC in Zsmart. IPv6 requires MTU 1492."

    if "ba list" in text or "whole ba" in text:
        return "Contact your NOC team — NOC users can access the whole BA list."

    if "online ratio" in text or "ftth online" in text:
        return "Check in Bridle site → Reports → Online Status."

    if "cwmp" in text or "tr069 daemon" in text:
        return "Enable TR069 Daemon and Enable CWMP Parameter in ONT settings."

    if "verified" in text and "dscm" in text:
        return "Close the order on the same day of verification. If not done same day, reverify before closing."

    if "vlan" in text and "mac" in text:
        return "Reverify the user ID with the correct VLAN and connected MAC."

    if "quota" in text or "56kbps" in text or "1gb" in text:
        return ("Complete ACS before customer starts browsing. FTTH orders run at 5Mbps up to 1GB, "
                "then drop to 56Kbps — ACS won't report at 56Kbps.")

    if "serial number" in text or "fs230817" in text:
        return "Invalid serial number in ONT. Try firmware upgrade. If serial doesn't change after upgrade, replace the ONT."

    if "b button" in text and "not" in text:
        return ("B button (Bridle/Edit) is only available for ONTs that report all standard paths. "
                "Check ONT make/model against Bridle supported models list. Firmware update may help.")

    # Generic technical catch-all
    if any(w in text for w in ["tr069", "tr-069", "acs", "ont", "bridle", "bng",
                                "dscm", "fms", "ldap", "bbnw", "ftth", "inform"]):
        return ("Check Bridle portal → Tools → Verification Assistant first. "
                "Share screenshots of Device Info, WAN Status, TR069 Status pages when escalating. "
                "Primary ACS: http://acs.bsnl.in:7547 | Secondary: http://acskl.bsnl.in:7547")

    # ── Casual / greeting patterns ─────────────────────────────────────────────
    if any(w in text for w in ["what is your name","your name","who are you"]):
        return "I'm BSNL Assistant 🤖"
    if any(w in text for w in ["how are you","how r u","hru","sukhamano"]):
        return "I'm good! What's up? 😊"
    if any(w in text for w in ["good morning","gm","morning","mornin"]):
        return "Good morning! ☀️😊"
    if any(w in text for w in ["good night","gn","good nite","nite","night"]):
        return "Good night! 🌙 Sleep well!"
    if any(w in text for w in ["good evening","evening","good afternoon","afternoon"]):
        return "Good evening! 😊"
    if any(w in text for w in ["hello","hi","hey","hii","hai","hy"]):
        return "Hey! 👋😊"
    if any(w in text for w in ["thank","thanks","thx","ty","tq","thanku"]):
        return "No problem! 😊 Anytime!"
    if any(w in text for w in ["haha","lol","lmao","hehe","😂"]):
        return "😂😂 ikr!"
    if any(w in text for w in ["okay","ok","okie","fine","sure","alright","noted","👍"]):
        return "👍"
    if any(w in text for w in ["bye","byee","goodbye","cya","see you","poga"]):
        return "Bye! 👋😊 Take care!"
    if any(w in text for w in ["bro","da","dei","mone","macha","machan"]):
        return "Yes bro? 😄"
    if any(w in text for w in ["nice","cool","awesome","great","superb"]):
        return "Thanks! 😊"
    if "hungry" in text or "food" in text or "eat" in text:
        return "Same! 😋 What are you having?"
    if "bored" in text or "boring" in text:
        return "Same here 😴 do something fun!"
    if "😭" in text or "sad" in text:
        return "Aww what happened? 🥺"
    if "🔥" in text or "fire" in text:
        return "🔥🔥"
    if "how to" in text or "how do" in text:
        return "Check Bridle portal → Tools → Verification Assistant 👍"

    return "Ok 👍"
