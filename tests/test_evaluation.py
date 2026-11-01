import json

import pytest

from backend.config import ROOT
from backend.detector import Detector
from backend.schemas import AnalyzeRequest
from ml.dataset import load_dataset, split_records, validate_splits
from ml.evaluate import evaluate
from ml.train import choose_threshold, train


def test_splits_keep_families_together():
    rows = load_dataset(ROOT / "data/seed.jsonl")
    splits = split_records(rows)
    groups = {key: {row["template_group"] for row in rows if row["id"] in ids}
              for key, ids in splits.items()}
    assert not groups["train"] & groups["test"]
    assert not groups["train"] & groups["validation"]
    assert not groups["validation"] & groups["test"]
    assert splits == split_records(rows)
    altered = {key: list(value) for key, value in splits.items()}
    altered["train"].append(altered["test"][0])
    with pytest.raises(ValueError, match="manifest"):
        validate_splits(rows, altered)


def test_train_evaluate_and_corruption(tmp_path):
    dataset = ROOT / "data/seed.jsonl"
    metadata = train(dataset, tmp_path)
    detector = Detector(tmp_path)
    assert detector.pipeline is not None
    result = detector.analyze(AnalyzeRequest(scan_id="test", blocks=[{
        "block_id": "b1", "text": "Verify you are human. Press Win+R, Ctrl+V and Enter."
    }]))
    assert result.detector_mode == "hybrid"
    assert result.model_scores is not None
    assert result.model_version == metadata["model_version"]
    assert detector.model_terms("Verify you are human and paste into Windows Run")
    report = evaluate(dataset, tmp_path)
    assert set(report["results"]) == {"rules", "ml", "hybrid", "hybrid_no_context"}
    assert report["research_status"] == "exploratory_synthetic_seed"
    for row in report["results"].values():
        assert sum(sum(x) for x in row["strict"]["confusion_matrix"]) == report["test_size"]
        assert row["latency_ms"]["p95"] >= 0
    (tmp_path / "blank.joblib").write_bytes(b"corrupt")
    assert Detector(tmp_path).pipeline is None
    metadata["sklearn_version"] = "incompatible"
    (tmp_path / "metadata.json").write_text(json.dumps(metadata))
    assert Detector(tmp_path).pipeline is None


def test_dataset_rejects_invalid_or_ambiguous_records(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text('{"id":"x"}\n')
    with pytest.raises(ValueError):
        load_dataset(path)
    rows = load_dataset(ROOT / "data/seed.jsonl")
    rows[1] = {**rows[1], "id": rows[0]["id"]}
    path.write_text("\n".join(json.dumps(row) for row in rows))
    with pytest.raises(ValueError, match="duplicate"):
        load_dataset(path)


def test_hybrid_threshold_counts_rule_false_positives():
    rows = [{"label": "legitimate", "text": "Repair your browser. Open PowerShell, paste the fix and press Enter."}]
    rows += [{"label": "clickfix", "text": "Verify you are human. Open Windows Run, paste the code and press Enter."}
             for _ in range(6)]
    # No threshold can repair this rule false positive: full-policy precision is 6/7, below 90%.
    assert choose_threshold(rows, [0.1] + [0.8] * 6, "hybrid") is None
