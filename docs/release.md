# BLANK 0.2.0 release preparation

This build is a self-contained beta, not a published or store-approved release.
Detection requires no backend or cloud hosting. Source and model are bundled locally.

## Package and install

Run `python tools/package_extension.py` from the repository root. The deterministic,
allowlisted ZIP is `dist/blank-0.2.0.zip`, with a matching SHA-256 file. Unzip into its own
directory and load that directory as an unpacked extension for beta testing. Do not load
the repository root. A store ZIP is an upload artifact, not a signed CRX or store listing.

The package includes manifest, worker, extraction, inference, UI, JSON model/rules, original
16/32/48/128 PNG icons, notices and full reused-source licenses. No code or model is fetched
remotely. Regenerate icons using `tools/build_icons.py`; export revised models using
`python -m ml.export_browser` after training and rule edits.

## Store listing draft

Name: BLANK.

Single purpose: Identify suspicious copy-and-run webpage instructions and explain the evidence.

Short description: On-device warnings for deceptive copy-and-run webpage instructions.
No account or server required.

Description: BLANK checks visible English instructions for verification or browser-repair
prompts that ask you to paste and execute system commands. Scan from the toolbar or opt
into automatic checks for individual websites. It explains suspicious and uncertain results
with passages from the page. Analysis runs locally; no browsing text is uploaded. BLANK is
experimental, focused on Windows-oriented instructions in the main document, and does not
block commands or guarantee protection. Its initial classifier uses a small synthetic corpus.

Permission justifications:

- `activeTab`: temporary manual extraction after the user invokes the toolbar action.
- `scripting`: inject bounded extraction and register opted-in site observers.
- `storage`: website preferences and transient latest results, restricted to trusted contexts.
- Optional HTTP/HTTPS host access: background checks only on user-enabled site patterns.

No required host permissions. No clipboard, history, cookies, downloads, native messaging,
remote code, external network permission, or API key. Disabled automatic scanning stops
observers and unregisters scripts; revoking browser access is a separate browser control.

## Remaining public-release gates

- Execute actual toolbar-action and host permission grant/decline/revocation checks in
  Chrome and Edge using the unmodified package. Automated loopback permission fixtures
  do not establish those acceptance results.
- Conduct a beta on representative sites and low-powered devices, including accessibility,
  multi-tab behavior, service-worker restarts, browser restarts, upgrades, and performance.
- Expand independently reviewed/provenanced data and assess false positives, missed lures,
  and uncertainty. Do not describe the 64 synthetic examples as validated real-world accuracy.
- Provide publisher identity, real support contact, publicly hosted privacy policy, genuine
  screenshots and store promotional assets. Verify dashboard data-use declarations against
  actual behavior, even though analysis stays local.
- Choose the project's own distribution license deliberately; third-party notices are included
  but do not constitute a license choice for the original BLANK source.
- Submit through the relevant developer account, complete store review, and establish
  issue reporting, versioning and a tested rollback/recovery procedure. No submission has occurred.

Official references consulted 2026-11-01:
[activeTab](https://developer.chrome.com/docs/extensions/develop/concepts/activeTab),
[prepare an extension ZIP](https://developer.chrome.com/docs/webstore/prepare),
[icons](https://developer.chrome.com/docs/extensions/develop/ui/configure-icons),
[publishing](https://developer.chrome.com/docs/webstore/publish).

Store requirements can change. Recheck them at submission time. No public listing,
developer-account registration, external upload or paid service was created by this work.
