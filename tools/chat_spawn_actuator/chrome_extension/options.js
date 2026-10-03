const DEFAULTS = {
  controlUrl: "https://raw.githubusercontent.com/boberino93-bit/duo-open/main/DuoOpen-AgentBus/control/chat_actuation/v1/ACTUATION_INDEX.json",
  projectUrl: "https://chatgpt.com/",
  enabled: false
};
(async () => {
  const c = {...DEFAULTS, ...(await chrome.storage.sync.get(DEFAULTS))};
  enabled.checked = c.enabled; controlUrl.value = c.controlUrl; projectUrl.value = c.projectUrl;
})();
save.onclick = async () => {
  const p = new URL(projectUrl.value.trim());
  if (p.origin !== "https://chatgpt.com") { status.textContent = "Project URL must be chatgpt.com"; return; }
  const c = new URL(controlUrl.value.trim());
  if (!c.toString().startsWith("https://raw.githubusercontent.com/boberino93-bit/duo-open/")) { status.textContent = "Control URL must stay inside boberino93-bit/duo-open"; return; }
  await chrome.storage.sync.set({enabled:enabled.checked, controlUrl:c.toString(), projectUrl:p.toString()});
  status.textContent = "Saved";
};
