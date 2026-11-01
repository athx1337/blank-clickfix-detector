# Verification record

## Current self-contained build — 0.2.0

Date: 2026-11-01, Windows/Python 3.14.3, Node and Playwright 1.56.0. The extension now
uses bundled JS inference/JSON data and does not call the reference API.

- **36 standard tests passed; 90% backend/ML coverage.** This includes 288 browser/Python
  comparisons across rules-only/hybrid modes, dialog variants, synthetic seed text and
  Unicode/negation regression variations. Verdicts, evidence codes/passages, mode/version
  and classifier scores agree within the stated 1e-6 tolerance. These are compatibility
  checks, not additional independent research observations.
- The committed JSON bundle matches a fresh training/export from the seed. Package tests
  verify deterministic bytes, the exact allowlist, PNG icons, local-only CSP and absence
  of required host permissions or Python/joblib files.
- **15 Chromium integration tests passed in 47.02 seconds** (Chromium 153.0.8010.12,
  explicitly selected cached revision 1243). No API server was started. Checks cover offline
  manual scans, hybrid display/evidence, private/editable exclusions, storage isolation,
  HTML-like evidence as text, traversal uncertainty, navigation cleanup, closed-shadow
  warning dismissal/rescan, opt-in dynamic insertion and disable, feedback-loop suppression,
  pause-all, unsupported pages, inference failure, corrupt-model rules-only fallback,
  corrupt-rules unavailability and delayed-commit invalidation on opt-out/navigation.
- The unmodified release ZIP was built, extracted into a temporary profile and initialized
  successfully with **no granted host origins**, no pairing and the hybrid model available.
  The harness waits for first-install onboarding before creating popup test tabs, avoiding
  a reproduced startup navigation race in the test setup.
- The harness records browser requests and rejects HTTP/HTTPS traffic beyond its local
  demo fixture. The shipped worker loads only extension-local JSON; CSP restricts connections
  to self. The automated UI fixture adds loopback host access to a temporary copy because
  its popup is opened in a tab; real toolbar access/prompts remain separate manual checks.
- Ruff (backend/ml/data/tests/tools), Python compileall, pip dependency consistency and
  JavaScript syntax checks passed. Screenshot of offline verdict/evidence UI was inspected.
- The direct ECC-guided review reproduced and fixed a stale-session commit race and
  checked the offline trust boundary; see local-review.md. CodeRabbit stayed inactive.

Build: PASS. Lint: PASS. Behavior/parity: PASS. Static type checking: NOT CONFIGURED.
Backend/ML coverage is not JavaScript coverage. The seed evaluation, labels, splits and
thresholds were not retuned for this port; it still establishes no hybrid improvement.

Public store target acceptance: **NOT PERFORMED**. No upload, account creation, cloud
service, developer identity, policy hosting or store approval has occurred. Manual Chrome
and Edge toolbar/permission acceptance, representative-data validation, broader beta work,
support contact and distribution license choice remain in release.md/manual-testing.md.

The following 0.1.0 record is historical; its pairing/API setup is not required for 0.2.0.

## Earlier local-server build — 0.1.0 (historical)

Date: 2026-11-01 (Asia/Calcutta). Local Windows prototype; no deployment, external push, or PR.

## Executed checks

- Clean Python 3.14.3 virtual environment installed from requirements-dev.txt; full resolved runtime/development locks saved. `pip check`: no broken requirements.
- Backend/pipeline pytest suite: **31 passed**, **91% combined backend/ML coverage**. Pairing generation/preservation/rotation and invalid-ID rejection, authentication, origins, Host, validation privacy, rate limiting, incremental/chunked body limits, disconnects, rules, raw evidence mapping, missing/corrupt/incompatible artifacts, inference failure, context ablation, grouped splits, model reload, threshold false-positive accounting, and evaluation were checked.
- Ruff on backend/ml/data/tests: passed. Python compile/import checks and all four extension JavaScript syntax checks: passed.
- Browser integration uses Playwright 1.56.0 with an explicitly selected **existing Chromium 153.0.8010.12** executable (cached Chromium revision 1243). It uses a temporary profile, real MV3 service worker/content scripts, actual popup controls, pairing, and HTTP API requests. This is not a claim that Playwright's default 1.56 browser bundle was downloaded/tested.
- **Latest browser run: 10 passed** in 51.97 seconds. It checks all manual demo verdicts, token isolation/private extraction, HTML-like evidence as text, bounded large-DOM uncertainty, navigation during analysis, dynamic opt-in/disable and feedback-loop suppression, actual hybrid mode display, analysis timeout, downtime, unsupported pages, editable-root exclusion, stable unchanged-content revisions, and discarding in-flight automatic results after opt-out.
- Popup screenshot captured and visually inspected: readable status, evidence, mode, site toggle, and settings. Screenshot is generated under ignored test-results.
- Source security review checked the fixed API address, lack of command execution/fetch proxy/clipboard hooks, trusted-context storage, strict CSP, text-only rendering, message sender checks, and absence of the previous product name in runtime code.

Automated checks used actual extension behavior and a local HTTP API. Manual Chrome/Edge acceptance remains separate below.

The direct ECC-guided review reproduced and fixed three browser privacy/lifecycle defects; see local-review.md. After those changes, the backend/pipeline suite still has 31 passing tests and 91% coverage. Ruff, Python compile checks, all extension syntax checks, dependency consistency, and diff whitespace checks pass. A high-confidence credential-pattern scan found no matching files or tracked private configuration. Static type checking remains unconfigured, and these checks are not a guarantee of security.

## Training/evaluation

Training and evaluation executed from the clean virtual environment. The authored seed has **64 synthetic, unreviewed examples, 32 families**, with train/validation/test sizes **36/14/14**. No real-incident or human-review claim is made. Dataset line endings were normalized to LF for reproducible hashes; labels/text/family assignments were not selected using test performance.

The checked-in machine-readable snapshot is `seed-evaluation.json`. Rules and hybrid have identical strict detections on this small seed; no hybrid improvement was established. ML-only errors and hybrid uncertain alerts remain in the report. A regression fix ensures hybrid threshold selection counts strong-rule false positives rather than measuring just its ML branch. This seed was inspected during development; even its held-out results are exploratory, not a new independent real-world benchmark.

## Skills and external review

The pinned ECC testing/security/verification skills and CodeRabbit code-review skill are installed project-locally, with licenses/provenance retained. They will be available to subsequent project turns through AGENTS.md and project skill storage.

**CodeRabbit: OPTIONAL/INACTIVE by user preference.** Its previously authorized CLI 0.9.2 installation was verified, but no login, review upload, billing, or paid continuation occurred. The user selected skills that work directly; project reviews now use ECC testing/security/verification instructions and local tools with the existing assistant. CodeRabbit sign-in is not required to continue BLANK development. See local-review.md for this direct review's reproduced findings, fixes, and verification.

## Remaining acceptance and research work

- Manual tests in actual Chrome and Edge, particularly real browser-action activeTab access on arbitrary sites and optional-host permission prompts/revocation, are **NOT PERFORMED**. Installed executables were inspected: Chrome 156.0.8078.74 and Edge 156.0.4314.58. Native computer-use initialization/app discovery succeeded, but no developer-mode, security/permission setting, or extension-installation UI was changed. The computer-use skill's guidance prohibits changing in-app security/privacy settings, and its confirmations policy requires action-time confirmation for browser-extension installation. Exact user-run acceptance steps are in manual-testing.md. Automated loopback tests use the installed loopback host permission.
- Human-reviewed dataset expansion toward 150–250 examples is **NOT COMPLETE**. The repository provides a schema, provenance/review policy, grouped split machinery, and a seed pipeline; it does not fabricate annotation labor or source incidents.
- No user study, real-world browsing trial, iframe/shadow-root/image-only coverage, clipboard/OS interception, or proof of infection prevention.
- Third-party deprecation warnings appear in Starlette/AnyIO and joblib/NumPy with the resolved environment; they do not fail the executed checks. They are retained rather than hidden.
- Dedicated static type checking is not configured; syntax/import checks, Ruff and behavior/integration tests were executed. No production target exists.
