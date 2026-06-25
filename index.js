/**
 * whatsapp-bridge/index.js
 * Run: node index.js
 */

const express    = require("express");
const axios      = require("axios");
const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode     = require("qrcode-terminal");

const app         = express();
const PORT        = 3000;
const BACKEND_URL = "http://localhost:5000";

let currentWhatsApp = null;  // phone number string
let currentName     = null;  // display name

// ── CORS ──────────────────────────────────────────────────────────────────────
app.use((req, res, next) => {
  res.header("Access-Control-Allow-Origin",  "*");
  res.header("Access-Control-Allow-Headers", "Content-Type,Authorization");
  res.header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS");
  if (req.method === "OPTIONS") return res.sendStatus(204);
  next();
});

app.use(express.json());

// ── WhatsApp client ───────────────────────────────────────────────────────────
const client = new Client({
  authStrategy: new LocalAuth(),
  puppeteer: {
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  },
});

// ── Routes ────────────────────────────────────────────────────────────────────

app.get("/status", (req, res) => {
  res.json({
    connected: !!currentWhatsApp,
    number:    currentWhatsApp,
    name:      currentName,
  });
});

app.post("/send", async (req, res) => {
  const { group_id, groupId, message } = req.body;
  const gid = group_id || groupId;
  if (!gid || !message) {
    return res.status(400).json({ error: "group_id and message are required" });
  }
  try {
    await client.sendMessage(gid, message);
    res.json({ success: true });
  } catch (err) {
    console.error("❌ Send error:", err.message);
    res.status(500).json({ error: err.message });
  }
});

app.get("/groups", async (req, res) => {
  try {
    console.log("⏳ Loading groups safely...");
    const chats  = await client.getChats();
    const groups = chats
      .filter(c => c.isGroup)
      .map(c => ({ id: c.id._serialized, name: c.name }));
    console.log(`📋 Loaded ${groups.length} groups`);
    res.json(groups);
  } catch (err) {
    console.error("❌ Groups error:", err.message);
    res.status(500).json({ error: err.message });
  }
});

// ── Auto-sync groups to backend with owner_phone ──────────────────────────────
async function syncGroupsToBackend(phone) {
  try {
    console.log("⏳ Syncing groups to backend...");
    const chats  = await client.getChats();
    const groups = chats
      .filter(c => c.isGroup)
      .map(c => ({ id: c.id._serialized, name: c.name }));

    await axios.post(`${BACKEND_URL}/api/groups/sync`, {
      groups:      groups,
      owner_phone: phone,
    });

    console.log(`✅ Synced ${groups.length} groups to backend for ${phone}`);
  } catch (err) {
    console.error("❌ Failed to sync groups to backend:", err.message);
  }
}

// ── WhatsApp events ───────────────────────────────────────────────────────────

client.on("qr", qr => {
  console.log("📱 Scan QR code:");
  qrcode.generate(qr, { small: true });
});

client.on("ready", async () => {
  const info      = client.info;
  currentWhatsApp = info.wid.user;
  currentName     = info.pushname;

  console.log("==============================");
  console.log("✅ WhatsApp Connected!");
  console.log("Number :", currentWhatsApp);
  console.log("Name   :", currentName);
  console.log("==============================");

  // Auto-sync this user's groups to backend immediately on connect
  await syncGroupsToBackend(currentWhatsApp);
});

client.on("disconnected", reason => {
  console.log("⚠️ WhatsApp disconnected:", reason);
  currentWhatsApp = null;
  currentName     = null;
});

// ── Receive message ───────────────────────────────────────────────────────────

client.on("message", async msg => {
  try {
    if (!msg.from.endsWith("@g.us")) return;
    if (msg.fromMe) return;
    if (!msg.body) return;

    const chat = await msg.getChat();

    console.log(`📨 [${chat.name}] ${msg.body}`);

    const payload = {
      group_id:        msg.from,
      group_name:      chat.name,
      sender:          msg.author || msg.from,
      message:         msg.body,
      content:         msg.body,
      whatsapp_number: currentWhatsApp,   // ← owner phone always sent
    };

    const response = await axios.post(
      `${BACKEND_URL}/webhook`,
      payload,
      { timeout: 120000 }
    );

    if (response.data && response.data.reply) {
      await client.sendMessage(msg.from, response.data.reply);
      console.log("✅ AI Reply Sent:", response.data.reply);
    } else {
      console.log("⚠️ No reply - status:", response.data && response.data.status);
    }

  } catch (err) {
    if (err.response) {
      console.log("❌ Backend error:", err.response.status, JSON.stringify(err.response.data));
    } else {
      console.log("❌ Error:", err.message);
    }
  }
});

// ── Start ─────────────────────────────────────────────────────────────────────

app.listen(PORT, () => {
  console.log(`🌐 WhatsApp Bridge running → http://localhost:${PORT}`);
  console.log(`Forwarding to backend → ${BACKEND_URL}`);
});

console.log("⏳ Starting WhatsApp client...");
client.initialize();