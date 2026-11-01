/* All analysis runs in this trusted worker using packaged rules and model data. */
importScripts("detector.js");
importScripts("cloud-config.js", "cloud.js", "cloud-worker.js");
const blank_states = new Map();
const blank_cache = new Map();
const blank_epochs = new Map();
const blank_commits = new Map();
const blank_ready = (async () => {
  await chrome.storage.local.setAccessLevel({accessLevel: "TRUSTED_CONTEXTS"});
  await chrome.storage.session.setAccessLevel({accessLevel: "TRUSTED_CONTEXTS"});
  await chrome.storage.local.remove("blank_token"); // Migrate old paired installations.
})();
const blank_detector = (async () => {
  const load = async name => {
    const response = await fetch(chrome.runtime.getURL(`assets/${name}.json`));
    if (!response.ok) throw new Error("Bundled detector data unavailable.");
    return response.json();
  };
  return new BlankDetector(await load("rules"), await load("model").catch(() => null));
})();
blank_detector.catch(() => {}); // Scans report a failed bundle as unavailable.

const blank_unavailable = (message) => ({verdict: "scan_unavailable", message});
const blank_supported = (url) => /^https?:\/\//i.test(url || "");
const blank_pattern = (url) => `${new URL(url).origin}/*`.replace(/:\d+(?=\/)/, "");

async function blank_ensure_offscreen() {
  if (chrome.offscreen?.hasDocument && await chrome.offscreen.hasDocument()) return;
  const existing = chrome.runtime.getContexts ? await chrome.runtime.getContexts({contextTypes: ["OFFSCREEN_DOCUMENT"]}) : [];
  if (existing.length > 0) return;
  if (chrome.offscreen?.createDocument) {
    await chrome.offscreen.createDocument({
      url: "offscreen.html",
      reasons: ["WORKERS", "CLIPBOARD"],
      justification: "Run local ONNX semantic inference and inspect clipboard safely"
    });
  }
}

async function blank_get_clipboard() {
  try {
    const task = (async () => {
      await blank_ensure_offscreen();
      const response = await chrome.runtime.sendMessage({
        target: "blank_offscreen",
        type: "blank_read_clipboard"
      });
      return response?.text || "";
    })();
    return await Promise.race([
      task,
      new Promise(resolve => setTimeout(() => resolve(""), 500))
    ]);
  } catch {
    return "";
  }
}

async function blank_run_semantic(blocks) {
  try {
    const task = (async () => {
      await blank_ensure_offscreen();
      const response = await chrome.runtime.sendMessage({
        target: "blank_offscreen",
        type: "blank_semantic_infer",
        id: crypto.randomUUID(),
        blocks
      });
      if (response?.error) return null;
      return response;
    })();
    return await Promise.race([
      task,
      new Promise(resolve => setTimeout(() => resolve(null), 3500))
    ]);
  } catch {
    return null;
  }
}

async function blank_settings() {
  await blank_ready;
  const {blank_sites = []} = await chrome.storage.local.get("blank_sites");
  const detector = await blank_detector.catch(() => null);
  return {sites: blank_sites, detector_mode: !detector ? "unavailable" : detector.model ? "hybrid" : "rules_only",
    model_version: detector?.model?.model_version ?? null};
}

function blank_commit(tabId, operation) {
  const pending = (blank_commits.get(tabId) || Promise.resolve()).catch(() => {}).then(operation);
  blank_commits.set(tabId, pending);
  pending.finally(() => {if (blank_commits.get(tabId) === pending) blank_commits.delete(tabId);}).catch(() => {});
  return pending;
}

async function blank_store_result(tabId, result, state) {
  return blank_commit(tabId, async () => {
    if (state && blank_states.get(tabId) !== state) return;
    await chrome.storage.session.set({[`blank_result_${tabId}`]: result});
    if (state && blank_states.get(tabId) !== state) {
      await chrome.storage.session.remove(`blank_result_${tabId}`);
      return;
    }
    await chrome.action.setBadgeText({tabId, text: result.verdict === "suspicious" ? "!" :
      result.verdict === "uncertain" ? "?" : result.verdict === "scan_unavailable" ? "×" : ""}).catch(() => {});
    await chrome.action.setBadgeBackgroundColor({tabId, color: result.verdict === "suspicious" ? "#c43c42" : "#9a6618"}).catch(() => {});
  });
}

function blank_clear_result(tabId) {
  return blank_commit(tabId, async () => {
    await chrome.storage.session.remove([`blank_result_${tabId}`, `blank_ai_result_${tabId}`]);
    await chrome.action.setBadgeText({tabId, text: ""}).catch(() => {});
  });
}

async function blank_analyze(tabId, extracted, automatic = false, pattern = null, clipboard = null) {
  const previous = blank_states.get(tabId);
  if (automatic && previous?.busy) return {skipped: true};
  if (automatic && Date.now() - (previous?.started || 0) < 5000) return {skipped: true};
  previous?.controller?.abort();
  const state = {controller: new AbortController(), busy: true, started: Date.now(), automatic, pattern};
  blank_states.set(tabId, state);
  const payload = {scan_id: crypto.randomUUID(), blocks: extracted.blocks, extraction: extracted.extraction};
  if (clipboard && typeof clipboard === "string") payload.clipboard = clipboard.slice(0, 4000);
  let result;
  try {
    const serialized = JSON.stringify(payload);
    if (new TextEncoder().encode(serialized).length > 131072) throw new Error("Extraction exceeded request limits.");
    const fingerprint = JSON.stringify([payload.blocks, payload.extraction]);
    const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(fingerprint)))].map(x => x.toString(16).padStart(2, "0")).join("");
    const cacheKey = `${tabId}:${digest}`;
    const cached = blank_cache.get(cacheKey);
    if (automatic && cached && Date.now() - cached.at < 30000) {
      result = {...cached.result, scan_id: payload.scan_id, cached: true};
    } else {
      const detector = await blank_detector;
      if (state.controller.signal.aborted) return {skipped: true};
      result = detector.analyze(payload);
      if (!["suspicious", "uncertain", "no_suspicious_signals"].includes(result.verdict) ||
          result.scan_id !== payload.scan_id || !Array.isArray(result.findings)) throw new Error("Invalid detector result.");
      const { blank_semantic_enabled = false } = await chrome.storage.local.get(["blank_semantic_enabled"]);
      if (blank_semantic_enabled && payload.blocks.length > 0 && !state.controller.signal.aborted) {
        const semantic = await blank_run_semantic(payload.blocks);
        if (semantic?.scores) {
          result.detector_mode = "hybrid_semantic";
          result.semantic_model_version = semantic.model_version;
          const threshold = semantic.thresholds?.hybrid ?? 0.8;
          for (const item of semantic.scores) {
            const block = payload.blocks.find(b => b.block_id === item.block_id);
            if (!block) continue;
            if (item.score >= threshold && result.verdict !== "suspicious") {
              const hasLure = result.findings.some(f => f.block_id === item.block_id) || Boolean(block.context?.has_copy_button);
              if (hasLure) {
                result.verdict = "suspicious";
                result.findings.push({
                  code: "SEMANTIC_MODEL_CONCERN",
                  message: `Experimental semantic model flagged ClickFix pattern (${item.score.toFixed(2)}).`,
                  block_id: item.block_id,
                  evidence: block.text.slice(0, 160)
                });
              }
            } else if (item.score >= 0.5 && result.verdict === "no_suspicious_signals") {
              result.verdict = "uncertain";
              result.findings.push({
                code: "SEMANTIC_MODEL_CONCERN",
                message: `Experimental semantic model noted ambiguous signals (${item.score.toFixed(2)}).`,
                block_id: item.block_id,
                evidence: block.text.slice(0, 160)
              });
            }
          }
        }
      }
      if (blank_cache.size > 50) blank_cache.clear();
      blank_cache.set(cacheKey, {at: Date.now(), result});
    }
  } catch (error) {
    if (state.controller.signal.aborted) return {skipped: true};
    result = blank_unavailable("Local analysis failed. Reload BLANK and retry; no protection verdict is available.");
  } finally {
    state.busy = false;
  }
  if (blank_states.get(tabId) !== state) return {skipped: true};
  await blank_store_result(tabId, result, state);
  if (blank_states.get(tabId) !== state) return {skipped: true};
  await chrome.tabs.sendMessage(tabId, {type: "blank_result", result,
    document_key: extracted.document_key, revision: extracted.revision, automatic}, {frameId: 0}).catch(() => {});
  return result;
}

async function blank_manual_scan(tabId, clipboard = null) {
  const epoch = blank_epochs.get(tabId);
  const tab = await chrome.tabs.get(tabId);
  if (!blank_supported(tab.url)) return {verdict: "unsupported_page", message: "Only supported HTTP and HTTPS webpages can be scanned."};
  try {
    if (clipboard === null || clipboard === undefined) {
      clipboard = await blank_get_clipboard();
    }
    await chrome.scripting.executeScript({target: {tabId, frameIds: [0]}, files: ["content.js"]});
    const extracted = await chrome.tabs.sendMessage(tabId, {type: "blank_extract"}, {frameId: 0});
    if (blank_epochs.get(tabId) !== epoch) return {skipped: true};
    return await blank_analyze(tabId, extracted, false, null, clipboard);
  } catch {
    if (blank_epochs.get(tabId) !== epoch) return {skipped: true};
    const result = blank_unavailable("The browser did not allow extraction on this page. Reload the page and retry.");
    await blank_store_result(tabId, result);
    return result;
  }
}

function blank_cancel_disabled_automatic(sites) {
  for (const [tabId, state] of blank_states) {
    if (state.automatic && !sites.includes(state.pattern)) {
      state.controller.abort();
      blank_states.delete(tabId);
    }
  }
}

async function blank_sync_sites() {
  const {sites} = await blank_settings();
  const permitted = [];
  for (const pattern of sites) {
    if (await chrome.permissions.contains({origins: [pattern]})) permitted.push(pattern);
  }
  blank_cancel_disabled_automatic(permitted);
  const existing = await chrome.scripting.getRegisteredContentScripts();
  const ids = existing.filter(x => x.id.startsWith("blank_auto_")).map(x => x.id);
  if (ids.length) await chrome.scripting.unregisterContentScripts({ids});
  let index = 0;
  for (const pattern of permitted) {
    await chrome.scripting.registerContentScripts([{id: `blank_auto_${index++}`, matches: [pattern],
      js: ["content.js"], runAt: "document_idle", allFrames: false, persistAcrossSessions: true}]);
  }
  for (const tab of await chrome.tabs.query({})) {
    // Existing isolated-world scripts recheck their own permission/settings through the worker.
    await chrome.tabs.sendMessage(tab.id, {type: "blank_refresh_auto"}, {frameId: 0}).catch(() => {});
    if (blank_supported(tab.url) && sites.includes(blank_pattern(tab.url)) &&
        await chrome.permissions.contains({origins: [blank_pattern(tab.url)]})) {
      await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ["content.js"]}).catch(() => {});
    }
  }
}

async function blank_ai_analyze(tabId, clipboard = null) {
  const tab = await chrome.tabs.get(tabId).catch(() => null);
  if (!tab || !blank_supported(tab.url)) {
    return { status: "unsupported", verdict: "unsupported_page" };
  }
  if (clipboard === null || clipboard === undefined) {
    clipboard = await blank_get_clipboard();
  }
  const extracted = await chrome.tabs.sendMessage(tabId, { type: "blank_extract" }, { frameId: 0 }).catch(() => null);
  const blocks = extracted?.blocks || [];
  let aiResult;
  try {
    aiResult = await BlankAI.request(blocks, { url: tab.url, title: tab.title, clipboard });
  } catch (err) {
    aiResult = { status: "unavailable", error: err.message, verdict: "uncertain" };
  }
  await chrome.storage.session.set({ [`blank_ai_result_${tabId}`]: aiResult }).catch(() => {});

  if (aiResult.status !== "completed") {
    return aiResult;
  }

  // AI Verdict Reconciliation: Harmonize local heuristics with deep AI semantic understanding
  const lastResultKey = `blank_result_${tabId}`;
  const sessionData = await chrome.storage.session.get([lastResultKey]).catch(() => ({}));
  let lastResult = sessionData[lastResultKey];

  if (aiResult.verdict === "legitimate" && (typeof aiResult.score !== "number" || aiResult.score < 0.50)) {
    const hasClipPayload = lastResult?.findings?.some(f => f.code === "CLIPBOARD_MALICIOUS_COMMAND");
    if (!hasClipPayload && lastResult && (lastResult.verdict === "suspicious" || lastResult.verdict === "uncertain")) {
      lastResult = {
        ...lastResult,
        verdict: "no_suspicious_signals",
        title: "Environment Secure",
        message: "Verified safe by Blank.ai: educational or search context; no command execution requested.",
        findings: [],
        reconciled_by_ai: true
      };
      await chrome.storage.session.set({ [lastResultKey]: lastResult }).catch(() => {});
      await chrome.action.setBadgeText({ tabId, text: "" }).catch(() => {});
      await chrome.tabs.sendMessage(tabId, {
        type: "blank_result",
        result: lastResult,
        document_key: extracted?.document_key,
        revision: extracted?.revision
      }, { frameId: 0 }).catch(() => {});

      return {
        ...aiResult,
        reconciled: true,
        updated_local_verdict: "no_suspicious_signals"
      };
    }
  } else if (aiResult.verdict === "scam" && (typeof aiResult.score !== "number" || aiResult.score >= 0.70)) {
    const aiFindings = [];
    if (Array.isArray(aiResult.reasons) && aiResult.reasons.length > 0) {
      for (const [idx, reason] of aiResult.reasons.entries()) {
        let code = "AI_SOCIAL_ENGINEERING";
        let glyph = "✦";
        let title = reason;
        let desc = "Deceptive pattern identified by deep AI contextual analysis.";
        if (/captcha|robot|human|verification/i.test(reason)) {
          code = "FAKE_VERIFICATION_LURE";
          glyph = "IMG";
          title = "Deceptive Verification Failure Lure";
          desc = "Simulates fake verification error or CAPTCHA prompt to lure user into execution.";
        } else if (/image|graphic|screenshot/i.test(reason)) {
          code = "INSTRUCTION_IMAGE_EVASION";
          glyph = "IMG";
          title = "Instructional Image Evasion";
          desc = "Accompanies deception with instructional image to avoid text filtering.";
        } else if (/run|powershell|cmd|terminal|command|paste|shortcut/i.test(reason)) {
          code = "SYSTEM_EXECUTION_LURE";
          glyph = ">_";
          title = "System Execution Request";
          desc = "Requests pasting and executing system commands.";
        } else if (/clipboard|copy/i.test(reason)) {
          code = "CLIPBOARD_MANIPULATION";
          glyph = "CPY";
          title = "Clipboard Manipulation Trap";
          desc = "Manipulates clipboard buffer or prompts user to copy payload.";
        } else if (/context|legitimate|error/i.test(reason)) {
          code = "UNVERIFIED_CONTEXT_TRAP";
          glyph = "!";
          title = "Unsolicited Access Request";
          desc = "No legitimate security or verification context for the requested action.";
        }
        aiFindings.push({
          code,
          glyph,
          title,
          message: reason,
          desc,
          evidence: aiResult.explanation || reason,
          block_id: `ai_${idx + 1}`
        });
      }
    } else if (aiResult.headline) {
      aiFindings.push({
        code: "AI_CLICKFIX_PATTERN",
        glyph: "✦",
        title: aiResult.headline,
        message: aiResult.headline,
        desc: "Social engineering pattern detected by Blank.ai.",
        evidence: aiResult.explanation || "Social engineering pattern detected by Blank.ai.",
        block_id: "ai_analysis"
      });
    }

    const combinedFindings = [...(lastResult?.findings || [])];
    for (const af of aiFindings) {
      if (!combinedFindings.some(f => f.code === af.code)) {
        combinedFindings.push(af);
      }
    }

    lastResult = {
      ...(lastResult || {}),
      verdict: "suspicious",
      title: "Deceptive Instructions Detected",
      message: "Blank.ai identified malicious ClickFix social engineering patterns.",
      findings: combinedFindings,
      reconciled_by_ai: true
    };
    await chrome.storage.session.set({ [lastResultKey]: lastResult }).catch(() => {});
    await chrome.action.setBadgeText({ tabId, text: "!" }).catch(() => {});
    await chrome.action.setBadgeBackgroundColor({ tabId, color: "#c43c42" }).catch(() => {});
    if (lastResult) {
      await chrome.tabs.sendMessage(tabId, {
        type: "blank_result",
        result: lastResult,
        document_key: extracted?.document_key,
        revision: extracted?.revision
      }, { frameId: 0 }).catch(() => {});
    }
    return {
      ...aiResult,
      reconciled: true,
      updated_local_verdict: "suspicious",
      updated_local_result: lastResult
    };
  }

  return aiResult;
}

async function blank_dispatch(message, sender) {
  await blank_ready;
  if (sender.id !== chrome.runtime.id) throw new Error("Invalid sender");
  const trusted = ["popup.html", "options.html"].some(page => sender.url === chrome.runtime.getURL(page));
  const content = sender.tab && sender.frameId === 0 && blank_supported(sender.url);
  if (content && message.type === "blank_auto_status") {
    const pattern = blank_pattern(sender.url);
    const {sites} = await blank_settings();
    return {enabled: sites.includes(pattern) && await chrome.permissions.contains({origins: [pattern]})};
  }
  if (content && message.type === "blank_auto_scan") {
    const epoch = blank_epochs.get(sender.tab.id);
    const status = await blank_dispatch({type: "blank_auto_status"}, sender);
    if (!status.enabled) return {skipped: true};
    const current = await chrome.tabs.sendMessage(sender.tab.id, {type: "blank_document"}, {frameId: 0}).catch(() => null);
    if (current?.document_key !== message.extracted?.document_key || blank_epochs.get(sender.tab.id) !== epoch) return {skipped: true};
    return blank_analyze(sender.tab.id, message.extracted, true, blank_pattern(sender.url));
  }
  if (!trusted) throw new Error("Message not allowed");
  if(message.type?.startsWith('blank_cloud_')) return blank_cloud_dispatch(message);
  switch (message.type) {
    case "blank_settings": return blank_settings();
    case "blank_check_detector":
      return (await blank_detector).analyze({scan_id: crypto.randomUUID(), blocks: []});
    case "blank_pause_all": {
      await chrome.storage.local.set({blank_sites: []});
      blank_cancel_disabled_automatic([]);
      await blank_sync_sites();
      return {paused: true};
    }
    case "blank_scan": return blank_manual_scan(message.tab_id, message.clipboard);
    case "blank_get_clipboard": return blank_get_clipboard();
    case "blank_ai_scan": return blank_ai_analyze(message.tab_id, message.clipboard);
    case "blank_last_ai_result":
      return (await chrome.storage.session.get(`blank_ai_result_${message.tab_id}`))[`blank_ai_result_${message.tab_id}`] || null;
    case "blank_last_result":
      return (await chrome.storage.session.get(`blank_result_${message.tab_id}`))[`blank_result_${message.tab_id}`] || null;
    case "blank_set_site": {
      const tab = await chrome.tabs.get(message.tab_id);
      if (!blank_supported(tab.url)) throw new Error("Unsupported page");
      const pattern = blank_pattern(tab.url);
      if (message.enabled && !await chrome.permissions.contains({origins: [pattern]})) throw new Error("Website access was not granted");
      const {sites} = await blank_settings();
      const next = sites.filter(x => x !== pattern);
      if (message.enabled) next.push(pattern);
      await chrome.storage.local.set({blank_sites: next});
      blank_cancel_disabled_automatic(next);
      await blank_sync_sites();
      return {enabled: Boolean(message.enabled)};
    }
    default: throw new Error("Unknown message");
  }
}

chrome.runtime.onMessage.addListener((message, sender, reply) => {
  blank_dispatch(message, sender).then(reply).catch(error => reply({error: error.message}));
  return true;
});
chrome.tabs.onUpdated.addListener((tabId, change) => {
  if (change.status === "loading") {
    blank_cloud_cancel(tabId);
    blank_epochs.set(tabId, (blank_epochs.get(tabId) || 0) + 1);
    blank_states.get(tabId)?.controller?.abort();
    blank_states.delete(tabId);
    blank_clear_result(tabId).catch(() => {});
    for (const key of blank_cache.keys()) if (key.startsWith(`${tabId}:`)) blank_cache.delete(key);
  }
});
chrome.tabs.onRemoved.addListener(tabId => {
  blank_cloud_cancel(tabId);
  blank_states.get(tabId)?.controller?.abort();
  blank_states.delete(tabId);
  blank_epochs.delete(tabId);
  blank_clear_result(tabId).catch(() => {});
  for (const key of blank_cache.keys()) if (key.startsWith(`${tabId}:`)) blank_cache.delete(key);
});
chrome.permissions.onRemoved.addListener(() => {
  blank_cloud_cancel();
  blank_sync_sites().catch(() => {});
});
chrome.runtime.onInstalled.addListener(details => {
  blank_sync_sites().catch(() => {});
  if (details.reason === "install") chrome.runtime.openOptionsPage();
  if (details.reason === "update") chrome.storage.session.clear();
});
chrome.runtime.onStartup.addListener(() => blank_sync_sites().catch(() => {}));
