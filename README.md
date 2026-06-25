# BSNL TR069 WhatsApp AI Assistant
## Complete Setup & Run Guide

---

## FOLDER STRUCTURE

```
bsnl_assistant/
├── bridge/
│   ├── index.js          ← WhatsApp Node.js bridge
│   └── package.json
├── backend/
│   ├── app.py            ← Flask API server
│   ├── requirements.txt
│   ├── database/
│   │   └── schema.py
│   ├── routes/
│   │   ├── groups.py
│   │   ├── messages.py
│   │   └── dashboard.py
│   └── services/
│       ├── ai_service.py
│       └── whatsapp_service.py
└── frontend/
    ├── index.html        ← Open in browser (localhost:5500)
    ├── css/style.css
    └── js/
        ├── api.js
        └── app.js
```

---

## PREREQUISITES (install once)

```
Node.js 18+     →  https://nodejs.org
Python 3.10+    →  https://python.org
VS Code         →  with Live Server extension
```

---

## STEP 1 — TERMINAL 1 (WhatsApp Bridge)

```bash
cd bsnl_assistant/bridge
npm install
node index.js
```

👉 A QR code will appear. Scan it with YOUR WhatsApp (Settings → Linked Devices → Link a device).
👉 Keep this terminal running always.

---

## STEP 2 — TERMINAL 2 (Python Backend)

```bash
cd bsnl_assistant/backend
pip install -r requirements.txt
python app.py
```

👉 Backend runs at http://localhost:5000
👉 Keep this terminal running always.

---

## STEP 3 — BROWSER (Frontend)

Open `frontend/index.html` with VS Code Live Server → http://localhost:5500

OR run a simple server:

```bash
cd bsnl_assistant/frontend
npx serve .
```

Then open http://localhost:3000 (or whatever port it shows)

---

## FIRST TIME SETUP (in browser)

1. Enter your 10-digit WhatsApp number
2. Enter your name
3. Enter your Anthropic API key (from console.anthropic.com)
4. Click Continue
5. Go to **Groups** → Click **"Sync from WhatsApp"**
6. Select the groups you want AI to monitor (click "Select this group")
7. Enable AI toggle for each group
8. Choose: **Auto Reply** ON = AI sends instantly | OFF = AI asks your approval first

---

## HOW IT WORKS

```
Someone sends message in group
        ↓
WhatsApp Bridge (Terminal 1) catches it
        ↓
Sends to Flask Backend (Terminal 2)
        ↓
Backend checks: is this group selected?
        ↓
AI generates reply using:
  • BSNL TR069 knowledge base (built-in)
  • YOUR own message samples (learned from your past replies)
  • Custom knowledge you added
        ↓
Auto Reply ON  → sends immediately
Auto Reply OFF → shows in Approvals tab for you to review
```

---

## STYLE LEARNING

The AI automatically saves every message YOU send in selected groups as a style sample.
Over time it learns:
- Your tone (casual / professional)
- Your average reply length
- Whether you use emojis
- Malayalam/English mix
- Your common phrases and shortcuts

Go to **My Style** tab → click **Re-analyze** to update the profile.
You can also add sample messages manually in **My Style** tab.

---

## COMMON ISSUES

**QR not showing?**
→ Terminal 1: `node index.js` must be running

**Groups not loading?**
→ Scan QR first, then click Sync

**AI not replying?**
→ Check: group is Selected + AI toggle is ON + API key is correct

**"Backend offline" in browser?**
→ Terminal 2: `python app.py` must be running

**Style not learning?**
→ Reply some messages from your own WhatsApp in the group, then Re-analyze

---

## RESETTING SESSION

To log out and re-scan QR:

```bash
# In Terminal 1 directory (bridge/)
rm -rf .wwebjs_auth
node index.js
```