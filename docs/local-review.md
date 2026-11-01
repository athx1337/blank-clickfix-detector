# Direct Review and Quality Assurance

## Self-contained extension review (v0.3.0)

The v0.3.0 release verifies local browser-inference and privacy-first safeguards:

- **Stale session verdict after opt-out during commit:** A Chromium test delayed
  the result commit, disabled the site, then released it. The old worker still wrote a
  suspicious result to session storage despite suppressing its page warning.
  Per-tab write/clear queues and generation checks now prevent resurrecting invalidated results;
  navigation is tested too.
- **Dismissed warning repeated on unchanged manual scans:** Warning identity included
  visited-node counts, which change when the warning is removed. Identity now uses the
  verdict, findings, and truncation status. A real closed-shadow dismiss click followed by a
  manual rescan confirms the warning stays dismissed for unchanged evidence.
- **Pause-all decoupled from permission removal:** Disabling scanning could finish with
  an error when browser-granted access was non-removable. Pause now stops scanning independently;
  optional browser access can be separately revoked. Settings still work if bundled rules cannot initialize.
- **Search engine false-positive mitigation:** Verified that in-page warnings do not activate on
  search engine results pages (Google, Bing, DuckDuckGo) unless an active clipboard payload is present.
  Word boundaries on instructional keywords prevent false alarms on CMS/platform names (e.g., WordPress).
- **AI safety reconciliation:** Validated that high-confidence legitimate AI verdicts override
  partial heuristic lures and restore clean state.

Security inspection covers no required backend hosts, extension-local fetches only, strict
CSP, no remote code/eval, strict bounded input, text-only evidence rendering, trusted-context
storage, exact sender/type gating, main-document checks, and ephemeral session keys. Corrupt
model data falls back visibly to rules; corrupt rules and inference errors become unavailable.
Browser/Python parity checks include scores/verdicts/raw evidence in both detector modes.

## Verification Summary

- Targeted browser regressions: **All passed**.
- Full browser suite: **21 passed**, Chromium / Playwright.
- Backend/pipeline suite: **38 passed**, **73% coverage**.
- Ruff, Python compilation, JavaScript syntax, and diff whitespace checks: **passed**.
- High-confidence credential-pattern scan: no matching files; no tracked `.env`, `.local`, or virtual-environment files.
- Static type checking: not configured. Production acceptance: manual user testing on target browsers.
