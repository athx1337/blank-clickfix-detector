import hashlib
import json
import re
import time
from pathlib import Path

import joblib
import sklearn

from backend.features import extract_features, normalize_with_offsets
from backend.rules import match_rules
from backend.schemas import AnalyzeRequest, AnalyzeResponse, Finding

RANK = {"no_suspicious_signals": 0, "uncertain": 1, "suspicious": 2}


class Detector:
    def __init__(self, model_dir: Path | None = None):
        self.pipeline = None
        self.metadata = None
        self.model_reason = "No trusted local model loaded"
        if model_dir is not None:
            self.load_model(model_dir)

    def load_model(self, directory):
        try:
            metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
            path = directory / "blank.joblib"
            if metadata["sklearn_version"] != sklearn.__version__:
                raise ValueError("incompatible model")
            if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["artifact_sha256"]:
                raise ValueError("artifact integrity mismatch")
            # Only use this fixed locally generated path. Hashes do not make untrusted pickle safe.
            self.pipeline = joblib.load(path)
            self.metadata = metadata
            self.model_reason = None
        except (OSError, ValueError, KeyError, EOFError, TypeError):
            self.pipeline = None
            self.metadata = None
            self.model_reason = "Model missing, corrupt, or incompatible; rules only"

    def score(self, text):
        normalized, _ = normalize_with_offsets(text)
        index = list(self.pipeline.classes_).index("clickfix")
        return float(self.pipeline.predict_proba([normalized])[0, index])

    def model_terms(self, text):
        vectorizer = self.pipeline.named_steps["tfidf"]
        classifier = self.pipeline.named_steps["classifier"]
        row = vectorizer.transform([normalize_with_offsets(text)[0]])
        # sklearn binary coefficients point toward classes_[1].
        sign = 1 if classifier.classes_[1] == "clickfix" else -1
        contributions = row.multiply(classifier.coef_[0] * sign).tocoo()
        names = vectorizer.get_feature_names_out()
        return [names[col] for col, value in sorted(zip(contributions.col, contributions.data),
                                                  key=lambda pair: -pair[1])[:3] if value > 0]

    def analyze(self, request: AnalyzeRequest, use_context=True, mode="hybrid"):
        start = time.perf_counter()
        findings, verdicts, scores = [], [], {}
        use_ml = self.pipeline is not None and mode != "rules"
        for block in request.blocks:
            rule = match_rules(block, use_context=use_context)
            verdict = rule.verdict if mode != "ml" else "no_suspicious_signals"
            if mode != "ml":
                findings.extend(rule.findings)
            if use_ml:
                score = self.score(block.text)  # failures propagate; never become a clean result
                scores[block.block_id] = round(score, 6)
                threshold = self.metadata["thresholds"]["ml" if mode == "ml" else
                                                        "hybrid" if use_context else "hybrid_no_context"]
                high = threshold is not None and score >= threshold
                if mode == "ml":
                    verdict = "suspicious" if high else "uncertain" if score >= 0.5 else "no_suspicious_signals"
                elif verdict != "suspicious" and high and rule.execution_lure and not any(
                    x.code == "CONFLICTING_EDUCATIONAL_CONTEXT" for x in rule.findings
                ):
                    verdict = "suspicious"
                elif verdict == "no_suspicious_signals" and score >= 0.5:
                    verdict = "uncertain"
                if score >= 0.5:
                    terms = ", ".join(self.model_terms(block.text)) or "no positive text features"
                    findings.append(Finding(code="MODEL_TEXT_SIMILARITY", block_id=block.block_id,
                                            message=f"Uncalibrated classifier score {score:.3f}; contributing terms: {terms}.",
                                            evidence=block.text[:600]))
            verdicts.append(verdict)
        verdict = max(verdicts, key=lambda value: RANK[value], default="no_suspicious_signals")
        if verdict != "suspicious" and len(request.blocks) > 1:
            combined_text = " ".join(b.text for b in request.blocks)
            combined_f = extract_features(combined_text)
            c_lure = combined_f.has("verification") or combined_f.has("repair")
            c_seq = combined_f.has("system") and combined_f.has("paste") and combined_f.has("execute")
            c_run_seq = combined_f.has("run_dialog") and combined_f.has("paste") and combined_f.has("execute")
            c_cmd_seq = combined_f.has("command") and combined_f.has("paste") and combined_f.has("execute")
            any_dialog = any(b.context.inside_dialog for b in request.blocks)
            if not combined_f.has("negation") and not (combined_f.has("reporting") and not any_dialog):
                if (c_lure and c_seq) or c_run_seq or c_cmd_seq:
                    verdict = "suspicious"
                    findings.insert(0, Finding(
                        code="SUSPICIOUS_MULTI_STEP_EXECUTION_SEQUENCE",
                        message="Multi-step instructions request opening Windows Run / PowerShell, pasting code, and executing it.",
                        block_id=request.blocks[0].block_id,
                        evidence=combined_text[:600]
                    ))
        if request.extraction.truncated and verdict != "suspicious":
            verdict = "uncertain"
        if request.clipboard and request.clipboard.strip():
            clip_text = request.clipboard.strip()
            clip_f = extract_features(clip_text)
            is_cmd = clip_f.has("command")
            is_sys = clip_f.has("system")
            is_script = bool(re.search(r"(?:powershell|cmd(?:\.exe)?|mshta|bash|sh|wscript|cscript|certutil|rundll32|regsvr32)\b", clip_text, re.I))
            has_flags = bool(re.search(r"-(?:enc|ep|executionpolicy|nop|w\s+hidden|c)\b|iex|iwr|irm|downloadstring|http", clip_text, re.I))
            if is_cmd or (is_sys and is_script) or (is_script and has_flags):
                findings.insert(0, Finding(
                    code="CLIPBOARD_MALICIOUS_COMMAND",
                    message="Clipboard contains an executable system command (often silently copied by ClickFix scams).",
                    block_id="clipboard",
                    evidence=clip_text[:300]
                ))
                verdict = "suspicious"
        return AnalyzeResponse(scan_id=request.scan_id, verdict=verdict,
                               detector_mode="hybrid" if use_ml else "rules_only", findings=findings,
                               model_version=self.metadata["model_version"] if use_ml else None,
                               model_scores=scores if use_ml else None,
                               processing_ms=round((time.perf_counter() - start) * 1000, 3),
                               block_count=len(request.blocks), extraction=request.extraction)
