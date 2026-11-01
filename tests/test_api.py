import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings


@pytest.fixture
def client(tmp_path):
    settings = Settings(token="test-pairing-token", origins=["chrome-extension://" + "a" * 32])
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8765") as client:
        yield client


def payload():
    return {"scan_id": "test", "blocks": [{"block_id": "b1", "text":
            "Verify you are human. Press Win+R, Ctrl+V and Enter."}]}


AUTH = {"Authorization": "Bearer test-pairing-token"}


def test_health_and_real_analysis(client):
    assert client.get("/health").json()["status"] == "ok"
    response = client.post("/analyze", headers=AUTH, json=payload())
    assert response.status_code == 200
    assert response.json()["verdict"] == "suspicious"


def test_auth_origin_host(client):
    assert client.post("/analyze", json=payload()).status_code == 401
    assert client.post("/analyze", headers={"Authorization": "Bearer wrong"}, json=payload()).status_code == 401
    assert client.post("/analyze", headers={**AUTH, "Origin": "https://evil.test"}, json=payload()).status_code == 403
    assert client.get("/health", headers={"Host": "evil.test"}).status_code == 400
    origin = "chrome-extension://" + "a" * 32
    response = client.options("/analyze", headers={"Origin": origin,
                              "Access-Control-Request-Method": "POST",
                              "Access-Control-Request-Headers": "authorization,content-type"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_validation_is_bounded_and_private(client):
    data = payload()
    data["blocks"][0]["context"] = {"inside_dialog": "PRIVATE_SECRET"}
    response = client.post("/analyze", headers=AUTH, json=data)
    assert response.status_code == 422
    assert "PRIVATE_SECRET" not in response.text
    data = payload()
    data["blocks"].append(data["blocks"][0])
    assert client.post("/analyze", headers=AUTH, json=data).status_code == 422
    assert client.post("/analyze", headers=AUTH, content=b"x" * 131073).status_code == 413


def test_bad_json_and_unknown_fields(client):
    assert client.post("/analyze", headers=AUTH, content=b"{").status_code == 422
    assert client.post("/analyze", headers=AUTH, json={**payload(), "url": "https://evil.test"}).status_code == 422


def test_rate_limit(client):
    codes = [client.post("/analyze", headers=AUTH, json=payload()).status_code for _ in range(61)]
    assert codes[-1] == 429


def test_clipboard_payload_detection(client):
    data = {
        "scan_id": "test_clip",
        "blocks": [{"block_id": "b1", "text": "Ordinary page text without commands."}],
        "clipboard": "powershell -NoP -W Hidden -C calc.exe"
    }
    response = client.post("/analyze", headers=AUTH, json=data)
    assert response.status_code == 200
    res = response.json()
    assert res["verdict"] == "suspicious"
    assert any(f["code"] == "CLIPBOARD_MALICIOUS_COMMAND" for f in res["findings"])

