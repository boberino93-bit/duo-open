(() => {
  const ID_RE = /^[A-Za-z0-9._:-]+$/;

  function decodeBase64Url(token) {
    const s = token.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((token.length + 3) % 4);
    return decodeURIComponent(escape(atob(s)));
  }

  function validEntry(e) {
    return e && typeof e === "object" &&
      Object.keys(e).sort().join(",") === ["round_id","ticket_id","role","generation","desired_state"].sort().join(",") &&
      ID_RE.test(e.round_id || "") && e.round_id.length <= 160 &&
      ID_RE.test(e.ticket_id || "") && e.ticket_id.length <= 160 &&
      ["MANAGER_REVIEWER","RESEARCH"].includes(e.role) &&
      Number.isInteger(e.generation) && e.generation >= 1 &&
      ["RUNNING","STOPPED"].includes(e.desired_state);
  }

  function validCommand(d) {
    if (!d || typeof d !== "object") return false;
    if (Object.keys(d).sort().join(",") !== ["schema","command_id","issued_by","max_managed_child_tabs","entries"].sort().join(",")) return false;
    if (d.schema !== "duoopen-browser-actuation-command/v1" || d.issued_by !== "primary" || !ID_RE.test(d.command_id || "") || d.command_id.length > 160) return false;
    if (!Number.isInteger(d.max_managed_child_tabs) || d.max_managed_child_tabs < 1 || d.max_managed_child_tabs > 19 || !Array.isArray(d.entries) || d.entries.length > d.max_managed_child_tabs) return false;
    const seen = new Set();
    for (const e of d.entries) { if (!validEntry(e) || seen.has(e.ticket_id)) return false; seen.add(e.ticket_id); }
    return true;
  }

  // Controller bridge: only background accepts this command if this exact conversation is armed.
  function scanAssistantCommands(root=document) {
    const nodes = root.querySelectorAll?.('[data-message-author-role="assistant"]') || [];
    for (const n of nodes) {
      const text = n.textContent || "";
      const re = /DUO_ACTUATOR_V1:([A-Za-z0-9_-]+):END/g;
      for (const match of text.matchAll(re)) {
        try {
          const d = JSON.parse(decodeBase64Url(match[1]));
          if (validCommand(d)) chrome.runtime.sendMessage({type:"DUO_DOM_COMMAND", command:d});
        } catch (_) {}
      }
    }
  }
  scanAssistantCommands();
  const observer = new MutationObserver(() => scanAssistantCommands());
  observer.observe(document.documentElement, {subtree:true, childList:true, characterData:true});

  // Child bootstrap path.
  const u = new URL(location.href);
  if (u.searchParams.get("duo_spawn") !== "1") return;
  const round = u.searchParams.get("duo_round") || "";
  const ticket = u.searchParams.get("duo_ticket") || "";
  const role = u.searchParams.get("duo_role") || "";
  const gen = Number(u.searchParams.get("duo_generation") || "0");
  if (!ID_RE.test(round) || !ID_RE.test(ticket) || !["MANAGER_REVIEWER","RESEARCH"].includes(role) || !Number.isInteger(gen) || gen < 1) return;

  const onceKey = `duoSpawnSubmitted:${ticket}:${gen}`;
  const prompt = `You are a Duo Open ${role} agent joining an existing round.\n\n` +
    `Bootstrap from /DuoOpen-AgentBus/JOIN_ROUND.md. Claim exactly ticket ${ticket} in round ${round}. ` +
    `Validate the ticket and current round before substantive work. Publish your own SESSION_STARTED only after the claim is valid. ` +
    `If the ticket cannot be validly claimed, publish/report SPAWN_REJECTED or the blocking evidence and do not improvise another assignment.\n\n` +
    `Use the local AgentBus/Artifactory as durable coordination truth and GitHub main as production truth. ` +
    `Follow current role authority, service interval, regression continuity, and human-isolation rules.`;

  function obs(state) { chrome.runtime.sendMessage({type:"DUO_ACTUATOR_OBSERVATION", ticket_id:ticket, state, url:location.href}); }
  function composer() {
    return document.querySelector('[data-testid="prompt-textarea"]') || document.querySelector('textarea') ||
      document.querySelector('[contenteditable="true"][role="textbox"]') || document.querySelector('[contenteditable="true"]');
  }
  function insert(el, text) {
    el.focus();
    if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) {
      const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value')?.set;
      setter ? setter.call(el, text) : (el.value = text);
      el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true}));
    } else {
      el.textContent = ''; document.execCommand('insertText', false, text);
      el.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:text}));
    }
  }
  function send() {
    const btn = document.querySelector('button[data-testid="send-button"]') || [...document.querySelectorAll('button')].find(b => /send/i.test(b.getAttribute('aria-label') || ''));
    if (btn && !btn.disabled) { btn.click(); return true; }
    const el = composer();
    if (el) { el.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', code:'Enter', bubbles:true})); el.dispatchEvent(new KeyboardEvent('keyup', {key:'Enter', code:'Enter', bubbles:true})); return true; }
    return false;
  }
  if (sessionStorage.getItem(onceKey)) { obs("PROMPT_ALREADY_SUBMITTED"); return; }
  obs("HOST_PAGE_LOADED");
  const started = Date.now(); let newChatClicked = false;
  const timer = setInterval(() => {
    if (/\/c\/[a-zA-Z0-9-]+/.test(location.pathname)) obs("CONVERSATION_URL_OBSERVED");
    const el = composer();
    if (!el) {
      if (!newChatClicked && Date.now() - started > 3000) {
        const candidate = [...document.querySelectorAll("a,button")].find(x => /new chat/i.test((x.getAttribute("aria-label") || "") + " " + (x.textContent || "")));
        if (candidate) { candidate.click(); newChatClicked = true; obs("NEW_CHAT_CLICKED"); return; }
      }
      if (Date.now() - started > 30000) { clearInterval(timer); obs("COMPOSER_TIMEOUT"); }
      return;
    }
    insert(el, prompt);
    setTimeout(() => { if (send()) { sessionStorage.setItem(onceKey, "1"); obs("PROMPT_SUBMITTED"); clearInterval(timer); } }, 250);
  }, 500);
})();
