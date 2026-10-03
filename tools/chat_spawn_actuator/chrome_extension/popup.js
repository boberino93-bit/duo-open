function controllerKey(url) {
  const u = new URL(url);
  if (u.origin !== "https://chatgpt.com") return null;
  const m = u.pathname.match(/\/c\/([A-Za-z0-9-]+)/);
  return m ? `https://chatgpt.com/c/${m[1]}` : null;
}
async function refresh() {
  const {controllerUrl=null} = await chrome.storage.local.get({controllerUrl:null});
  s.textContent = controllerUrl ? `Armed: ${controllerUrl}` : "Not armed";
}
arm.onclick = async () => {
  const [tab] = await chrome.tabs.query({active:true,currentWindow:true});
  const key = controllerKey(tab.url || "");
  if (!key) { s.textContent = "Open the Primary ChatGPT conversation first."; return; }
  await chrome.storage.local.set({controllerUrl:key});
  await refresh();
};
disarm.onclick = async () => { await chrome.storage.local.remove("controllerUrl"); await refresh(); };
refresh();
