"""Export the validation-selected semantic encoder and audit quantization drift."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import joblib
import numpy as np

from backend.config import ROOT
from backend.features import normalize_with_offsets
from ml.dataset import load_dataset
from ml.semantic import aggregate_embeddings, encode_blocks, token_windows


def export_semantic(experiment: Path, destination: Path, data: Path):
    import onnxruntime as ort
    import torch
    from onnxruntime.quantization import QuantType, quantize_dynamic
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(4)
    report = json.loads((experiment / "comparison.json").read_text())
    selected = report["semantic_selection"]
    if selected not in {"minilm_frozen", "minilm_setfit"}:
        raise ValueError("No validation-selected semantic model")
    body = SentenceTransformer(str(experiment / selected), device="cpu", trust_remote_code=False)
    body.max_seq_length = 256
    transformer = body[0].auto_model
    transformer.set_attn_implementation("eager")
    transformer.eval()
    classifier = joblib.load(experiment / f"{selected}.joblib")  # trusted local artifact only
    destination.mkdir(parents=True, exist_ok=True)
    model_dir = destination / "model"
    model_dir.mkdir(exist_ok=True)
    onnx_dir = model_dir / "onnx"
    onnx_dir.mkdir(exist_ok=True)
    body.tokenizer.save_pretrained(str(model_dir))
    transformer.config.save_pretrained(str(model_dir))

    class Encoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.model = transformer

        def forward(self, input_ids, attention_mask, token_type_ids):
            return self.model(input_ids=input_ids, attention_mask=attention_mask,
                              token_type_ids=token_type_ids).last_hidden_state

    fp32 = experiment / "encoder.onnx"
    inputs = body.tokenizer("BLANK verification example", return_tensors="pt")
    torch.onnx.export(Encoder(), (inputs["input_ids"], inputs["attention_mask"], inputs["token_type_ids"]),
                      str(fp32), input_names=["input_ids", "attention_mask", "token_type_ids"],
                      output_names=["last_hidden_state"], opset_version=17, dynamo=False,
                      dynamic_axes={name: {0: "batch", 1: "sequence"} for name in
                                    ("input_ids", "attention_mask", "token_type_ids", "last_hidden_state")})
    quantized = onnx_dir / "model_quantized.onnx"
    quantize_dynamic(str(fp32), str(quantized), weight_type=QuantType.QInt8)
    sign = 1 if classifier.classes_[1] == "clickfix" else -1
    metadata = {"schema_version": 1, "model_id": selected,
                "model_version": "blank-semantic-" + report["dataset_sha256"][:12],
                "dataset_sha256": report["dataset_sha256"], "source": report["training"][selected],
                "weights": (classifier.coef_[0] * sign).tolist(),
                "intercept": float(classifier.intercept_[0] * sign),
                "thresholds": report["validation"][selected]["thresholds"],
                "window": {"content_tokens": 254, "overlap": 32, "cap": 8},
                "experimental": True, "promoted": False}
    (destination / "classifier.json").write_text(json.dumps(metadata, separators=(",", ":")), encoding="utf-8")
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    session = ort.InferenceSession(str(quantized), sess_options=options, providers=["CPUExecutionProvider"])
    parity, differences = [], []
    rows = load_dataset(data)
    for row in rows:
        text = row["text"]
        ids = body.tokenizer.encode(normalize_with_offsets(text)[0], add_special_tokens=False)
        windows, cut = token_windows(ids)
        encoded = body.tokenizer.pad([body.tokenizer.prepare_for_model(w, return_attention_mask=True) for w in windows],
                                     return_tensors="np")
        hidden = session.run(None, {k: v.astype(np.int64) for k, v in encoded.items()})[0]
        mask = encoded["attention_mask"][..., None]
        means = (hidden * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1)
        vector = aggregate_embeddings(means)
        quant_score = float(1 / (1 + np.exp(-(vector @ np.array(metadata["weights"]) + metadata["intercept"]))))
        reference, _ = encode_blocks(body, [text])
        reference_score = float(classifier.predict_proba(reference)[0, list(classifier.classes_).index("clickfix")])
        differences.append(abs(quant_score - reference_score))
        parity.append({"id": row["id"], "text": text, "token_windows": windows, "truncated": cut,
                       "reference_score": reference_score, "onnx_score": quant_score,
                       "onnx_vector": vector.tolist()})
    drift = {"sample_count": len(parity), "max_score_absolute_difference": max(differences),
             "mean_score_absolute_difference": float(np.mean(differences)),
             "advisory_boundary_disagreements": sum((r["reference_score"] >= 0.5) != (r["onnx_score"] >= 0.5) for r in parity),
             "scope": "authored synthetic seed compatibility check, not independent effectiveness evidence"}
    (experiment / "semantic-parity.json").write_text(json.dumps({"drift": drift, "cases": parity}), encoding="utf-8")
    (destination / "quantization.json").write_text(json.dumps(drift, indent=2), encoding="utf-8")
    metadata["hashes"] = {str(p.relative_to(destination)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in model_dir.rglob("*") if p.is_file()}
    (destination / "classifier.json").write_text(json.dumps(metadata, separators=(",", ":")), encoding="utf-8")
    shutil.copyfile(ROOT / "data/README.md", experiment / "dataset-provenance.md")
    print(json.dumps(drift, indent=2), flush=True)
    return drift


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, default=ROOT / "experiments/seed-ai")
    parser.add_argument("--output", type=Path, default=ROOT / "extension/semantic")
    parser.add_argument("--data", type=Path, default=ROOT / "data/seed.jsonl")
    args = parser.parse_args()
    export_semantic(args.experiment, args.output, args.data)
