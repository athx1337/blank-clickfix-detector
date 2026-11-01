import hashlib
import json
import zipfile

from tools.package_extension import FILES, package


def test_package_is_reproducible_and_contains_only_runtime(tmp_path):
    path = package(tmp_path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert hashlib.sha256(package(tmp_path).read_bytes()).hexdigest() == digest
    with zipfile.ZipFile(path) as archive:
        assert set(archive.namelist()) == set(FILES)
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["permissions"] == ["activeTab", "scripting", "storage", "offscreen", "clipboardRead"]
        assert not manifest.get("host_permissions")
        assert "connect-src 'self'" in manifest["content_security_policy"]["extension_pages"]
        assert 'https://api.groq.com' in manifest["content_security_policy"]["extension_pages"]
        assert "web_accessible_resources" not in manifest
        assert not any(name.endswith((".py", ".joblib")) for name in archive.namelist())
        for name in manifest["icons"].values():
            assert archive.read(name).startswith(b"\x89PNG\r\n\x1a\n")
