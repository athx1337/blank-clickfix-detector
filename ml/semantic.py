"""Shared semantic windowing and mean-of-normalized-window embeddings."""
import numpy as np

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"


def token_windows(ids, size=254, overlap=32, cap=8):
    # 254 content tokens + CLS/SEP = the model's 256-token limit.
    starts = range(0, max(1, len(ids)), size - overlap)
    windows = []
    for start in starts:
        if len(windows) == cap:
            return windows, True
        windows.append(ids[start:start + size])
        if start + size >= len(ids):
            break
    return windows, False


def aggregate_embeddings(rows):
    rows = np.asarray(rows, dtype=np.float64)
    if rows.ndim != 2 or not len(rows) or not np.isfinite(rows).all():
        raise ValueError("Invalid embeddings")
    norms = np.linalg.norm(rows, axis=1, keepdims=True)
    average = (rows / np.maximum(norms, 1e-12)).mean(axis=0)
    return average / max(float(np.linalg.norm(average)), 1e-12)


def encode_blocks(model, texts):
    """Same tokenization/pooling for frozen, fine-tuned, exported and browser models."""
    import torch

    from backend.features import normalize_with_offsets

    vectors, truncated = [], []
    tokenizer = model.tokenizer
    model.eval()
    for text in texts:
        ids = tokenizer.encode(normalize_with_offsets(text)[0], add_special_tokens=False)
        windows, cut = token_windows(ids)
        batch = tokenizer.pad([tokenizer.prepare_for_model(w, add_special_tokens=True,
                                                          return_attention_mask=True) for w in windows],
                              return_tensors="pt")
        with torch.inference_mode():
            output = model({key: value.to(model.device) for key, value in batch.items()})["sentence_embedding"]
        vectors.append(aggregate_embeddings(output.cpu().numpy()))
        truncated.append(cut)
    return np.array(vectors), truncated
