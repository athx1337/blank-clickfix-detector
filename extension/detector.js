/* BLANK local inference. No execution, network calls, or third-party runtime.
 * English rule patterns: MIT ClickFixMitigator (Jordi Serrano, 2026).
 * Bounded excerpts: Apache-2.0 ClickGrab adaptation. See THIRD_PARTY_NOTICES.txt.
 */
(() => {
  "use strict";
  const rank = {no_suspicious_signals: 0, uncertain: 1, suspicious: 2};
  const own = (value, keys) => value && typeof value === "object" && !Array.isArray(value) &&
    Object.keys(value).every(key => keys.includes(key));
  const validId = value => typeof value === "string" && /^[a-zA-Z0-9_-]{1,64}$/.test(value);
  const length = value => Array.from(value).length;
  function normalize(text) {
    let normalized = "", raw = 0;
    const offsets = [];
    for (const char of text) {
      if (!"\u200b\u200c\u200d\ufeff\u2060".includes(char)) {
        const converted = char.normalize("NFKC").toLowerCase();
        normalized += converted;
        for (let i = 0; i < converted.length; i++) offsets.push([raw, raw + char.length]);
      }
      raw += char.length;
    }
    return {normalized, offsets};
  }
  function validate(request) {
    if (!own(request, ["scan_id", "blocks", "extraction", "clipboard"]) || !validId(request.scan_id) ||
        !Array.isArray(request.blocks) || request.blocks.length > 24) throw Error("Invalid scan input.");
    if (request.clipboard !== undefined && (typeof request.clipboard !== "string" || length(request.clipboard) > 4000)) {
      throw Error("Invalid clipboard input.");
    }
    const ids = new Set(); let total = 0;
    for (const b of request.blocks) {
      if (!own(b, ["block_id", "text", "context"]) || !validId(b.block_id) || ids.has(b.block_id) ||
          typeof b.text !== "string" || !length(b.text) || length(b.text) > 2000) throw Error("Invalid instruction block.");
      ids.add(b.block_id); total += length(b.text);
      if (b.context !== undefined && (!own(b.context, ["inside_dialog", "has_code", "has_copy_button"]) ||
          Object.values(b.context).some(value => typeof value !== "boolean"))) throw Error("Invalid block context.");
    }
    if (total > 24000) throw Error("Extraction exceeded text limits.");
    const e = request.extraction === undefined ? {} : request.extraction;
    if (!own(e, ["truncated", "main_frame_only", "visited_nodes"]) ||
        ["truncated", "main_frame_only"].some(k => k in e && typeof e[k] !== "boolean") ||
        ("visited_nodes" in e && (!Number.isInteger(e.visited_nodes) || e.visited_nodes < 0 || e.visited_nodes > 6000))) {
      throw Error("Invalid extraction metadata.");
    }
    return {truncated: false, main_frame_only: true, visited_nodes: 0, ...e};
  }
  class BlankDetector {
    constructor(rules, model) {
      if (rules?.schema_version !== 1 || !own(rules.patterns,
          ["verification", "repair", "system", "paste", "execute", "command", "reporting", "negation", "run_dialog"]) ||
          Object.keys(rules.patterns).length !== 9) throw Error("Bundled rules unavailable.");
      this.patterns = Object.fromEntries(Object.entries(rules.patterns).map(([key, value]) => {
        if (typeof value !== "string" || value.length > 2000) throw Error("Invalid bundled rule.");
        // Python word boundaries include Unicode letters/numbers; JS \\b does not.
        const word = "[\\p{L}\\p{N}_]";
        const boundary = `(?:(?<=${word})(?!${word})|(?<!${word})(?=${word}))`;
        return [key, new RegExp(value.replaceAll("\\b", boundary), "gisu")];
      }));
      this.model = null;
      const finite = values => Array.isArray(values) && values.every(Number.isFinite);
      if (model?.schema_version === 1 && model.policy_version === "blank-policy-1" &&
          typeof model.model_version === "string" && Array.isArray(model.terms) &&
          model.terms.length > 0 && model.terms.length <= 10000 &&
          model.terms.every(t => typeof t === "string" && t.length <= 4000) &&
          new Set(model.terms).size === model.terms.length && finite(model.weights) && finite(model.idf) &&
          model.weights.length === model.terms.length && model.idf.length === model.terms.length &&
          model.idf.every(n => n > 0) && Number.isFinite(model.intercept) &&
          ["ml", "hybrid", "hybrid_no_context"].every(k => model.thresholds && k in model.thresholds &&
            (model.thresholds[k] === null || (Number.isFinite(model.thresholds[k]) && model.thresholds[k] >= 0 && model.thresholds[k] <= 1)))) {
        this.model = model;
        this.vocabulary = new Map(model.terms.map((term, i) => [term, i]));
      }
    }
    rules(block) {
      const {normalized, offsets} = normalize(block.text);
      const matches = Object.fromEntries(Object.entries(this.patterns).map(([key, regex]) =>
        [key, [...normalized.matchAll(regex)].map(m => [m.index, m.index + m[0].length])]));
      for (const key of ["verification", "repair"]) matches[key] = matches[key].filter(([start]) =>
        !/\b(?:no|without|fake|mock|simulate|simulated|about|test|understand|learn\s+about)\s+(?:(?:verification|browser|captcha|clickfix|or|a|any|the|fake)\s+){0,5}$/i.test(normalized.slice(Math.max(0, start - 80), start)));
      const has = key => matches[key].length > 0;
      const findings = [], dialog = Boolean(block.context?.inside_dialog);
      const passage = keys => {
        const spans = keys.filter(has).map(k => matches[k][0]);
        if (!spans.length) return Array.from(block.text).slice(0, 600).join("");
        const start = offsets[Math.min(...spans.map(s => s[0]))][0];
        const end = offsets[Math.max(...spans.map(s => s[1])) - 1][1];
        // Slice by code points, matching Python raw excerpt bounds even before emoji.
        const chars = Array.from(block.text), left = Math.max(0, length(block.text.slice(0, start)) - 50);
        return chars.slice(left, Math.min(chars.length, length(block.text.slice(0, end)) + 50, left + 600)).join("");
      };
      const add = (code, message, keys) => findings.push({code, message, block_id: block.block_id, evidence: passage(keys)});
      const lure = has("verification") || has("repair"), sequence = has("system") && has("paste") && has("execute");
      const runSequence = has("run_dialog") && has("paste") && has("execute");
      if (has("negation") && !dialog) return {verdict: "no_suspicious_signals", findings, execution_lure: false};
      let strong = false;
      if (has("verification") && sequence) {
        strong = true; add("VERIFICATION_WITH_SYSTEM_EXECUTION", "Verification instructions request system command execution.", ["verification", "system", "paste", "execute"]);
      }
      if (has("repair") && sequence) {
        strong = true; add("REPAIR_WITH_PASTE_AND_RUN", "Browser repair instructions request pasting and running a command.", ["repair", "system", "paste", "execute"]);
      }
      if (has("command") && has("paste") && has("execute")) {
        strong = true; add("SUSPICIOUS_COMMAND_IN_INSTRUCTION_CONTEXT", "Execution instructions include a risky command pattern.", ["command", "paste", "execute"]);
      }
      if (!lure && runSequence) {
        strong = true; add("SUSPICIOUS_SYSTEM_EXECUTION_SEQUENCE", "Instructions request opening Windows Run, pasting clipboard content, and executing it.", ["run_dialog", "paste", "execute"]);
      }
      if (lure && has("system") && has("paste") && dialog && block.context?.has_copy_button) {
        strong = true; add("DIALOG_LURE_WITH_COPY_AND_SYSTEM_PASTE", "A verification or repair dialog combines copying and system paste instructions.", ["system", "paste"]);
      }
      const hasImg = /\[Instruction Image:\s*[^\]]+\]/i.test(block.text);
      const hasImgInstructions = /\[Instruction Image:\s*[^\]]*(?:step\s*\d|powershell|cmd(?:\.exe)?|terminal|shortcut|\bpress\b|\bpaste\b|\bexecute\b|run\s+command)[^\]]*\]/i.test(block.text);
      if (has("verification") && hasImg) {
        if (dialog || block.context?.has_copy_button || has("system") || has("paste") || hasImgInstructions) {
          strong = true; add("INSTRUCTION_IMAGE_VERIFICATION_LURE", "Verification instructions display an instructional image to evade text inspection.", ["verification"]);
        }
      }
      if (strong && has("reporting") && !dialog) {
        add("CONFLICTING_EDUCATIONAL_CONTEXT", "The passage may be reporting an attack rather than requesting it.", ["reporting"]);
        return {verdict: "uncertain", findings, execution_lure: true};
      }
      if (strong) return {verdict: "suspicious", findings, execution_lure: true};
      const partial = lure && has("system");
      if (partial) add("PARTIAL_SYSTEM_EXECUTION_LURE", "A verification or repair claim refers to a system command interface.", ["verification", "repair", "system"]);
      return {verdict: partial ? "uncertain" : "no_suspicious_signals", findings, execution_lure: partial};
    }
    predict(text) {
      const tokens = normalize(text).normalized.match(/[\p{L}\p{N}_]{2,}/gu) || [];
      const counts = new Map();
      const add = term => {const index = this.vocabulary.get(term); if (index !== undefined) counts.set(index, (counts.get(index) || 0) + 1);};
      tokens.forEach(add);
      for (let i = 1; i < tokens.length; i++) add(tokens[i - 1] + " " + tokens[i]);
      const values = [...counts].map(([i, count]) => [i, count * this.model.idf[i]]);
      const norm = Math.sqrt(values.reduce((sum, [, value]) => sum + value * value, 0)) || 1;
      const contributions = values.map(([i, value]) => [i, value / norm * this.model.weights[i]]);
      const logit = this.model.intercept + contributions.reduce((sum, [, v]) => sum + v, 0);
      const score = 1 / (1 + Math.exp(-logit));
      if (!Number.isFinite(score)) throw Error("Local inference failed.");
      const terms = contributions.sort((a, b) => b[1] - a[1] || a[0] - b[0]).slice(0, 3).filter(([, v]) => v > 0).map(([i]) => this.model.terms[i]);
      return {score, terms};
    }
    analyze(request) {
      const start = performance.now(), extraction = validate(request), findings = [], scores = Object.create(null);
      let verdict = "no_suspicious_signals";
      for (const block of request.blocks) {
        const rule = this.rules(block); let decision = rule.verdict;
        findings.push(...rule.findings);
        if (this.model) {
          const {score, terms} = this.predict(block.text);
          scores[block.block_id] = Number(score.toFixed(6));
          const threshold = this.model.thresholds.hybrid;
          if (decision !== "suspicious" && threshold !== null && score >= threshold && rule.execution_lure &&
              !rule.findings.some(f => f.code === "CONFLICTING_EDUCATIONAL_CONTEXT")) decision = "suspicious";
          else if (decision === "no_suspicious_signals" && score >= 0.5) decision = "uncertain";
          if (score >= 0.5) findings.push({code: "MODEL_TEXT_SIMILARITY", block_id: block.block_id,
            message: `Uncalibrated classifier score ${score.toFixed(3)}; contributing terms: ${terms.join(", ") || "no positive text features"}.`,
            evidence: Array.from(block.text).slice(0, 600).join("")});
        }
        if (rank[decision] > rank[verdict]) verdict = decision;
      }
      if (verdict !== "suspicious" && request.blocks.length > 1) {
        const combinedText = request.blocks.map(b => b.text).join(" ");
        const { normalized } = normalize(combinedText);
        const matches = Object.fromEntries(Object.entries(this.patterns).map(([key, regex]) => {
          let list = [...normalized.matchAll(regex)].map(m => [m.index, m.index + m[0].length]);
          if (["verification", "repair"].includes(key)) {
            list = list.filter(([start]) =>
              !/\b(?:no|without|fake|mock|simulate|simulated|about|test|understand|learn\s+about)\s+(?:(?:verification|browser|captcha|clickfix|or|a|any|the|fake)\s+){0,5}$/i.test(normalized.slice(Math.max(0, start - 80), start)));
          }
          return [key, list.length > 0];
        }));
        const cLure = matches.verification || matches.repair;
        const cSeq = matches.system && matches.paste && matches.execute;
        const cRunSeq = matches.run_dialog && matches.paste && matches.execute;
        const cCmdSeq = matches.command && matches.paste && matches.execute;
        const anyDialog = request.blocks.some(b => b.context?.inside_dialog);
        if (!matches.negation && !(matches.reporting && !anyDialog)) {
          if ((cLure && cSeq) || cRunSeq || cCmdSeq) {
            verdict = "suspicious";
            findings.unshift({
              code: "SUSPICIOUS_MULTI_STEP_EXECUTION_SEQUENCE",
              message: "Multi-step instructions request opening Windows Run / PowerShell, pasting code, and executing it.",
              block_id: request.blocks[0].block_id,
              evidence: Array.from(combinedText).slice(0, 600).join("")
            });
          }
        }
      }
      if (extraction.truncated && verdict !== "suspicious") verdict = "uncertain";
      if (request.clipboard && typeof request.clipboard === "string" && request.clipboard.trim()) {
        const clipText = request.clipboard.trim();
        const { normalized } = normalize(clipText);
        const matchesCmd = this.patterns.command && this.patterns.command.test(normalized);
        const matchesSys = this.patterns.system && this.patterns.system.test(normalized);
        const isScript = /(?:powershell|cmd(?:\.exe)?|mshta|bash|sh|wscript|cscript|certutil|rundll32|regsvr32)\b/i.test(clipText);
        const hasFlags = /-(?:enc|ep|executionpolicy|nop|w\s+hidden|c)\b|iex|iwr|irm|downloadstring|http/i.test(clipText);
        if (matchesCmd || (matchesSys && isScript) || (isScript && hasFlags)) {
          findings.unshift({
            code: "CLIPBOARD_MALICIOUS_COMMAND",
            message: "Clipboard contains an executable system command (often silently copied by ClickFix scams).",
            block_id: "clipboard",
            evidence: clipText.slice(0, 300)
          });
          verdict = "suspicious";
        }
      }
      return {scan_id: request.scan_id, verdict, findings, detector_mode: this.model ? "hybrid" : "rules_only",
        model_version: this.model?.model_version ?? null, model_scores: this.model ? scores : null,
        processing_ms: Number((performance.now() - start).toFixed(3)), block_count: request.blocks.length, extraction};
    }
  }
  globalThis.BlankDetector = BlankDetector;
})();
