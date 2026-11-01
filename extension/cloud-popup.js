let blank_cloud_preview = null;
const blank_cloud_status = document.getElementById("cloud-status");
const blank_cloud_key_status = document.getElementById("popup-cloud-key-status");
const blank_cloud_key_input = document.getElementById("popup-cloud-key");
const blank_cloud_provider = document.getElementById("popup-cloud-provider");
const blank_cloud_clear_btn = document.getElementById("popup-cloud-clear");
const blank_cloud_connected_badge = document.getElementById("cloud-connected-badge");
const blank_cloud_connected_name = document.getElementById("cloud-connected-name");
const blank_cloud_input_group = document.getElementById("cloud-input-group");

const blank_cloud_messages = {
  key_required: "Add your own provider key in Settings to use cloud AI. Local scans remain ready.",
  permission_required: "Grant provider access in Settings.",
  authentication_error: "Provider rejected this key. Update it in Settings.",
  permission_error: "The provider account does not allow this request.",
  quota_exceeded: "Provider quota reached. Wait before retrying; local scans still work.",
  timeout: "Cloud analysis timed out.",
  cancelled: "Cloud request cancelled or page changed.",
  refused: "The provider declined this assessment.",
  invalid_response: "Cloud output failed evidence validation.",
  incomplete_response: "The provider returned an incomplete response.",
  response_too_large: "Provider response exceeded limits.",
  network_error: "Could not reach the selected provider.",
  provider_unavailable: "Provider unavailable."
};

async function blank_refresh_cloud_popup_state() {
  try {
    const settings = await blank_send("blank_cloud_settings");
    const activeProvider = settings.provider || "groq";
    if (blank_cloud_provider) {
      blank_cloud_provider.value = activeProvider;
    }
    const isConfigured = Boolean(settings.configured?.[activeProvider]);

    if (isConfigured) {
      if (blank_cloud_connected_badge) blank_cloud_connected_badge.hidden = false;
      if (blank_cloud_input_group) blank_cloud_input_group.hidden = true;
      if (blank_cloud_connected_name) {
        blank_cloud_connected_name.textContent = "AI Defense Active";
      }
    } else {
      if (blank_cloud_connected_badge) blank_cloud_connected_badge.hidden = true;
      if (blank_cloud_input_group) blank_cloud_input_group.hidden = false;
      if (blank_cloud_key_status) {
        blank_cloud_key_status.textContent = "No key configured for this session.";
      }
      if (blank_cloud_key_input) {
        blank_cloud_key_input.value = "";
        blank_cloud_key_input.placeholder = activeProvider === "groq" ? "Paste Groq key (gsk_...)" : "Paste Gemini key (AIza...)";
      }
    }
  } catch (err) {
    if (blank_cloud_key_status) blank_cloud_key_status.textContent = err.message;
  }
}

// Provider select change handler
if (blank_cloud_provider) {
  blank_cloud_provider.onchange = () => {
    const p = blank_cloud_provider.value;
    if (blank_cloud_key_input) {
      blank_cloud_key_input.value = "";
      blank_cloud_key_input.placeholder = p === "groq" ? "Paste Groq key (gsk_...)" : "Paste Gemini key (AIza...)";
    }
    if (blank_cloud_key_status) {
      blank_cloud_key_status.textContent = `Selected ${p.toUpperCase()}. Enter key and click Connect.`;
    }
  };
}

// Inline Connect API Key button handler
const saveBtn = document.getElementById("popup-cloud-save");
if (saveBtn) {
  saveBtn.onclick = async () => {
    saveBtn.disabled = true;
    const provider = blank_cloud_provider?.value || "groq";
    const key = blank_cloud_key_input?.value?.trim() || "";
    if (!key) {
      if (blank_cloud_key_status) blank_cloud_key_status.textContent = "Please enter an API key.";
      saveBtn.disabled = false;
      return;
    }
    const origin = provider === "groq" ? "https://api.groq.com/*" : "https://generativelanguage.googleapis.com/*";
    try {
      if (blank_cloud_key_status) blank_cloud_key_status.textContent = "Requesting provider permission…";
      const granted = await chrome.permissions.request({origins: [origin]});
      if (!granted) throw Error("Provider access was declined.");
      const result = await blank_send("blank_cloud_configure", {provider, key});
      if (result?.error) throw Error(result.error);
      await blank_refresh_cloud_popup_state();
    } catch (err) {
      if (blank_cloud_key_status) blank_cloud_key_status.textContent = err.message;
    } finally {
      saveBtn.disabled = false;
    }
  };
}

// Inline Change / Forget Key button handler
if (blank_cloud_clear_btn) {
  blank_cloud_clear_btn.onclick = async () => {
    await blank_send("blank_cloud_forget");
    await blank_refresh_cloud_popup_state();
  };
}

// Cloud Preview
document.getElementById("cloud-preview").onclick = async () => {
  document.getElementById("cloud-form").hidden = true;
  document.getElementById("cloud-findings").replaceChildren();
  blank_cloud_status.textContent = "Preparing a fresh local scan and passage preview…";
  try {
    const settings = await blank_send("blank_cloud_settings");
    if (!settings.configured?.[settings.provider]) {
      blank_cloud_status.textContent = blank_cloud_messages.key_required;
      return;
    }
    const preview = await blank_send("blank_cloud_preview", {tab_id: blank_tab.id});
    if (preview.error) throw Error(preview.error);
    blank_cloud_preview = preview;
    blank_render(preview.local_result);

    const container = document.getElementById("cloud-passages");
    container.replaceChildren();

    for (const block of preview.blocks) {
      const section = document.createElement("section");
      const label = document.createElement("label");
      const input = document.createElement("input");
      const text = document.createElement("blockquote");

      section.className = "finding skeuo-finding-card cloud-passage-item";
      input.type = "checkbox";
      input.value = block.block_id;
      input.checked = true;

      label.className = "cloud-passage-label";
      label.append(input, document.createTextNode(` Include ${block.block_id}`));
      text.className = "finding-evidence-quote";
      text.textContent = block.text;

      section.append(label, text);
      container.append(section);
    }

    document.getElementById("cloud-consent").checked = false;
    document.getElementById("cloud-policy").textContent = preview.provider === "gemini" ?
      "Gemini free-tier content may be used to improve Google products. Do not send sensitive information." :
      "Groq may retain content for reliability or abuse monitoring; account data controls apply. Do not send sensitive information.";
    blank_cloud_status.textContent = `Review before sending to ${preview.provider} · ${preview.model}. ${preview.omitted_blocks} additional blocks omitted.`;
    document.getElementById("cloud-form").hidden = false;
  } catch (error) {
    blank_cloud_status.textContent = error.message;
  }
};

// Cloud Submit Form
document.getElementById("cloud-form").onsubmit = async (event) => {
  event.preventDefault();
  const button = document.getElementById("cloud-send");
  const cancel = document.getElementById("cloud-cancel");
  button.disabled = true;
  cancel.hidden = false;
  blank_cloud_status.textContent = "Requesting a cloud second opinion…";

  try {
    const block_ids = [...document.querySelectorAll("#cloud-passages input:checked")].map(x => x.value);
    const result = await blank_send("blank_cloud_analyze", {
      tab_id: blank_tab.id,
      nonce: blank_cloud_preview.nonce,
      block_ids,
      confirmed: true
    });
    if (result.error) throw Error(result.error);
    if (result.status !== "completed") {
      blank_cloud_status.textContent = blank_cloud_messages[result.status] || "Cloud assessment unavailable.";
      return;
    }
    blank_cloud_status.textContent = `Cloud: ${blank_labels[result.verdict]} · ${result.provider} · ${result.model} · ${result.processing_ms} ms${result.disagreement ? " · Disagrees with local analysis" : ""}. The local verdict remains above.`;

    const container = document.getElementById("cloud-findings");
    container.replaceChildren();

    for (const finding of result.findings) {
      const card = document.createElement("section");
      const reason = document.createElement("p");
      const quote = document.createElement("blockquote");

      card.className = "finding skeuo-finding-card";
      reason.className = "finding-raw-message";
      reason.textContent = finding.message;
      quote.className = "finding-evidence-quote";
      quote.textContent = finding.evidence;

      card.append(reason, quote);
      container.append(card);
    }
  } catch (error) {
    blank_cloud_status.textContent = error.message;
  } finally {
    button.disabled = false;
    cancel.hidden = true;
    document.getElementById("cloud-consent").checked = false;
  }
};

document.getElementById("cloud-cancel").onclick = () => blank_send("blank_cloud_cancel", {tab_id: blank_tab.id});

// Initialize on load
blank_refresh_cloud_popup_state();
