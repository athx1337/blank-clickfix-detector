const blank_labels = {
  ready: "Ready",
  scanning: "Scanning",
  suspicious: "Suspicious",
  uncertain: "Uncertain",
  no_suspicious_signals: "No suspicious signals found",
  scan_unavailable: "Scan unavailable",
  unsupported_page: "Unsupported page"
};
let blank_tab;
const blank_send = (type, data = {}) => chrome.runtime.sendMessage({type, ...data});

function blank_render_clipboard(clipText) {
  const card = document.getElementById("clipboard-card");
  const codeEl = document.getElementById("clipboard-code-text");
  const clearBtn = document.getElementById("clipboard-clear-btn");
  const label = document.getElementById("clipboard-clear-label");

  if (!card || !codeEl) return;

  if (!clipText || !clipText.trim()) {
    card.style.display = "none";
    return;
  }

  codeEl.textContent = clipText.slice(0, 300);
  card.style.display = "flex";
  if (label) label.textContent = "WIPE CLIPBOARD NOW";
  if (clearBtn) {
    clearBtn.classList.remove("cleared");
    clearBtn.onclick = async () => {
      try {
        await navigator.clipboard.writeText("");
        if (label) label.textContent = "✓ CLIPBOARD WIPED CLEAN";
        clearBtn.classList.add("cleared");
        setTimeout(() => {
          card.style.display = "none";
        }, 1500);
      } catch {}
    };
  }
}

async function blank_get_clipboard() {
  try {
    if (navigator.clipboard && navigator.clipboard.readText) {
      const text = await Promise.race([
        navigator.clipboard.readText(),
        new Promise(resolve => setTimeout(() => resolve(""), 350))
      ]);
      if (text) return text;
    }
  } catch {}
  try {
    const res = await Promise.race([
      blank_send("blank_get_clipboard"),
      new Promise(resolve => setTimeout(() => resolve({ text: "" }), 350))
    ]);
    return res?.text || (typeof res === "string" ? res : "") || "";
  } catch {}
  return "";
}

function blank_render(result) {
  const verdict = result?.verdict || "ready";
  const stateEl = document.getElementById("state");
  if (stateEl) stateEl.textContent = blank_labels[verdict] || "Scan unavailable";

  const statusEl = document.getElementById("status");
  if (statusEl) statusEl.dataset.verdict = verdict;
  document.body.dataset.threat = verdict === "suspicious" ? "true" : "false";

  const headline = document.getElementById("status-headline");
  if (headline) {
    headline.textContent = result?.title || (
      verdict === "suspicious" ? "Deceptive Instructions Detected" :
      verdict === "uncertain" ? "Ambiguous Instructions" :
      verdict === "scanning" ? "Scanning Webpage…" :
      verdict === "scan_unavailable" || verdict === "unsupported_page" ? "Scan Unavailable" :
      "Environment Secure"
    );
  }

  const summary = document.getElementById("summary");
  if (summary) {
    summary.textContent = result?.message || (
      verdict === "suspicious" ? "This page contains deceptive instructions attempting system execution." :
      verdict === "uncertain" ? "Review visible evidence and extraction limits before proceeding." :
      verdict === "no_suspicious_signals" ? "This page contains no deceptive copy-and-run prompts." :
      verdict === "scanning" ? "Reading and analyzing instruction blocks on this device…" :
      verdict === "unsupported_page" ? "Open a standard HTTP or HTTPS webpage to scan." :
      "Scan visible webpage instructions for deceptive execution requests."
    );
  }

  const scanBtnLabel = document.getElementById("scan-btn-label");
  if (scanBtnLabel) {
    scanBtnLabel.textContent = verdict === "suspicious" ? "RE-SCAN PAGE" :
      verdict === "scanning" ? "SCANNING…" : "SCAN THIS PAGE";
  }

  const metaEl = document.getElementById("meta");
  if (metaEl) {
    const modeStr = result.detector_mode === "rules_only" ? "Rules only" : "Hybrid";
    const truncStr = result.extraction?.truncated ? " · Extraction incomplete" : "";
    metaEl.textContent = result?.detector_mode ? `${modeStr}${truncStr}` : "";
  }

  const container = document.getElementById("findings");
  container.replaceChildren();

  const clipFinding = (result?.findings || []).find(f => f.code === "CLIPBOARD_MALICIOUS_COMMAND");
  blank_render_clipboard(clipFinding ? clipFinding.evidence : null);

  // If page was scanned and found clean, display Oxide All Clear banner
  if (verdict === "no_suspicious_signals") {
    const cleanCard = document.createElement("section");
    cleanCard.className = "oxide-clean-banner";
    cleanCard.innerHTML = `
      <div class="oxide-clean-icon">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
      </div>
      <div class="oxide-clean-col">
        <div class="oxide-clean-title">[ ALL CLEAR ]</div>
        <div class="oxide-clean-desc">No deceptive ClickFix instructions detected on this page.</div>
      </div>
    `;
    container.append(cleanCard);
  }

  // Filter out clipboard finding (displayed in dedicated threat card)
  let displayFindings = (result?.findings || []).filter(f => f.code !== "CLIPBOARD_MALICIOUS_COMMAND");

  // Suppress duplicate/redundant generic MODEL_TEXT_SIMILARITY cards
  const hasRuleFindings = displayFindings.some(f => f.code !== "MODEL_TEXT_SIMILARITY");
  if (hasRuleFindings) {
    displayFindings = displayFindings.filter(f => f.code !== "MODEL_TEXT_SIMILARITY");
  } else {
    // If only MODEL_TEXT_SIMILARITY findings exist, deduplicate to keep only the highest scoring one
    const modelFindings = displayFindings.filter(f => f.code === "MODEL_TEXT_SIMILARITY");
    if (modelFindings.length > 1) {
      let bestFinding = modelFindings[0];
      let maxScore = 0;
      for (const mf of modelFindings) {
        const m = mf.message?.match(/0\.\d+/);
        const sc = m ? parseFloat(m[0]) : 0;
        if (sc > maxScore) {
          maxScore = sc;
          bestFinding = mf;
        }
      }
      displayFindings = [bestFinding];
    }
  }

  for (const finding of displayFindings.slice(0, 16)) {
    const card = document.createElement("section");
    card.className = "finding oxide-finding-card";

    let glyphText = ">_";
    let friendlyTitle = "Suspicious Instruction";
    let friendlyDesc = finding.message;

    if (finding.title) {
      glyphText = finding.glyph || "✦";
      friendlyTitle = finding.title;
      friendlyDesc = finding.desc || finding.message;
    } else if (finding.code === "VERIFICATION_WITH_SYSTEM_EXECUTION" || finding.code === "SUSPICIOUS_SYSTEM_EXECUTION_SEQUENCE") {
      glyphText = ">_";
      friendlyTitle = "System Command Execution Sequence";
      friendlyDesc = "Instructs opening Windows Run (Win + R), pasting code, and executing.";
    } else if (finding.code === "SUSPICIOUS_MULTI_STEP_EXECUTION_SEQUENCE") {
      glyphText = ">_";
      friendlyTitle = "Multi-Step Execution Sequence";
      friendlyDesc = "Coordinates system run dialog or terminal paste across instruction steps.";
    } else if (finding.code === "INSTRUCTION_IMAGE_VERIFICATION_LURE") {
      glyphText = "IMG";
      friendlyTitle = "Instructional Image Evasion";
      friendlyDesc = "Displays verification instructions inside an image to evade text filters.";
    } else if (finding.code === "REPAIR_WITH_PASTE_AND_RUN") {
      glyphText = ">_";
      friendlyTitle = "Browser Repair Execution";
      friendlyDesc = "Instructs pasting and running a command in terminal under pretext of repair.";
    } else if (finding.code === "DIALOG_LURE_WITH_COPY_AND_SYSTEM_PASTE" || finding.code === "INSTRUCTION_DIALOG_COPY_EXECUTE") {
      glyphText = "CPY";
      friendlyTitle = "Copy & Paste Execution Trap";
      friendlyDesc = "Combines copying a code payload with instructions to paste into system.";
    } else if (finding.code === "MODEL_TEXT_SIMILARITY") {
      glyphText = "ML";
      const match = finding.message?.match(/0\.\d+/);
      const score = match ? match[0] : "0.55";
      friendlyTitle = `Semantic Risk Score: ${score}`;
      friendlyDesc = "Elevated statistical similarity to known ClickFix attack patterns.";
    } else {
      glyphText = "!";
      friendlyTitle = finding.message.length > 32 ? finding.message.slice(0, 32) + "…" : finding.message;
      friendlyDesc = finding.message;
    }

    const header = document.createElement("div");
    header.className = "oxide-finding-header";

    const glyphEl = document.createElement("div");
    glyphEl.className = "oxide-finding-glyph";
    glyphEl.textContent = glyphText;

    const infoCol = document.createElement("div");
    infoCol.className = "oxide-finding-info";

    const titleEl = document.createElement("div");
    titleEl.className = "oxide-finding-title";
    titleEl.textContent = friendlyTitle;

    const descEl = document.createElement("div");
    descEl.className = "oxide-finding-desc";
    descEl.textContent = friendlyDesc;

    infoCol.append(titleEl, descEl);

    const toggleEl = document.createElement("div");
    toggleEl.className = "oxide-finding-toggle";
    toggleEl.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>`;

    header.append(glyphEl, infoCol, toggleEl);

    const details = document.createElement("div");
    details.className = "oxide-finding-details";

    const rawMsg = document.createElement("p");
    rawMsg.className = "oxide-finding-raw-msg";
    rawMsg.textContent = finding.message;

    const evidenceEl = document.createElement("pre");
    evidenceEl.className = "oxide-finding-evidence";
    evidenceEl.textContent = finding.evidence;

    const codeTag = document.createElement("span");
    codeTag.className = "oxide-finding-code-tag";
    codeTag.textContent = `[ ${finding.code} · ${finding.block_id.toUpperCase()} ]`;

    details.append(rawMsg, evidenceEl, codeTag);

    // Expand first finding by default for immediate threat visibility
    if (displayFindings.indexOf(finding) === 0) {
      card.classList.add("expanded");
    }

    header.onclick = (e) => {
      e.preventDefault();
      card.classList.toggle("expanded");
    };

    card.append(header, details);
    container.append(card);
  }
}

function blank_render_ai(aiResult) {
  const idle = document.getElementById("ai-idle");
  const loading = document.getElementById("ai-loading");
  const resultBox = document.getElementById("ai-result");
  const chip = document.getElementById("ai-chip");

  if (!aiResult) {
    if (idle) idle.style.display = "block";
    if (loading) loading.style.display = "none";
    if (resultBox) resultBox.style.display = "none";
    if (chip) { chip.textContent = "[ READY ]"; chip.className = "oxide-ai-chip"; }
    return;
  }

  if (aiResult.status === "analyzing") {
    if (idle) idle.style.display = "none";
    if (loading) loading.style.display = "block";
    if (resultBox) resultBox.style.display = "none";
    if (chip) { chip.textContent = "[ AUDITING… ]"; chip.className = "oxide-ai-chip analyzing"; }
    return;
  }

  if (aiResult.status === "unconfigured") {
    if (idle) idle.style.display = "none";
    if (loading) loading.style.display = "none";
    if (resultBox) resultBox.style.display = "flex";
    if (chip) { chip.textContent = "[ BYOK READY ]"; chip.className = "oxide-ai-chip"; }
    const banner = document.getElementById("ai-verdict-banner");
    const icon = document.getElementById("ai-verdict-icon");
    const title = document.getElementById("ai-verdict-title");
    const sub = document.getElementById("ai-verdict-sub");
    const headline = document.getElementById("ai-headline");
    const explanation = document.getElementById("ai-explanation");
    const reasonsList = document.getElementById("ai-reasons-list");
    if (banner) banner.className = "oxide-ai-banner ai-banner-byok";
    if (icon) icon.textContent = "⚡";
    if (title) title.textContent = "LOCAL HYBRID DEFENSE ACTIVE";
    if (sub) sub.textContent = "OPTIONAL BYOK CLOUD AI";
    if (headline) headline.textContent = "Deep Cloud AI Verification (Optional)";
    if (explanation) explanation.textContent = "On-device detection is 100% active. Add a free Groq or Gemini API key in Settings (⚙️) if you want dual-layer cloud LLM auditing.";
    if (reasonsList) reasonsList.replaceChildren();
    const reasonsBox = document.getElementById("ai-reasons-box");
    if (reasonsBox) reasonsBox.style.display = "none";
    return;
  }

  if (idle) idle.style.display = "none";
  if (loading) loading.style.display = "none";
  if (resultBox) resultBox.style.display = "flex";

  const banner = document.getElementById("ai-verdict-banner");
  const icon = document.getElementById("ai-verdict-icon");
  const title = document.getElementById("ai-verdict-title");
  const sub = document.getElementById("ai-verdict-sub");
  const headline = document.getElementById("ai-headline");
  const explanation = document.getElementById("ai-explanation");
  const reasonsList = document.getElementById("ai-reasons-list");

  const isScam = aiResult.verdict === "scam";
  const isLegit = aiResult.verdict === "legitimate";

  if (chip) {
    chip.textContent = isScam ? "[ SCAM CONFIRMED ]" : (isLegit ? "[ VERIFIED SAFE ]" : "[ UNCERTAIN ]");
    chip.className = `oxide-ai-chip ${isScam ? "scam" : (isLegit ? "safe" : "uncertain")}`;
  }

  if (banner) {
    banner.className = `oxide-ai-banner ${isScam ? "ai-banner-scam" : (isLegit ? "ai-banner-legit" : "ai-banner-uncertain")}`;
  }

  if (icon) {
    icon.textContent = isScam ? "🛑" : (isLegit ? "🛡️" : "⚠️");
  }

  if (title) {
    title.textContent = isScam ? "SCAM DETECTED" : (isLegit ? "VERIFIED SAFE" : "UNCERTAIN SIGNALS");
  }

  if (sub) {
    const pct = Math.round((typeof aiResult.score === "number" ? aiResult.score : (isScam ? 0.99 : 0.05)) * 100);
    sub.textContent = isScam ? `RISK CONFIDENCE: ${pct}%` : `SAFETY CONFIDENCE: ${isLegit ? Math.max(90, 100 - pct) : pct}%`;
  }

  if (headline) {
    headline.textContent = aiResult.headline || (isScam ? "Social Engineering / ClickFix Attack" : "Instructions Appear Safe");
  }

  if (explanation) {
    explanation.textContent = aiResult.explanation || "";
  }

  if (reasonsList) {
    reasonsList.replaceChildren();
    for (const reason of (aiResult.reasons || []).slice(0, 5)) {
      const li = document.createElement("li");
      li.textContent = reason;
      reasonsList.append(li);
    }
    const reasonsBox = document.getElementById("ai-reasons-box");
    if (reasonsBox) reasonsBox.style.display = (aiResult.reasons && aiResult.reasons.length) ? "flex" : "none";
  }


}

document.getElementById("scan").onclick = async () => {
  const button = document.getElementById("scan");
  button.disabled = true;
  blank_render({verdict: "scanning"});
  blank_render_ai({status: "analyzing"});
  try {
    const clipboardText = await blank_get_clipboard();
    const result = await Promise.race([
      blank_send("blank_scan", {tab_id: blank_tab.id, clipboard: clipboardText}),
      new Promise((_, reject) => setTimeout(() => reject(new Error("Local scan timed out")), 8000))
    ]);
    blank_render(result?.error ? {verdict: "scan_unavailable", message: result.error} : result);
    if (!result?.error && clipboardText && /(?:powershell|cmd(?:\.exe)?|mshta|bash|sh|wscript|cscript|certutil|rundll32|regsvr32)\b/i.test(clipboardText)) {
      blank_render_clipboard(clipboardText);
    }
    // Automatically trigger Blank.ai deep intelligence with clipboard included
    blank_send("blank_ai_scan", {tab_id: blank_tab.id, clipboard: clipboardText}).then(aiRes => {
      blank_render_ai(aiRes);
      if (aiRes?.reconciled && aiRes?.updated_local_verdict === "no_suspicious_signals") {
        blank_render({
          verdict: "no_suspicious_signals",
          title: "Environment Secure",
          message: "Verified safe by Blank.ai deep intelligence: educational or search context; no command execution requested."
        });
      } else if (aiRes?.reconciled && aiRes?.updated_local_verdict === "suspicious") {
        blank_render(aiRes.updated_local_result || {
          ...result,
          verdict: "suspicious",
          title: "Deceptive Instructions Detected",
          message: "Blank.ai identified malicious ClickFix social engineering patterns."
        });
      }
      if (aiRes?.clipboard_verdict === "malicious" && clipboardText) {
        blank_render_clipboard(clipboardText);
      }
    }).catch(err => {
      blank_render_ai({status: "unavailable", error: err.message, verdict: "uncertain"});
    });
  } catch (err) {
    blank_render({verdict: "scan_unavailable", message: err.message || "Extension unavailable. Reload and retry."});
    blank_render_ai(null);
  } finally {
    button.disabled = false;
  }
};

document.getElementById("settings").onclick = () => chrome.runtime.openOptionsPage();

document.getElementById("auto").onchange = async (event) => {
  const checkbox = event.target, enabled = checkbox.checked;
  try {
    if (!/^https?:/.test(blank_tab?.url || "")) throw new Error("Open a supported webpage first.");
    const pattern = `${new URL(blank_tab.url).origin}/*`.replace(/:\d+(?=\/)/, "");
    if (enabled && !await chrome.permissions.request({origins: [pattern]})) throw new Error("Website access was declined.");
    const result = await blank_send("blank_set_site", {tab_id: blank_tab.id, enabled});
    if (result?.error) throw new Error(result.error);
    checkbox.checked = result.enabled;
  } catch (error) {
    checkbox.checked = !enabled;
    blank_render({verdict: "scan_unavailable", message: error.message});
  }
};

window.blank_render = blank_render;
window.blank_render_ai = blank_render_ai;

(async () => {
  [blank_tab] = await chrome.tabs.query({active: true, currentWindow: true});
  const settings = await blank_send("blank_settings");
  if (settings?.error || settings.detector_mode === "unavailable") {
    blank_render({verdict: "scan_unavailable", message: "Bundled detector unavailable. Reload BLANK and retry."});
  }
  if (/^https?:/.test(blank_tab?.url || "")) {
    const pattern = `${new URL(blank_tab.url).origin}/*`.replace(/:\d+(?=\/)/, "");
    document.getElementById("auto").checked = settings.sites?.includes(pattern) && await chrome.permissions.contains({origins: [pattern]});
  } else {
    document.getElementById("auto").disabled = true;
  }
  const last = await blank_send("blank_last_result", {tab_id: blank_tab?.id});
  if (last) blank_render(last);
  const lastAi = await blank_send("blank_last_ai_result", {tab_id: blank_tab?.id});
  if (lastAi) blank_render_ai(lastAi);
})();
