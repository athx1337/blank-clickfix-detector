# Architecture and threat model

## Current runtime: self-contained extension (0.2.0)

The installed extension does **not** use the Python API. Its service worker imports
`detector.js` and loads only packaged `assets/rules.json` and `assets/model.json` through
extension-local URLs. The MV3 CSP permits connections only to the extension itself.
There are no required host permissions, tokens, cloud services, remote scripts, remote
models, or runtime Python dependencies. `activeTab` grants manual extraction access
when the user invokes the toolbar action; optional per-host access enables automatic scans.

The Python backend below remains a development/reference implementation for research,
API regression tests, and comparison. Its security configuration is not an installation step.

`ml.export_browser` exports word-unigram/bigram vocabulary, IDF, signed logistic weights,
intercept, validation thresholds and provenance summary. JS applies the same per-character
normalization, token counts, TF-IDF L2 normalization and logistic function. Raw evidence
offsets track UTF-16 positions in the browser; excerpt limits use code points. Unicode word
boundaries in fixed rules are translated to Unicode-aware lookarounds. Parity checks cover
the seed plus regression variations, in dialog/non-dialog and rules-only/hybrid modes;
they are compatibility checks, not a fresh research benchmark or proof against all Unicode evasion.

Missing/corrupt/incompatible model data visibly falls back to `rules_only`. Missing rules
or unexpected analysis failures report unavailable, never a clean result. Settings remain
available so users can disable scanning even if detector initialization fails. Bundles ship
with extension releases; no background model download exists. JSON is data, never evaluated.

Page DOM is untrusted. Only main-frame isolated content scripts can submit automatic scans,
after current site opt-in and host-permission checks. Only popup/options can initiate manual
scans or change settings. Input validation enforces types, unknown-field rejection, duplicate
IDs, block/total bounds, and extraction metadata. No content script receives direct access to
local/session storage. No page-accessible messaging bridge is exposed.

Automatic messages must match the current document key. Manual extraction is checked
against navigation epochs. Result writes and clears are serialized per tab, and the scan
generation is rechecked inside the write so opt-out/navigation cannot resurrect stale
session results while a commit is pending. Dismissal identity ignores traversal counts,
which can change when BLANK's own warning is removed.

Persistent storage contains enabled-site patterns only. The latest result (including evidence)
per tab is held in trusted session storage and removed on navigation/tab close/browser restart;
there is no history. An in-memory automatic cache expires after 30 seconds. Old pairing tokens
are removed on migration. Main-document extraction, rules and lifecycle limits below still apply.

## Optional research API trust boundaries

The optional reference API accepts the same bounded instruction schema from authenticated
local research tools. The 0.2.0 extension neither calls it nor reads its pairing credentials.
Its ignored local configuration remains separate from the browser package. No web-accessible
scripts, `window.postMessage` bridge, clipboard hooks, or arbitrary URL proxy exist.

The local API accepts a bearer token, validates Host, rejects browser origins outside explicitly configured extension IDs, and sets exact-origin CORS. Origin-less local tools still require a token for analysis. CORS is not authentication. The local user and locally generated model/configuration files are trusted; a compromised local OS, malicious extension, or tampered Python installation is outside the threat model.

## Optional research API

`GET /health` returns `status`, `api_version`, `paired`, `ml_available`, nullable `model_version`, and a non-sensitive model degradation `reason`. Health never returns a credential.

`POST /analyze` requires `Authorization: Bearer <local pairing token>` and JSON:

```json
{
  "scan_id": "example_1",
  "blocks": [{"block_id": "block_0", "text": "Visible instructions", "context": {
    "inside_dialog": false, "has_code": false, "has_copy_button": false
  }}],
  "extraction": {"truncated": false, "main_frame_only": true, "visited_nodes": 40}
}
```

The response contains the scan ID, `verdict`, `detector_mode`, findings (`code`, `message`, `block_id`, `evidence`), nullable model version, measured `processing_ms`, block count, and extraction metadata. `model_scores` is present only with ML. Each score is an uncalibrated classifier output. Timing covers backend detection, not browser/network latency.

Errors: 400 invalid Host, 401 invalid/missing pairing token, 403 forbidden origin, 408 body timeout, 413 oversized body, 422 malformed/invalid schema, 429 rate limited, 503 unconfigured pairing/analysis failure/timeout. Validation responses omit submitted values. The backend never makes outbound requests.

Bounds: 24 blocks; 2,000 characters each; 24,000 total characters; 128 KiB body read incrementally; duplicate IDs and unknown fields rejected. The token-authenticated analysis budget is 60 requests/minute per process. Two dedicated inference threads bound simultaneous CPU work; analysis waits time out after four seconds. Run one Uvicorn worker for the documented in-memory rate limit. Browser inference is synchronous bounded local work; no fetch/remote timeout applies.

## Extraction

A bounded TreeWalker visits at most 6,000 DOM nodes, rejecting private/editable/hidden/script/style subtrees. Its root and ancestors are checked explicitly because TreeWalker does not filter its own root. Text nodes are grouped into nearest dialogs/articles/sections/main or smaller fallback blocks. Dialogs take priority, relevant instruction candidates are deduplicated, and all payload bounds apply. Exclusions are structural and also apply to collected parent text.

This deliberately modest heuristic can miss instructions beyond traversal limits or merge unrelated text inside one article. Truncation returns uncertainty. Visual text in images, CSS pseudo-elements, canvas, child frames, and shadow roots is not extracted. Hidden clipboard commands are not read: the visible lure/execution sequence is the detection target.

## Rules and policy

Text normalization applies NFKC per character, lowercasing and removal of selected zero-width formatting characters; an offset map preserves evidence in raw text. Fixed regex features inspect verification/repair, system interface, paste, execution, suspicious syntax, reporting, and negation.

Verification/repair + system interface + paste + execution is strong evidence, even with no visible command. A dialog containing a lure/system/paste sequence and a copy button is corroborated contextual evidence. A command pattern combined with paste/execute is another strong rule. Reporting context outside a dialog downgrades a strong match to uncertain. Negated advice outside a dialog is not a direct execution request. These are heuristics, not proof of intent; attackers may exploit contextual ambiguities.

Rules are never suppressed merely by hostname. Model scores cannot cancel strong rules. High model scores plus a partial execution/lure signal can strengthen uncertainty to suspicious, except reporting conflict. Score-only concerns remain uncertain. Block results aggregate suspicious > uncertain > no signals. Truncation raises non-suspicious results to uncertain.

TF-IDF word unigrams/bigrams (10,000 feature cap) and logistic regression (`C=1`, max 1,000 iterations, seed 42) use text only. Context affects rules/hybrid policy, enabling an actual no-DOM-context ablation. Feature contributions use TF-IDF × signed logistic coefficient, not generated prose. The reference API loads only a fixed local artifact after metadata/version/hash checks. The hash detects corruption but cannot establish provenance. The browser uses exported JSON with schema/dimension/numeric checks instead of joblib.

## Browser lifecycle

Automatic scans require both an enabled-site setting and current host permission. Dynamic registration runs at document idle in the main frame. MutationObserver debounces one second, with a five-second per-tab request interval, one request in flight, and latest pending work retained. Fingerprints skip unchanged content. Identical automatic payloads use a 30-second in-memory cache; manual scans bypass it. Results are associated with document keys/content revisions and worker generations; identical extraction does not advance the content revision. Navigation aborts old work. Site opt-out or lost permission aborts/discards pending automatic requests, and stopped observers reject automatic results. Settings persist; result state is session-only and removed on navigation/tab close. No browsing log is written.

An isolated shadow-root warning limits CSS interference, not hostile-page control. The popup remains the trusted place to inspect evidence. A hostile page can remove or imitate on-page warnings.
