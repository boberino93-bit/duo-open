const DEFAULTS = {
  controlUrl: "https://raw.githubusercontent.com/boberino93-bit/duo-open/main/DuoOpen-AgentBus/control/chat_actuation/v1/ACTUATION_INDEX.json",
  projectUrl: "https://chatgpt.com/",
  enabled: false,
  pollMinutes: 1
};
const CAP = 19;
const ID_RE = /^[A-Za-z0-9._:-]+$/;
const CONTROL_PREFIX = "https://raw.githubusercontent.com/boberino93-bit/duo-open/";

async function cfg() {
  return {...DEFAULTS, ...(await chrome.storage.sync.get(DEFAULTS))};
}

function validEntry(e) {
  if (!e || typeof e !== "object") return false;
  const keys = Object.keys(e).sort().join(",");
  if (keys !== ["desired_state","generation","role","round_id","ticket_id"].sort().join(",")) return false;
  return typeof e.round_id === "string" && e.round_id.length > 0 && e.round_id.length <= 160 && ID_RE.test(e.round_id) &&
    typeof e.ticket_id === "string" && e.ticket_id.length > 0 && e.ticket_id.length <= 160 && ID_RE.test(e.ticket_id) &&
    ["MANAGER_REVIEWER","RESEARCH"].includes(e.role) &&
    Number.isInteger(e.generation) && e.generation >= 1 &&
    ["RUNNING","STOPPED"].includes(e.desired_state);
}

function validateIndex(d) {
  if (!d || d.schema !== "duoopen-chat-actuation-index/v1" || d.project !== "duo-open" ||
      d.source_repo !== "boberino93-bit/duo-open" || d.source_branch !== "main" || !Array.isArray(d.entries)) return false;
  if (!Number.isInteger(d.max_managed_child_tabs) || d.max_managed_child_tabs < 1 || d.max_managed_child_tabs > CAP) return false;
  if (d.entries.length > d.max_managed_child_tabs) return false;
  const seen = new Set();
  for (const e of d.entries) {
    if (!validEntry(e) || seen.has(e.ticket_id)) return false;
    seen.add(e.ticket_id);
  }
  return true;
}

function withSpawnParams(base, e) {
  const u = new URL(base || "https://chatgpt.com/");
  if (u.origin !== "https://chatgpt.com") throw new Error("projectUrl must be chatgpt.com");
  u.searchParams.set("duo_spawn", "1");
  u.searchParams.set("duo_round", e.round_id);
  u.searchParams.set("duo_ticket", e.ticket_id);
  u.searchParams.set("duo_role", e.role);
  u.searchParams.set("duo_generation", String(e.generation));
  return u.toString();
}


function validDomCommand(d) {
  if (!d || d.schema !== "duoopen-browser-actuation-command/v1" || d.issued_by !== "primary") return false;
  if (!ID_RE.test(d.command_id || "") || d.command_id.length > 160) return false;
  if (!Number.isInteger(d.max_managed_child_tabs) || d.max_managed_child_tabs < 1 || d.max_managed_child_tabs > CAP) return false;
  if (!Array.isArray(d.entries) || d.entries.length > d.max_managed_child_tabs) return false;
  const seen = new Set();
  for (const e of d.entries) {
    if (!validEntry(e) || seen.has(e.ticket_id)) return false;
    seen.add(e.ticket_id);
  }
  return Object.keys(d).sort().join(",") === ["schema","command_id","issued_by","max_managed_child_tabs","entries"].sort().join(",");
}

async function reconcileEntries(entries, cap, projectUrl) {
  const m = await mappings();
  const desired = new Map(entries.map(e => [e.ticket_id, e]));
  for (const ticket of Object.keys(m)) {
    const e = desired.get(ticket);
    if (!e || e.desired_state === "STOPPED" || e.generation !== m[ticket].generation) await closeMapped(m, ticket);
  }
  let managed = Object.keys(m).length;
  for (const e of entries) {
    if (e.desired_state !== "RUNNING" || m[e.ticket_id]) continue;
    if (managed >= Math.min(cap, CAP)) break;
    const url = withSpawnParams(projectUrl, e);
    const tab = await chrome.tabs.create({url, active:false});
    m[e.ticket_id] = {tabId:tab.id, generation:e.generation, round_id:e.round_id, role:e.role, state:"HOST_TAB_OPENED", openedAt:Date.now()};
    managed++;
  }
  await saveMappings(m);
}

async function applyDomCommand(d) {
  if (!validDomCommand(d)) throw new Error("invalid DOM actuation command");
  const c = await cfg();
  if (!c.enabled) return;
  const seen = (await chrome.storage.local.get({seenCommands:[]})).seenCommands;
  if (seen.includes(d.command_id)) return;
  await reconcileEntries(d.entries, d.max_managed_child_tabs, c.projectUrl);
  const next = [...seen.slice(-99), d.command_id];
  await chrome.storage.local.set({seenCommands:next, lastDomCommand:d.command_id, lastDomCommandAt:Date.now()});
}

async function mappings() {
  return (await chrome.storage.local.get({ticketTabs:{}})).ticketTabs;
}
async function saveMappings(m) { await chrome.storage.local.set({ticketTabs:m}); }

async function closeMapped(m, ticket) {
  const cur = m[ticket];
  if (!cur) return;
  try { await chrome.tabs.remove(cur.tabId); } catch (_) {}
  delete m[ticket];
}

async function reconcile() {
  const c = await cfg();
  if (!c.enabled) return;
  let d;
  try {
    if (!c.controlUrl.startsWith(CONTROL_PREFIX)) throw new Error("controlUrl must stay inside boberino93-bit/duo-open");
    const r = await fetch(c.controlUrl, {cache:"no-store"});
    if (!r.ok) throw new Error(`control HTTP ${r.status}`);
    d = await r.json();
  } catch (err) {
    await chrome.storage.local.set({lastError:String(err), lastPollAt:Date.now()});
    return;
  }
  if (!validateIndex(d)) {
    await chrome.storage.local.set({lastError:"invalid actuation index", lastPollAt:Date.now()});
    return;
  }

  try { await reconcileEntries(d.entries, d.max_managed_child_tabs, c.projectUrl); }
  catch (err) { await chrome.storage.local.set({lastError:String(err), lastPollAt:Date.now()}); return; }
  await chrome.storage.local.set({lastError:null, lastPollAt:Date.now(), lastIndexGeneration:d.generation});
}

chrome.runtime.onMessage.addListener((msg, sender) => {
  if (!msg || !sender.tab?.id) return;
  (async () => {
    if (msg.type === "DUO_ACTUATOR_OBSERVATION") {
      const m = await mappings();
      const t = msg.ticket_id;
      const cur = m[t];
      if (cur && cur.tabId === sender.tab.id) {
        cur.state = msg.state;
        cur.observedUrl = msg.url || sender.tab.url || null;
        cur.updatedAt = Date.now();
        await saveMappings(m);
      }
      return;
    }
    if (msg.type === "DUO_DOM_COMMAND") {
      const {controllerUrl=null} = await chrome.storage.local.get({controllerUrl:null});
      const su = new URL(sender.tab.url || "https://invalid/");
      const m = su.pathname.match(/\/c\/([A-Za-z0-9-]+)/);
      const senderKey = m ? `https://chatgpt.com/c/${m[1]}` : null;
      if (!controllerUrl || senderKey !== controllerUrl) return;
      await applyDomCommand(msg.command);
    }
  })();
});

chrome.runtime.onInstalled.addListener(async () => {
  await chrome.alarms.create("duo-reconcile", {periodInMinutes:1});
  await reconcile();
});
chrome.runtime.onStartup.addListener(reconcile);
chrome.alarms.onAlarm.addListener(a => { if (a.name === "duo-reconcile") reconcile(); });
