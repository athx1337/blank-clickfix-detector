"""Build a deterministic, allowlisted extension ZIP without developer/private files."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ["manifest.json", "background.js", "detector.js", "content.js", "popup.html", "popup.js",
         "cloud.js", "cloud-worker.js", "cloud-popup.js", "cloud-config.js",
         "offscreen.html", "offscreen.js", "semantic-worker.js",
         "popup.css", "options.html", "options.js", "assets/model.json", "assets/rules.json",
         "THIRD_PARTY_NOTICES.txt", "licenses/ClickFixMitigator-MIT.txt", "licenses/ClickGrab-Apache-2.0.txt",
         *[f"icons/blank-{size}.png" for size in (16, 32, 48, 128)]]


def package(output_dir: Path = ROOT / "dist"):
    extension = ROOT / "extension"
    manifest = json.loads((extension / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("host_permissions") or manifest["manifest_version"] != 3:
        raise ValueError("Unexpected required hosts or manifest version")
    model = json.loads((extension / "assets/model.json").read_text(encoding="utf-8"))
    if model["schema_version"] != 1 or not model["terms"]:
        raise ValueError("Missing browser model")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"blank-{manifest['version']}.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(FILES):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            content = (extension / name).read_bytes()
            if Path(name).suffix in {".js", ".html", ".css", ".json", ".txt"}:
                content = content.replace(b"\r\n", b"\n")
            archive.writestr(info, content)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(".zip.sha256").write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return path


def package_semantic(output_dir: Path = ROOT / "dist"):
    extension = ROOT / "extension"
    manifest = json.loads((extension / "manifest.json").read_text(encoding="utf-8"))
    semantic_files = [str(p.relative_to(extension)).replace("\\", "/")
                      for p in (extension / "assets/semantic").rglob("*") if p.is_file()]
    all_files = sorted(set(FILES + semantic_files))
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"blank-{manifest['version']}-experimental-semantic.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in all_files:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            content = (extension / name).read_bytes()
            if Path(name).suffix in {".js", ".html", ".css", ".json", ".txt"}:
                content = content.replace(b"\r\n", b"\n")
            archive.writestr(info, content)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(".zip.sha256").write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print("Standard package:", package())
    print("Experimental semantic package:", package_semantic())
