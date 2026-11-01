import argparse
import json
import platform
import statistics
from pathlib import Path

import numpy as np
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from backend.config import ROOT
from backend.detector import Detector
from backend.schemas import AnalyzeRequest
from ml.dataset import dataset_hash, load_dataset, validate_splits


def metrics(labels, predictions):
    precision, recall, f1, _ = precision_recall_fscore_support(labels, predictions, average="binary", zero_division=0)
    matrix = confusion_matrix(labels, predictions, labels=[0, 1]).tolist()
    tn, fp = matrix[0]
    return {"precision": round(float(precision), 4), "recall": round(float(recall), 4),
            "f1": round(float(f1), 4), "confusion_matrix": matrix,
            "matrix_order": "[[TN, FP], [FN, TP]]", "false_positive_rate": fp / (tn + fp) if tn + fp else None}


def evaluate(data: Path, model_dir: Path):
    rows = load_dataset(data)
    manifest = json.loads((model_dir / "splits.json").read_text(encoding="utf-8"))
    detector = Detector(model_dir)
    if detector.pipeline is None:
        raise ValueError("Train a trusted local model before evaluation")
    fingerprint = dataset_hash(data)
    if manifest["dataset_sha256"] != fingerprint or detector.metadata["dataset_sha256"] != fingerprint:
        raise ValueError("Dataset/model/split mismatch; refusing to fabricate a new test set")
    validate_splits(rows, manifest["splits"])
    held_out = [r for r in rows if r["id"] in manifest["splits"]["test"]]
    results = {}
    for mode in ("rules", "ml", "hybrid", "hybrid_no_context"):
        predictions, verdicts, latencies, errors = [], [], [], []
        for row in held_out:
            request = AnalyzeRequest(scan_id="evaluation", blocks=[{
                "block_id": row["id"], "text": row["text"], "context": row.get("context", {})
            }])
            response = detector.analyze(request, use_context=mode != "hybrid_no_context",
                                        mode="hybrid" if mode == "hybrid_no_context" else mode)
            predicted = int(response.verdict == "suspicious")
            actual = int(row["label"] == "clickfix")
            predictions.append(predicted)
            verdicts.append(response.verdict)
            latencies.append(response.processing_ms)
            if predicted != actual:
                errors.append({"id": row["id"], "kind": "false_positive" if predicted else "false_negative",
                               "label": row["label"], "verdict": response.verdict, "text": row["text"]})
        labels = [int(r["label"] == "clickfix") for r in held_out]
        uncertain = sum(v == "uncertain" for v in verdicts)
        results[mode] = {"strict": metrics(labels, predictions),
                         "all_warnings": metrics(labels, [int(v != "no_suspicious_signals") for v in verdicts]),
                         "uncertain_rate": uncertain / len(held_out),
                         "decision_coverage": 1 - uncertain / len(held_out),
                         "latency_ms": {"median": statistics.median(latencies),
                                        "p95": float(np.percentile(latencies, 95)),
                                        "scope": "one block, warm model, single measured pass; not browser latency"},
                         "errors": errors,
                         "subsets": {kind: sum(r["synthetic"] == synthetic for r in held_out)
                                     for kind, synthetic in (("synthetic", True), ("sourced_or_recreated", False))}}
    return {"research_status": "exploratory_synthetic_seed" if all(r["synthetic"] for r in rows)
            else "small_reviewed_corpus_not_representative", "dataset_sha256": fingerprint,
            "model_metadata": detector.metadata, "test_size": len(held_out),
            "family_count": len({r["template_group"] for r in rows}),
            "test_families": sorted({r["template_group"] for r in held_out}),
            "test_ids": manifest["splits"]["test"], "platform": platform.platform(),
            "results": results, "limitations": ["Small authored corpus, not a real-world protection estimate",
            "Synthetic test wording may share author style despite family separation",
            "Uncertain counts as non-detection in strict metrics and as alert in all_warnings",
            "Test examples must not be reused for threshold tuning; revisions require a fresh evaluation set"]}


def main():
    parser = argparse.ArgumentParser(description="Evaluate frozen BLANK splits without retraining")
    parser.add_argument("--data", type=Path, default=ROOT / "data/seed.jsonl")
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/evaluation.json")
    args = parser.parse_args()
    report = evaluate(args.data, args.model_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(report["research_status"], "test blocks:", report["test_size"])
    for mode, result in report["results"].items():
        print(mode, result["strict"], "uncertain:", round(result["uncertain_rate"], 3))
    print("Saved:", args.output)


if __name__ == "__main__":
    main()
