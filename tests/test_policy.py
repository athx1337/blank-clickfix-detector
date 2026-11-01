import asyncio
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app import RequestGuard, create_app
from backend.config import Settings
from backend.detector import Detector
from backend.features import evidence, extract_features, normalize_with_offsets
from backend.rules import match_rules
from backend.schemas import AnalyzeRequest, Block


def test_context_ablation_is_real():
    block = Block(block_id="b", text="Human verification. Open Windows Run and paste the check.",
                  context={"inside_dialog": True, "has_copy_button": True})
    assert match_rules(block).verdict == "suspicious"
    assert match_rules(block, use_context=False).verdict == "uncertain"


def test_raw_evidence_mapping_and_suspicious_command():
    text = "Verify you are human. Press Ｗｉｎ\u200b+R, then Ctrl+V and Enter."
    f = extract_features(text)
    assert evidence(text, f, ["verification", "system"]) in text
    assert normalize_with_offsets("\ufeffA")[0] == "a"
    assert evidence("abc", extract_features("abc"), []) == "abc"
    block = Block(block_id="b", text="Paste mshta.exe [INERT_PLACEHOLDER] and press Enter.")
    assert match_rules(block).verdict == "suspicious"


def test_missing_model_and_configuration(tmp_path):
    detector = Detector(tmp_path)
    assert detector.model_reason
    with patch.dict("os.environ", {"blank_config": str(tmp_path / "absent.json")}):
        assert Settings.load().token == ""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"token": "test", "origins": []}))
    with patch.dict("os.environ", {"blank_config": str(path)}):
        assert Settings.load().token == "test"
    with TestClient(create_app(Settings(model_dir=tmp_path)), base_url="http://127.0.0.1:8765") as client:
        assert client.post("/analyze", json={"scan_id": "x", "blocks": []}).status_code == 503


def test_inference_failure_never_becomes_clean(tmp_path):
    app = create_app(Settings(token="test", model_dir=tmp_path))
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        with patch.object(app.state.detector, "analyze", side_effect=RuntimeError("PRIVATE_BODY")):
            response = client.post("/analyze", headers={"Authorization": "Bearer test"},
                                   json={"scan_id": "x", "blocks": []})
    assert response.status_code == 503
    assert "PRIVATE_BODY" not in response.text


def test_schema_limits():
    with pytest.raises(ValueError):
        AnalyzeRequest(scan_id="x", blocks=[{"block_id": f"b{i}", "text": "x" * 2000} for i in range(13)])
    with pytest.raises(ValueError):
        AnalyzeRequest(scan_id="x", blocks=[{"block_id": "b", "text": "x" * 2001}])


def test_chunked_body_and_disconnect_are_bounded():
    statuses = []

    async def app(scope, receive, send):
        statuses.append("forwarded")

    async def run(messages):
        guard = RequestGuard(app, Settings(token="test"))
        scope = {"type": "http", "path": "/analyze", "method": "POST", "headers": [
            (b"host", b"127.0.0.1:8765"), (b"authorization", b"Bearer test")]}

        async def receive():
            return messages.pop(0)

        async def send(message):
            if message["type"] == "http.response.start":
                statuses.append(message["status"])

        await guard(scope, receive, send)

    asyncio.run(run([{"type": "http.request", "body": b"x" * 70000, "more_body": True},
                     {"type": "http.request", "body": b"x" * 70000, "more_body": False}]))
    assert statuses == [413]
    statuses.clear()
    asyncio.run(run([{"type": "http.disconnect"}]))
    assert statuses == []
