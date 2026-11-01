const blank_status = document.getElementById("status");
async function blank_refresh() {
  try {
    const result = await chrome.runtime.sendMessage({type: "blank_settings"});
    if (result?.error) throw Error(result.error);
    const sites = document.getElementById("sites"); sites.replaceChildren();
    for (const site of result.sites) {
      const item = document.createElement("li"); item.textContent = site; sites.append(item);
    }
    if (!result.sites.length) {
      const item = document.createElement("li"); item.textContent = "None — manual scans are ready."; sites.append(item);
    }
    blank_status.textContent = result.detector_mode === "unavailable" ? "Local detector unavailable. Reload BLANK and retry." :
      `Ready on this device · ${result.detector_mode} · ${result.model_version || "ML unavailable; rules only"}`;
  } catch { blank_status.textContent = "Local detector unavailable. Reload BLANK and retry."; }
}
document.getElementById("test").onclick = async () => {
  try {
    const result = await chrome.runtime.sendMessage({type: "blank_check_detector"});
    if (result?.error) throw Error(result.error);
    blank_status.textContent = `Local detector working · ${result.detector_mode} · ${result.model_version || "ML unavailable; rules only"}`;
  } catch { blank_status.textContent = "Local detector unavailable. Reload BLANK and retry."; }
};
document.getElementById("pause").onclick = async () => {
  try {
    const result = await chrome.runtime.sendMessage({type: "blank_pause_all"});
    if (result?.error) throw Error(result.error);
    await blank_refresh();
  } catch { blank_status.textContent = "Could not change automatic scanning. Retry or revoke access in browser settings."; }
};
blank_refresh();

const blank_cloud_config_status=document.getElementById('cloud-config-status');
async function blank_refresh_cloud() {
  const result=await chrome.runtime.sendMessage({type:'blank_cloud_settings'});
  document.getElementById('provider').value=result.provider;
  blank_cloud_config_status.textContent=result.configured[result.provider] ?
    `${result.provider} key configured for this browser session. Provider authentication is checked on your next request.` :
    'No key configured for the selected provider. Local scans are ready.';
}
document.getElementById('cloud-key-form').onsubmit=async event=>{
  event.preventDefault();
  const button=document.getElementById('cloud-connect'), input=document.getElementById('cloud-key');
  const provider=document.getElementById('provider').value;
  const origin=provider==='groq'?'https://api.groq.com/*':'https://generativelanguage.googleapis.com/*';
  button.disabled=true;
  try {
    if(!await chrome.permissions.request({origins:[origin]})) throw Error('Provider access was declined.');
    const result=await chrome.runtime.sendMessage({type:'blank_cloud_configure',provider,key:input.value});
    if(result.error) throw Error(result.error);
    await blank_refresh_cloud();
  } catch(error) {blank_cloud_config_status.textContent=error.message;}
  finally {input.value='';button.disabled=false;}
};
document.getElementById('cloud-forget').onclick=async()=>{
  await chrome.runtime.sendMessage({type:'blank_cloud_forget'});
  document.getElementById('cloud-key').value='';
  await blank_refresh_cloud();
};
document.getElementById('provider').onchange=()=>{
  document.getElementById('cloud-key').value='';
  blank_cloud_config_status.textContent='Enter and save a key to select this provider. No request has been sent.';
};
blank_refresh_cloud().catch(()=>{blank_cloud_config_status.textContent='Cloud settings unavailable. Local scans remain available.';});

const blank_semantic_toggle=document.getElementById('semantic-toggle');
const blank_semantic_status=document.getElementById('semantic-status');
if(blank_semantic_toggle) {
  chrome.storage.local.get(['blank_semantic_enabled']).then(res => {
    blank_semantic_toggle.checked = Boolean(res.blank_semantic_enabled);
    if(blank_semantic_status) blank_semantic_status.textContent = res.blank_semantic_enabled ?
      'Experimental local semantic AI active (runs offline via packaged ONNX WebAssembly).' :
      'Experimental semantic AI is off (rules and baseline TF-IDF active).';
  }).catch(()=>{});
  blank_semantic_toggle.onchange = async () => {
    await chrome.storage.local.set({blank_semantic_enabled: blank_semantic_toggle.checked});
    if(blank_semantic_status) blank_semantic_status.textContent = blank_semantic_toggle.checked ?
      'Experimental local semantic AI active (runs offline via packaged ONNX WebAssembly).' :
      'Experimental semantic AI is off (rules and baseline TF-IDF active).';
  };
}
