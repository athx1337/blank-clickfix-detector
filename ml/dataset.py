import hashlib
import json
from pathlib import Path

from sklearn.model_selection import StratifiedGroupKFold

from backend.features import normalize_with_offsets
from backend.schemas import Block

REQUIRED = {"id", "text", "label", "scenario", "template_group", "source", "synthetic"}


def dataset_hash(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_dataset(path: Path):
    rows, ids = [], set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not REQUIRED <= row.keys() or row["label"] not in {"clickfix", "legitimate"}:
            raise ValueError(f"Invalid dataset record on line {line_number}")
        if type(row["synthetic"]) is not bool:
            raise ValueError("synthetic must be a boolean")
        if row["id"] in ids:
            raise ValueError("duplicate dataset ID")
        if any(not isinstance(row[key], str) or not row[key].strip()
               for key in ("id", "text", "scenario", "template_group", "source")):
            raise ValueError("Dataset strings must be nonempty")
        if row.get("review_status") in {"ambiguous", "excluded"}:
            continue
        if not row["synthetic"] and row.get("review_status") != "human_reviewed":
            raise ValueError("Non-synthetic records require actual human review before research use")
        Block(block_id="dataset", text=row["text"], context=row.get("context", {}))
        ids.add(row["id"])
        rows.append(row)
    if not rows:
        raise ValueError("Dataset is empty")
    return rows


def split_records(rows):
    # Connected components enforce template, source-family, and exact normalized-duplicate grouping.
    parents = list(range(len(rows)))

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    seen = {}
    labels = {}
    for i, row in enumerate(rows):
        normalized = " ".join(normalize_with_offsets(row["text"])[0].split())
        if normalized in labels and labels[normalized] != row["label"]:
            raise ValueError("Identical text has conflicting labels")
        labels[normalized] = row["label"]
        keys = [("template", row["template_group"]), ("text", normalized)]
        if not row["synthetic"]:
            keys.append(("source", row.get("source_family", row["source"])))
        for key in keys:
            if key in seen:
                parents[root(i)] = root(seen[key])
            else:
                seen[key] = i
    groups = [root(i) for i in range(len(rows))]
    if len(set(groups)) < 10:
        raise ValueError("At least 10 independent families are required for this exploratory five-fold split")
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    folds = [test for _, test in splitter.split(rows, [r["label"] for r in rows], groups)]
    partitions = {"test": list(folds[0]), "validation": list(folds[1]),
                  "train": [i for fold in folds[2:] for i in fold]}
    for indices in partitions.values():
        if {rows[i]["label"] for i in indices} != {"clickfix", "legitimate"}:
            raise ValueError("Grouped partitions lack both labels; collect more independent data")
    return {name: sorted(rows[i]["id"] for i in indices) for name, indices in partitions.items()}


def validate_splits(rows, splits):
    if splits != split_records(rows):
        raise ValueError("Split manifest differs from deterministic grouped assignments")
