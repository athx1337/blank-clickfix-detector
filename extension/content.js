(() => {
  if (globalThis.__blank_content) { globalThis.__blank_content.refresh(); return; }
  const blank_document = crypto.randomUUID();
  const blank_excluded = "input,textarea,select,option,script,style,noscript,template,[contenteditable]:not([contenteditable='false']),[hidden],[aria-hidden='true']";
  const blank_relevant = /verif|captcha|robot|repair|browser.{0,20}error|powershell|terminal|command|paste|ctrl\s*\+\s*v|win(?:dows)?(?:\s*key)?\s*(?:\+|and)?\s*[rx]|windows\s+run|run\s*(?:dialog|box)|press\s+enter|hit\s+enter|instruction\s+image|failedver|iex|iwr|bypass/i;
  let blank_revision = 0, blank_observer = null, blank_timer = null;
  let blank_snapshot_fingerprint = null;
  let blank_last_fingerprint = "", blank_last_call = 0, blank_inflight = false, blank_pending = false;
  let blank_warning = null, blank_dismissed = "";

  function blank_hidden(element) {
    const style = getComputedStyle(element);
    return style.display === "none" || style.visibility === "hidden" || style.visibility === "collapse" || style.opacity === "0";
  }

  function blank_snapshot(blocks, extraction) {
    // Read-only/unchanged extraction must not invalidate an in-flight result.
    const fingerprint = JSON.stringify([blocks, extraction.truncated]);
    if (fingerprint !== blank_snapshot_fingerprint) {
      blank_snapshot_fingerprint = fingerprint;
      blank_revision++;
    }
    return {blocks, extraction, document_key: blank_document, revision: blank_revision};
  }

  function blank_extract() {
    const buckets = new Map();
    let visited = 0, truncated = false, collected = 0;
    const root = document.body || document.documentElement;
    // TreeWalker never applies its filter to its own root. Check it and its ancestors explicitly.
    for (let ancestor = root; ancestor; ancestor = ancestor.parentElement) {
      if (ancestor.matches(blank_excluded) || blank_hidden(ancestor)) {
        return blank_snapshot([], {truncated: false, main_frame_only: true, visited_nodes: 0});
      }
    }
    // One bounded traversal; rejected subtrees cannot leak through parent textContent/innerText.
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        if (visited >= 6000) { truncated = true; return NodeFilter.FILTER_REJECT; }
        visited++;
        if (node.nodeType === Node.ELEMENT_NODE) {
          if (node === blank_warning || node.matches(blank_excluded) || blank_hidden(node)) return NodeFilter.FILTER_REJECT;
          if (node.tagName === "IMG") return NodeFilter.FILTER_ACCEPT;
          return NodeFilter.FILTER_SKIP;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    let node;
    while (visited < 6000 && (node = walker.nextNode())) {
      let value = "";
      let isImg = false;
      if (node.nodeType === Node.ELEMENT_NODE && node.tagName === "IMG") {
        isImg = true;
        const alt = (node.alt || "").trim();
        const title = (node.title || "").trim();
        const aria = (node.getAttribute("aria-label") || "").trim();
        const src = (node.src || "").split("/").pop().split("?")[0];
        const label = alt || title || aria;
        const isInstructionContext = Boolean(node.closest("[role=dialog],dialog,[class*='modal'],[class*='captcha'],[class*='verification'],[class*='challenge'],[class*='flow'],[class*='step']"));
        const hasInstructionKeywords = /(?:step\s*\d|instruct|verify|verification|captcha|robot|human|terminal|powershell|cmd|\bpress\b|\bpaste\b|guide|solve)/i.test(label || src);
        if (label || src) {
          if ((isInstructionContext || hasInstructionKeywords) && !/wordpress/i.test(label || src)) {
            value = `[Instruction Image: ${label || src}]`;
          } else {
            value = `[Image: ${label || src}]`;
          }
        }
      } else {
        value = node.textContent.slice(0, 24000).replace(/\s+/g, " ").trim();
      }
      if(node.textContent.length>24000) truncated=true;
      if (!value) continue;
      collected+=value.length;
      if(collected>96000) {truncated=true;break;}
      // Keep related verification widgets, steps, and instruction dialogs together.
      const parent = node.parentElement || node;
      const topContainer = parent.closest(
        "[role=dialog],dialog,[class*='modal'],[class*='captcha'],[class*='verification'],[class*='challenge'],[class*='cf-'],[class*='demo']"
      );
      const listContainer = parent.closest("ol,ul,[class*='flow'],[class*='wizard'],[class*='steps'],[class*='instructions'],[class*='inst']");
      const owner = topContainer || listContainer || parent.closest("article,section,main,[class*='card'],[class*='box']") || parent.closest("div") || parent;
      if (!buckets.has(owner)) buckets.set(owner, {segments: [],
        inside_dialog: Boolean(owner.closest("[role=dialog],dialog"))});
      const bucket = buckets.get(owner);
      bucket.segments.push({text:value,has_code:Boolean(parent.closest("pre,code")),
        has_copy_button:Boolean(parent.closest("button,[role=button]")&&/copy/i.test(value)),
        heading:Boolean(parent.closest('h1,h2,h3,h4,h5,h6')),
        structural:Boolean(isImg||parent.closest('ol,ul,button,[role=button],pre')||bucket.inside_dialog)});
    }
    if (visited >= 6000) truncated = true;
    const windows=[];
    for(const bucket of buckets.values()) {
      let text='',heading='',has_code=false,has_copy_button=false,structural=bucket.inside_dialog;
      const emit=()=>{if(text.trim()) windows.push({text:text.trim(),inside_dialog:bucket.inside_dialog,
        has_code,has_copy_button,structural});};
      for(const segment of bucket.segments) {
        if(segment.heading) heading=segment.text.slice(0,160);
        // Do not clip the start of an entire article. Keep bounded overlapping instruction windows.
        for(let offset=0;offset<segment.text.length;offset+=1600) {
          const part=segment.text.slice(offset,offset+1600);
          if(text.length+part.length+1>2000) {
            emit(); text=(heading+' '+text.slice(-180)).trim();
            has_code=false;has_copy_button=false;structural=bucket.inside_dialog;
          }
          text=(text+' '+part).trim();has_code ||=segment.has_code;
          has_copy_button ||=segment.has_copy_button;structural ||=segment.structural;
        }
      }
      emit();
    }
    const unique=[...new Map(windows.map(x=>[x.text,x])).values()];
    const keyword=unique.filter(x=>blank_relevant.test(x.text));
    const structural=unique.filter(x=>!blank_relevant.test(x.text)&&x.structural);
    keyword.sort((a,b)=>Number(b.inside_dialog)-Number(a.inside_dialog));
    structural.sort((a,b)=>Number(b.inside_dialog)-Number(a.inside_dialog));
    // Reserve six slots for non-keyword instruction structures; unused slots return to keyword blocks.
    const count=Math.min(6,structural.length);
    const candidates=[...keyword.slice(0,24-count),...structural.slice(0,count)];
    if(keyword.length+structural.length>candidates.length) truncated=true;
    const seen = new Set(), blocks = [];
    let total = 0;
    for (const candidate of candidates) {
      if (seen.has(candidate.text)) continue;
      seen.add(candidate.text);
      if (blocks.length >= 24 || total + candidate.text.length > 24000) { truncated = true; continue; }
      total += candidate.text.length;
      const {text, structural: _structural, ...context} = candidate;
      blocks.push({block_id: `block_${blocks.length}`, text, context});
    }
    return blank_snapshot(blocks, {truncated, main_frame_only: true, visited_nodes: Math.min(visited, 6000)});
  }

  function blank_show(result) {
    if (!["suspicious", "uncertain"].includes(result.verdict)) { blank_warning?.remove(); blank_warning = null; return; }
    // Do not display intrusive in-page warning banner on search engine results pages unless an active clipboard payload was detected
    const isSearchPage = /^(?:https?:\/\/)?(?:[a-z0-9-]+\.)*(?:google|bing|duckduckgo|yahoo|ecosia|baidu)\.[a-z.]+\/search/i.test(location.href);
    const hasClipPayload = (result.findings || []).some(f => f.code === "CLIPBOARD_MALICIOUS_COMMAND");
    if (isSearchPage && !hasClipPayload) {
      blank_warning?.remove();
      blank_warning = null;
      return;
    }
    // Traversal counts change when our own warning appears/disappears; that is not new evidence.
    const findingKeys = (result.findings || []).map(f => `${f.code}:${f.block_id}`).sort();
    const fingerprint = JSON.stringify([result.verdict, findingKeys, result.extraction?.truncated]);
    if (fingerprint === blank_dismissed) return;
    blank_warning?.remove();
    blank_warning = document.createElement("aside");
    blank_warning.setAttribute("data-blank-warning", "");
    blank_warning.style.cssText = "position:fixed;bottom:20px;left:20px;z-index:2147483647;max-width:min(440px,90vw)";
    const shadow = blank_warning.attachShadow({mode: "closed"});
    const style = document.createElement("style");
    style.textContent = `:host{color-scheme:dark}section{background:oklch(0.162 0.01 260);color:oklch(0.79 0.0011 260);border:1px solid ${result.verdict === "suspicious" ? "oklch(0.712 0.185 11.3)" : "oklch(0.837 0.14 75)"};border-radius:6px;padding:18px;box-shadow:0 8px 32px rgba(0,0,0,0.6);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}h2{font-family:"GT America Mono",monospace;font-size:12px;letter-spacing:0.06em;text-transform:uppercase;margin:0 0 8px;color:${result.verdict === "suspicious" ? "oklch(0.82 0.14 11.3)" : "oklch(0.837 0.14 75)"}}p{margin:8px 0;color:oklch(0.70 0.002 260)}blockquote{margin:10px 0;padding:8px 12px;background:oklch(0.12 0.012 260);border-left:2px solid ${result.verdict === "suspicious" ? "oklch(0.712 0.185 11.3)" : "oklch(0.837 0.14 75)"};border-radius:2px;font-family:monospace;font-size:12px;color:oklch(0.995 0.0001 260);white-space:pre-wrap;overflow-wrap:anywhere}button{background:oklch(0.19 0.009 260);color:oklch(0.79 0.0011 260);border:1px solid oklch(0.316 0.006 260);border-radius:2px;font-family:"GT America Mono",monospace;font-size:11px;letter-spacing:0.05em;text-transform:uppercase;padding:6px 12px;cursor:pointer}`;
    const panel = document.createElement("section");
    panel.setAttribute("role", result.verdict === "suspicious" ? "alert" : "status");
    const heading = document.createElement("h2");
    heading.textContent = `BLANK · ${result.verdict === "suspicious" ? "Suspicious instructions" : "Uncertain instructions"}`;
    const advice = document.createElement("p");
    advice.textContent = result.verdict === "suspicious" ? "Pause before following these instructions. Do not paste unfamiliar website commands into system tools." : "Review these instructions carefully. BLANK found ambiguous signals or incomplete page coverage.";
    panel.append(heading, advice);
    for (const finding of (result.findings || []).slice(0, 2)) {
      const reason = document.createElement("p"), quote = document.createElement("blockquote");
      reason.textContent = finding.message;
      quote.textContent = finding.evidence.slice(0, 350);
      panel.append(reason, quote);
    }
    const dismiss = document.createElement("button");
    dismiss.textContent = "Dismiss warning";
    dismiss.onclick = () => { blank_dismissed = fingerprint; blank_warning?.remove(); blank_warning = null; };
    panel.append(dismiss);
    shadow.append(style, panel);
    document.documentElement.append(blank_warning);
  }

  function blank_schedule() {
    blank_pending = true;
    clearTimeout(blank_timer);
    blank_timer = setTimeout(blank_auto, Math.max(1000, 5000 - (Date.now() - blank_last_call)));
  }

  async function blank_auto() {
    if (!blank_observer) return;
    if (blank_inflight) { blank_pending = true; return; }
    blank_pending = false;
    const extracted = blank_extract();
    const fingerprint = JSON.stringify([extracted.blocks, extracted.extraction.truncated]);
    if (fingerprint === blank_last_fingerprint) return;
    blank_inflight = true;
    blank_last_call = Date.now();
    try {
      const result = await chrome.runtime.sendMessage({type: "blank_auto_scan", extracted});
      if (!result?.skipped && !result?.error && result?.verdict !== "scan_unavailable") blank_last_fingerprint = fingerprint;
      if (result?.skipped) blank_pending = true;
    } catch { /* Extension may have been reloaded; no page data is logged. */ }
    finally { blank_inflight = false; if (blank_pending) blank_schedule(); }
  }

  async function blank_refresh() {
    try {
      const status = await chrome.runtime.sendMessage({type: "blank_auto_status"});
      if (!status?.enabled) {
        blank_observer?.disconnect(); blank_observer = null; clearTimeout(blank_timer); return;
      }
      if (blank_observer) return;
      blank_observer = new MutationObserver(mutations => {
        const relevant = mutations.some(m => {
          if (m.target === blank_warning || blank_warning?.contains(m.target)) return false;
          const changed = [...m.addedNodes, ...m.removedNodes];
          return !changed.length || changed.some(n => n !== blank_warning);
        });
        if (relevant) blank_schedule();
      });
      blank_observer.observe(document.documentElement, {childList: true, subtree: true, characterData: true,
        attributes: true, attributeFilter: ["class", "style", "hidden", "aria-hidden"]});
      blank_schedule();
    } catch { /* No automatic access without an affirmative worker response. */ }
  }

  chrome.runtime.onMessage.addListener((message, sender, reply) => {
    if (sender.id !== chrome.runtime.id) return;
    if (message.type === "blank_document") { reply({document_key: blank_document}); return; }
    if (message.type === "blank_extract") { reply(blank_extract()); return; }
    if (message.type === "blank_result" && message.document_key === blank_document && message.revision === blank_revision) {
      if (message.automatic && !blank_observer) { reply({displayed: false}); return; }
      blank_show(message.result); reply({displayed: true});
    }
    if (message.type === "blank_refresh_auto") { blank_refresh(); reply({ok: true}); }
  });
  globalThis.__blank_content = {refresh: blank_refresh};
  blank_refresh();
})();
