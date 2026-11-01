import json

from backend.config import ROOT
from ml.benchmark import benchmark, bootstrap_recall_delta, decisions


def test_lexical_benchmark_freezes_splits_and_records_failures(tmp_path):
    report = benchmark(ROOT / "data/seed.jsonl", tmp_path, semantic=False)
    assert report["human_reviewed_count"] == 0
    assert report["promotion"]["eligible"] is False
    assert report["cloud"]["groq"]["status"] == "not_performed"
    assert report["results"]["word_char_hybrid"]["outcomes"]
    assert (tmp_path / "splits.json").is_file()
    assert json.loads((tmp_path / "comparison.json").read_text())["dataset_sha256"] == report["dataset_sha256"]


def test_truncation_and_direct_rules_cannot_be_cleared():
    rows = [{"id": "a", "text": "Verify you are human. Open Run, paste and press Enter.",
             "label": "clickfix", "template_group": "a"},
            {"id": "b", "text": "Ordinary news", "label": "legitimate", "template_group": "b"}]
    assert decisions(rows, [0.01, 0.01], 0.9, hybrid=True, truncated=[False, True]) == ["suspicious", "uncertain"]
    assert bootstrap_recall_delta(rows, ["suspicious", "no_suspicious_signals"],
                                  ["suspicious", "no_suspicious_signals"]) == [0., 0.]
