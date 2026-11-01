"""Export trusted local sklearn artifacts as inert, bundled browser JSON data."""
import argparse
import json
from pathlib import Path

from backend.config import ROOT
from backend.detector import Detector
from backend.features import PATTERNS


def export_browser(model_dir: Path, destination: Path):
    detector = Detector(model_dir)
    if detector.pipeline is None:
        raise ValueError("A valid trusted local model is required for export")
    vectorizer = detector.pipeline.named_steps["tfidf"]
    classifier = detector.pipeline.named_steps["classifier"]
    if (vectorizer.ngram_range != (1, 2) or vectorizer.norm != "l2"
            or vectorizer.sublinear_tf or vectorizer.binary or vectorizer.stop_words is not None
            or vectorizer.token_pattern != r"(?u)\b\w\w+\b"
            or list(classifier.classes_) != ["clickfix", "legitimate"]):
        raise ValueError("Unsupported vectorizer or classifier contract")
    sign = -1  # sklearn binary coefficients point to legitimate (classes_[1]).
    model = {
        "schema_version": 1, "policy_version": "blank-policy-1",
        "model_version": detector.metadata["model_version"],
        "dataset_sha256": detector.metadata["dataset_sha256"],
        "thresholds": detector.metadata["thresholds"],
        "training_summary": {key: detector.metadata[key] for key in
                             ("synthetic_count", "human_reviewed_count", "split_sizes")},
        "terms": vectorizer.get_feature_names_out().tolist(),
        "idf": vectorizer.idf_.tolist(),
        "weights": (classifier.coef_[0] * sign).tolist(),
        "intercept": float(classifier.intercept_[0] * sign),
    }
    destination.mkdir(parents=True, exist_ok=True)
    for name, value in {"model": model, "rules": {"schema_version": 1, "patterns": PATTERNS}}.items():
        (destination / f"{name}.json").write_text(
            json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n",
            encoding="utf-8", newline="\n")
    return model["model_version"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models")
    parser.add_argument("--output", type=Path, default=ROOT / "extension/assets")
    args = parser.parse_args()
    print(export_browser(args.model_dir, args.output))


if __name__ == "__main__":
    main()
