"""Exploratory, grouped BLANK AI comparison. Does not replace the released model."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from backend.config import ROOT
from backend.features import normalize_with_offsets
from backend.rules import match_rules
from backend.schemas import Block
from ml.dataset import dataset_hash, load_dataset, split_records, validate_splits
from ml.evaluate import metrics
from ml.semantic import MODEL_ID, encode_blocks
from ml.train import choose_threshold


def summarize(rows, verdicts, latencies):
    y = [int(r["label"] == "clickfix") for r in rows]
    return {"strict": metrics(y, [int(v == "suspicious") for v in verdicts]),
            "all_warnings": metrics(y, [int(v != "no_suspicious_signals") for v in verdicts]),
            "uncertain_rate": sum(v == "uncertain" for v in verdicts) / len(rows),
            "decision_coverage": sum(v != "uncertain" for v in verdicts) / len(rows),
            "latency_ms": {"median": float(np.median(latencies)), "p95": float(np.percentile(latencies, 95))},
            "outcomes": [{"id": r["id"], "label": r["label"], "verdict": v,
                          "correct_strict": (v == "suspicious") == (r["label"] == "clickfix")}
                         for r, v in zip(rows, verdicts)],
            "subsets": {kind: sum(r["synthetic"] == synthetic for r in rows)
                        for kind, synthetic in (("synthetic", True), ("sourced_or_recreated", False))}}


def decisions(rows, scores, threshold, hybrid=False, use_context=True, truncated=None):
    verdicts = []
    for i, (row, score) in enumerate(zip(rows, scores)):
        rule = match_rules(Block(block_id="benchmark", text=row["text"], context=row.get("context", {})),
                           use_context=use_context)
        high = threshold is not None and score >= threshold
        if not hybrid:
            verdict = "suspicious" if high else "uncertain" if score >= 0.5 else "no_suspicious_signals"
        else:
            verdict = rule.verdict
            if verdict != "suspicious" and high and rule.execution_lure and not any(
                    f.code == "CONFLICTING_EDUCATIONAL_CONTEXT" for f in rule.findings):
                verdict = "suspicious"
            elif verdict == "no_suspicious_signals" and score >= 0.5:
                verdict = "uncertain"
        if truncated and truncated[i] and verdict != "suspicious":
            verdict = "uncertain"
        verdicts.append(verdict)
    return verdicts


def bootstrap_recall_delta(rows, baseline, candidate):
    """Family bootstrap, descriptive interval; not a claim of independent field efficacy."""
    groups = sorted({r["template_group"] for r in rows})
    rng = np.random.default_rng(42)
    deltas = []
    for _ in range(1000):
        selected = rng.choice(groups, size=len(groups), replace=True)
        indices = [i for g in selected for i, r in enumerate(rows) if r["template_group"] == g
                   and r["label"] == "clickfix"]
        if indices:
            deltas.append(np.mean([candidate[i] == "suspicious" for i in indices]) -
                          np.mean([baseline[i] == "suspicious" for i in indices]))
    return [float(v) for v in np.percentile(deltas, [2.5, 97.5])] if deltas else None


def benchmark(data: Path, output: Path, semantic=True):
    output.mkdir(parents=True, exist_ok=True)
    rows = load_dataset(data)
    fingerprint = dataset_hash(data)
    split_path = output / "splits.json"
    if split_path.exists():
        saved = json.loads(split_path.read_text())
        if saved["dataset_sha256"] != fingerprint:
            raise ValueError("Use a new experiment directory when the dataset changes")
        splits = saved["splits"]
    else:
        splits = split_records(rows)
        split_path.write_text(json.dumps({"dataset_sha256": fingerprint, "splits": splits}, indent=2))
    validate_splits(rows, splits)
    indices = {name: [i for i, r in enumerate(rows) if r["id"] in ids] for name, ids in splits.items()}
    train_rows = [rows[i] for i in indices["train"]]
    validation = [rows[i] for i in indices["validation"]]
    tests = [rows[i] for i in indices["test"]]
    texts = [normalize_with_offsets(r["text"])[0] for r in rows]
    labels = [r["label"] for r in train_rows]
    report = {"research_status": "exploratory; no real-world or human-review claim",
              "dataset_sha256": fingerprint, "split_ids": splits, "seed": 42,
              "human_reviewed_count": sum(r.get("review_status") == "human_reviewed" for r in rows),
              "family_count": len({r["template_group"] for r in rows}),
              "environment": {"python": platform.python_version(), "platform": platform.platform()},
              "versions": {p: importlib.metadata.version(p) for p in ("numpy", "scikit-learn", "joblib")},
              "results": {}, "validation": {}, "cloud": {p: {"status": "not_performed",
              "reason": "No user key supplied; live calls are explicit opt-in, never part of default benchmark"}
              for p in ("groq", "gemini")}}
    candidates = {}
    for name, features in {
        "word": TfidfVectorizer(ngram_range=(1, 2), max_features=10000),
        "word_char": FeatureUnion([("word", TfidfVectorizer(ngram_range=(1, 2), max_features=10000)),
                                   ("char", TfidfVectorizer(analyzer="char", ngram_range=(3, 5), max_features=15000))]),
    }.items():
        print("Training", name, flush=True)
        pipeline = Pipeline([("features", features), ("classifier", LogisticRegression(C=1, max_iter=1000, random_state=42))])
        pipeline.fit([texts[i] for i in indices["train"]], labels)
        scores, latencies = [], []
        for text in texts:
            start = time.perf_counter()
            scores.append(float(pipeline.predict_proba([text])[0, list(pipeline.classes_).index("clickfix")]))
            latencies.append((time.perf_counter() - start) * 1000)
        candidates[name] = (scores, latencies, [False] * len(rows))
        joblib.dump(pipeline, output / f"{name}.joblib")
    if semantic:
        import torch
        from huggingface_hub import HfApi, snapshot_download
        from sentence_transformers import SentenceTransformer
        from setfit import SetFitModel, Trainer, TrainingArguments
        from datasets import Dataset

        torch.set_num_threads(4)
        revision_path = output / "upstream.json"
        revision = json.loads(revision_path.read_text())["revision"] if revision_path.exists() else HfApi().model_info(MODEL_ID).sha
        revision_path.write_text(json.dumps({"model": MODEL_ID, "revision": revision}, indent=2))
        print("Downloading pinned encoder", revision, flush=True)
        snapshot = snapshot_download(MODEL_ID, revision=revision, local_dir=output / "upstream_model",
                                     allow_patterns=["*.json", "*.txt", "*.safetensors", "1_Pooling/*", "2_Normalize/*", "README.md"])
        body = SentenceTransformer(snapshot, device="cpu", trust_remote_code=False)
        body.max_seq_length = 256
        for name in ("minilm_frozen", "minilm_setfit"):
            start = time.perf_counter()
            if name == "minilm_setfit":
                print("Fine-tuning SetFit (200 optimizer steps maximum)", flush=True)
                fitted = SetFitModel.from_pretrained(snapshot, device="cpu", trust_remote_code=False)
                args = TrainingArguments(batch_size=16, num_iterations=10, max_steps=200,
                                         seed=42, report_to="none", logging_steps=50)
                training = Dataset.from_dict({"text": [texts[i] for i in indices["train"]],
                                              "label": [int(v == "clickfix") for v in labels]})
                Trainer(model=fitted, args=args, train_dataset=training).train()
                body = fitted.model_body
                body.max_seq_length = 256
            vectors, cuts, latencies = [], [], []
            for text in texts:
                tick = time.perf_counter()
                vector, cut = encode_blocks(body, [text])
                vectors.append(vector[0])
                cuts.extend(cut)
                latencies.append((time.perf_counter() - tick) * 1000)
            vectors = np.asarray(vectors)
            classifier = LogisticRegression(C=1, max_iter=1000, random_state=42).fit(vectors[indices["train"]], labels)
            scores = classifier.predict_proba(vectors)[:, list(classifier.classes_).index("clickfix")].tolist()
            candidates[name] = (scores, latencies, cuts)
            body.save_pretrained(str(output / name))
            joblib.dump(classifier, output / f"{name}.joblib")
            report.setdefault("training", {})[name] = {"duration_seconds": time.perf_counter() - start,
                "source_revision": revision, "max_tokens": 256, "overlap": 32, "max_windows": 8,
                "batch_size": 16, "num_iterations": 10 if name.endswith("setfit") else 0,
                "max_optimizer_steps": 200 if name.endswith("setfit") else 0}
        report["versions"].update({p: importlib.metadata.version(p) for p in
                                   ("torch", "sentence-transformers", "setfit", "transformers", "huggingface-hub")})
    baseline = None
    semantic_selection = []
    for name, (scores, latencies, cuts) in candidates.items():
        val_scores = [scores[i] for i in indices["validation"]]
        thresholds = {mode: choose_threshold(validation, val_scores, mode)
                      for mode in ("ml", "hybrid", "hybrid_no_context")}
        report["validation"][name] = {"thresholds": thresholds}
        for mode in ("ml", "hybrid", "hybrid_no_context"):
            val_verdicts = decisions(validation, val_scores, thresholds[mode], mode != "ml", mode != "hybrid_no_context")
            if mode == "hybrid":
                val_summary = summarize(validation, val_verdicts, [latencies[i] for i in indices["validation"]])
                report["validation"][name]["hybrid"] = val_summary
                if name.startswith("minilm"):
                    m = val_summary["strict"]
                    semantic_selection.append((m["recall"], m["precision"], name == "minilm_frozen", name))
            verdicts = decisions(tests, [scores[i] for i in indices["test"]], thresholds[mode], mode != "ml",
                                 mode != "hybrid_no_context", [cuts[i] for i in indices["test"]])
            result = summarize(tests, verdicts, [latencies[i] for i in indices["test"]])
            for outcome, i in zip(result["outcomes"], indices["test"]):
                outcome.update(score=scores[i], semantic_truncated=cuts[i])
            if name == "word" and mode == "hybrid":
                baseline = verdicts
            if baseline is not None:
                result["recall_delta_family_bootstrap_95pct"] = bootstrap_recall_delta(tests, baseline, verdicts)
            report["results"][f"{name}_{mode}"] = result
    for use_context in (True, False):
        ticks, verdicts = [], []
        for row in tests:
            start = time.perf_counter()
            verdicts.append(match_rules(Block(block_id="r", text=row["text"], context=row.get("context", {})), use_context).verdict)
            ticks.append((time.perf_counter() - start) * 1000)
        report["results"]["rules" if use_context else "rules_no_context"] = summarize(tests, verdicts, ticks)
    report["semantic_selection"] = max(semantic_selection)[-1] if semantic_selection else None
    report["selection_basis"] = "validation hybrid recall, precision, then frozen-model resource preference; no test tuning"
    report["promotion"] = {"eligible": False, "reason": "Reviewed representative data and release gates not established"}
    report["artifact_hashes"] = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in output.rglob("*") if p.is_file() and p.suffix in {".joblib", ".safetensors"}}
    (output / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Saved comparison; selected experimental semantic candidate:", report["semantic_selection"], flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/seed.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/seed-ai")
    parser.add_argument("--lexical-only", action="store_true")
    args = parser.parse_args()
    benchmark(args.data, args.output, not args.lexical_only)


if __name__ == "__main__":
    main()
