# Direct review using ECC skills

## Self-contained extension review (0.2.0)

The 0.2.0 work uses the same free ECC testing/security/verification instructions. No
CodeRabbit service, login or external review upload ran. The following are additional
confirmed fixes during the browser-inference port:

- **Medium: stale session verdict after opt-out during commit.** A Chromium test delayed
  the result commit, disabled the site, then released it. The old worker still wrote a
  suspicious result to session storage despite suppressing its page warning. The test
  failed before the fix and passed after. Per-tab write/clear queues and generation
  checks now prevent resurrecting invalidated results; navigation is tested too.
- **Low: dismissed warning repeated on unchanged manual scans.** Warning identity included
  visited-node counts, which change when the warning is removed. Identity now uses the
  verdict, findings and truncation. A real closed-shadow dismiss click followed by a
  manual rescan confirms the warning stays dismissed for unchanged evidence.
- **Low: pause-all coupled to permission removal.** Disabling scanning could finish with
  an error when browser-granted access was non-removable (reproduced with the test fixture's
  required loopback grant). Pause now stops scanning independently; optional browser access
  can be separately revoked. Settings still work if bundled rules cannot initialize.

Security inspection covers no required backend hosts, extension-local fetches only, strict
CSP, no remote code/eval, strict bounded input, text-only evidence rendering, trusted-context
storage, exact sender/type gating, main-document checks and old-token migration. Corrupt
model data falls back visibly to rules; corrupt rules and inference errors become unavailable.
Browser/Python parity checks include scores/verdicts/raw evidence in both detector modes.
This is a bounded assistant-led review, not independent security certification. Current
executed checks and remaining acceptance gates are in verification.md and release.md.

## Earlier local-server version (0.1.0; historical record)

Review date: 2026-11-01 (Asia/Calcutta). The user selected skills that work without a separate review service or subscription. This review applies the installed ECC python-testing, security-review, and verification-loop instructions with the existing assistant, pytest, Ruff, and Chromium. No CodeRabbit invocation, account login, code upload, paid credits, or additional review API was used. The previously installed CodeRabbit CLI remains inactive; it was not uninstalled.

## Reproduced findings and fixes

1. **Editable-root privacy exclusion (high priority):** TreeWalker does not run its filter on the traversal root. A page with `contenteditable` on its body could therefore send editable instruction text despite the exclusion policy. A real Chromium regression reproduced nonempty extracted blocks from an editable body. Extraction now checks the root and its ancestors for excluded/hidden state before traversal.
2. **Unchanged extraction invalidates pending results (medium priority):** Each extraction incremented the document revision, even when the meaningful payload was identical. A background read could invalidate an in-flight manual result. A Chromium regression reproduced consecutive unchanged snapshots with revisions 2 and 3. Revisions now advance only when blocks/context/truncation change; traversal counts do not change content identity.
3. **Automatic scan publishes after opt-out (medium priority):** Disabling automatic scanning stopped the observer but did not cancel a pending worker request. A delayed real backend request reproduced a new suspicious warning after opt-out. Worker state now records the automatic site's pattern and aborts/discards pending automatic work when the site is disabled or its permission is removed. The content script also ignores automatic results once its observer is stopped.

All three failures were reproduced before implementing fixes. The fixes are confined to browser extraction/lifecycle behavior; detector rules, trained weights, dataset labels, split IDs, and held-out evaluation were not tuned or regenerated from these browser tests.

## Verification

- Targeted browser regressions: **3 passed** after all three reproduced failures were fixed.
- Full browser suite: **10 passed** in 51.97 seconds, Chromium 153.0.8010.12 / Playwright 1.56.0.
- Backend/pipeline suite: **31 passed**, **91% coverage**.
- Ruff, Python compilation, JavaScript syntax, dependency consistency, and diff whitespace checks: **passed**.
- High-confidence credential-pattern scan: no matching files; no tracked `.local` or virtual-environment files.
- Static type checking: not configured. Production acceptance: not applicable to this local prototype.

The browser tests use a temporary Chromium profile and real extension/API integration. Existing limitations remain: no independent human-reviewed research corpus or real-world protection estimate, and manual Chrome/Edge arbitrary-host permission acceptance remains separate. This pass found and resolved three confirmed issues; it is not an exhaustive assurance that no other defects exist.

This is an assistant-led code review guided by freely reusable skill instructions, not a claim of an independent audit or a CodeRabbit service result.
