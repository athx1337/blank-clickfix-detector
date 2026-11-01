import argparse
import hashlib
import json
import platform
import importlib.metadata
from pathlib import Path

import joblib
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from backend.config import ROOT
from backend.detector import Detector
from backend.features import normalize_with_offsets
from backend.rules import match_rules
from backend.schemas import Block
from ml.dataset import dataset_hash, load_dataset, split_records, validate_splits


def choose_threshold(rows, scores, mode):
    candidates = []
    for threshold in [x / 100 for x in range(50, 100, 5)]:
        predictions = []
        for row, score in zip(rows, scores):
            rule = match_rules(Block(block_id="validation", text=row["text"], context=row.get("context", {})),
                               use_context=mode != "hybrid_no_context")
            if mode == "ml":
                predicted = score >= threshold
            else:
                predicted = rule.verdict == "suspicious" or (
                    score >= threshold and rule.execution_lure and not any(
                        f.code == "CONFLICTING_EDUCATIONAL_CONTEXT" for f in rule.findings))
            predictions.append(predicted)
        tp = sum(pred and row["label"] == "clickfix" for row, pred in zip(rows, predictions))
        count = sum(predictions)
        positives = sum(row["label"] == "clickfix" for row in rows)
        # A minimum of five validation alerts is an engineering guard, not statistical certification.
        if count >= 5 and tp / count >= 0.9:
            candidates.append((tp / positives, tp / count, threshold))
    return max(candidates)[2] if candidates else None


def train(data: Path, model_dir: Path, new_split=False):
    rows = load_dataset(data)
    fingerprint = dataset_hash(data)
    model_dir.mkdir(parents=True, exist_ok=True)
    split_path = model_dir / "splits.json"
    if split_path.exists() and not new_split:
        manifest = json.loads(split_path.read_text(encoding="utf-8"))
        if manifest["dataset_sha256"] != fingerprint:
            raise ValueError("Dataset changed. Explicitly use --new-split and retire earlier test claims.")
        splits = manifest["splits"]
    else:
        splits = split_records(rows)
        manifest = {"dataset_sha256": fingerprint, "seed": 42, "splits": splits}
        split_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    validate_splits(rows, splits)
    train_rows = [r for r in rows if r["id"] in splits["train"]]
    validation = [r for r in rows if r["id"] in splits["validation"]]
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=10000)),
        ("classifier", LogisticRegression(C=1, max_iter=1000, random_state=42)),
    ])
    pipeline.fit([normalize_with_offsets(r["text"])[0] for r in train_rows], [r["label"] for r in train_rows])
    index = list(pipeline.classes_).index("clickfix")
    scores = pipeline.predict_proba([normalize_with_offsets(r["text"])[0] for r in validation])[:, index]
    thresholds = {mode: choose_threshold(validation, scores, mode)
                  for mode in ("ml", "hybrid", "hybrid_no_context")}
    path = model_dir / "blank.joblib"
    joblib.dump(pipeline, path)
    metadata = {"model_version": "blank-" + fingerprint[:12], "dataset_sha256": fingerprint,
                "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "sklearn_version": sklearn.__version__, "python_version": platform.python_version(),
                "library_versions": {name: importlib.metadata.version(name)
                                     for name in ("numpy", "scipy", "scikit-learn", "joblib")},
                "policy_version": "blank-policy-1",
                "thresholds": thresholds, "threshold_objective": "validation precision >= 0.90, >=5 alerts; maximize recall",
                "advisory_threshold": 0.5, "advisory_note": "Default classifier boundary; not calibrated probability",
                "split_sizes": {key: len(value) for key, value in splits.items()},
                "synthetic_count": sum(row["synthetic"] for row in rows),
                "human_reviewed_count": sum(row.get("review_status") == "human_reviewed" for row in rows)}
    (model_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    if Detector(model_dir).pipeline is None:
        raise RuntimeError("New model failed to reload")
    return metadata


def main():
    parser = argparse.ArgumentParser(description="Train BLANK on grouped instruction families")
    parser.add_argument("--data", type=Path, default=ROOT / "data/seed.jsonl")
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models")
    parser.add_argument("--new-split", action="store_true")
    args = parser.parse_args()
    print(json.dumps(train(args.data, args.model_dir, args.new_split), indent=2))


if __name__ == "__main__":
    main()
