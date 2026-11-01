import json

import pytest

from backend import configure


def test_pairing_generation_preservation_and_rotation(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(configure, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["configure", "--extension-id", "a" * 32])
    configure.main()
    path = tmp_path / ".local/config.json"
    original = json.loads(path.read_text())
    assert len(original["token"]) >= 43
    assert original["origins"] == ["chrome-extension://" + "a" * 32]
    monkeypatch.setattr("sys.argv", ["configure", "--extension-id", "b" * 32])
    configure.main()
    preserved = json.loads(path.read_text())
    assert preserved["token"] == original["token"]
    assert len(preserved["origins"]) == 2
    monkeypatch.setattr("sys.argv", ["configure", "--extension-id", "b" * 32, "--rotate"])
    configure.main()
    rotated = json.loads(path.read_text())
    assert rotated["token"] != original["token"]
    assert len(rotated["origins"]) == 2
    capsys.readouterr()  # Test-only generated credentials never appear in normal test output.


def test_pairing_rejects_invalid_extension_id(tmp_path, monkeypatch):
    monkeypatch.setattr(configure, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["configure", "--extension-id", "https://evil.test"])
    with pytest.raises(SystemExit):
        configure.main()
    assert not (tmp_path / ".local/config.json").exists()
