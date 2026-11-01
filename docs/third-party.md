# Reuse and Third-Party Notices

| Upstream | Pinned revision | Material and local destination | License / changes |
|---|---|---|---|
| [ClickFixMitigator](https://github.com/j0rd1s3rr4n0/ClickFixMitigator) | ae0e5144930f391f97dd8a7cbe0aa08548ee0d3d | English subset of shortcut/paste recognition from browser-extension/content-script.js, adapted in backend/features.py | MIT, copyright (c) 2026 Jordi Serrano; broad Windows-key-only and non-English matches removed; bounded features/raw offsets added |
| [ClickGrab](https://github.com/MHaggis/ClickGrab) | e5e78d67fb44172a24a4ac6adeceb7b7dae09e80 | extract_match_with_context helper adapted to excerpt() in backend/features.py | Apache-2.0; raw-offset API, 600-character output limit; no fetching/decoding/command execution imported |
| [ClickFix Defense Kit](https://github.com/DareDev256/clickfix-defense-kit) | f4ad2b1583644848d176fec803cdf78568ad0fbf | Regression-corpus organization and permanent false-positive/bypass testing practice | Architectural and testing inspiration only; no source or corpus rows copied |
| [ClipShield](https://github.com/xorjosh/ClipShield) | 1b55b4ecbdef254a35646eb18e18444c247a8e91 | DOM observer/warning architectural inspiration | GPL-3.0 source not vendored or translated |

Full upstream licenses are in `licenses/`. Original project and contributor attribution remains above. No third-party malware payloads, binaries, captured browser profiles, or live attack pages were imported. Data reuse rights are separate from these code licenses. No upstream corpus is used as independent held-out evidence.

For the self-contained 0.3.0 extension, the credited English patterns are exported to `extension/assets/rules.json`. The bounded excerpt adaptation is translated in `extension/detector.js`, with code-point limits and UTF-16 offset mapping. The changed runtime destination and modifications are recorded in `extension/THIRD_PARTY_NOTICES.txt`; full MIT and Apache-2.0 texts are also shipped in `extension/licenses/`.

The original BLANK icon source is `tools/build_icons.py`; generated PNGs are bundled. The model vocabulary/weights are trained locally from BLANK-authored synthetic data, with no sklearn code shipped in-browser.
