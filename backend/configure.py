"""Local-only pairing configuration. Never expose this file through a web server."""
import argparse
import json
import re
import secrets

from backend.config import ROOT


def main():
    parser = argparse.ArgumentParser(description="Pair BLANK with unpacked browser extension IDs")
    parser.add_argument("--extension-id", action="append", required=True)
    parser.add_argument("--rotate", action="store_true")
    args = parser.parse_args()
    if any(not re.fullmatch(r"[a-p]{32}", value) for value in args.extension_id):
        parser.error("Each extension ID must contain 32 letters from a through p")
    path = ROOT / ".local" / "config.json"
    data = json.loads(path.read_text()) if path.exists() else {"token": secrets.token_urlsafe(32), "origins": []}
    if args.rotate:
        data["token"] = secrets.token_urlsafe(32)
    data["origins"] = sorted(set(data["origins"] + ["chrome-extension://" + x for x in args.extension_id]))
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("Pairing token (paste only into BLANK extension settings):", data["token"])
    print("Local configuration saved. Restart the backend after changing allowed IDs or rotating the token.")


if __name__ == "__main__":
    main()
