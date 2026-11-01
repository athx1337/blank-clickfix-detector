# Manual Chrome/Edge acceptance

These are instructions, not claims that manual browser checks were executed. See `verification.md` for actual results.

1. Load the unmodified `extension` folder (or extracted release ZIP) in Chrome/Edge. Confirm introduction and **Check local detector** work with no Python process. Pin the toolbar icon.
2. Open the local lab at port 8080. Scan verification: expect suspicious with a verification/system-execution passage despite no visible command.
3. Scan repair: expect suspicious with paste/run evidence. Scan the tutorial and normal CAPTCHA: rules-only mode should find no suspicious signals. Hybrid can legitimately show model uncertainty; it must explain this rather than claim danger from PowerShell alone.
4. Scan the ordinary page: expect a limited no-signals result. Scan the reporting page: expect uncertainty, not automatic proof of an attack.
5. Keep Uvicorn stopped. Disconnect external internet while using the already-loaded local demos: scans must still work. Service-worker DevTools must show no outgoing HTTP/HTTPS analysis requests. Corrupt bundles are tested automatically on temporary copies, not your installed source.
6. On the dynamic demo, enable automatic scanning. Accept website access if requested, insert the simulated instructions, and wait up to seven seconds. Expect a warning. Dismiss it; unchanged content must not repeatedly warn.
7. Disable automatic scanning, reload the dynamic page, insert again, and confirm no automatic warning/request. Remove optional website access through browser settings and repeat on an ordinary HTTP/HTTPS host.
8. Navigate to a different page during a scan. The old document's result must not be shown on the new document. Scan `chrome://extensions`, `edge://extensions`, `about:blank`, and local files: expect unsupported or a clear browser-access limitation.
9. Add a password input, textarea, contenteditable region, hidden instruction, and an HTML-like evidence passage on a local fixture. Inspect extraction through extension service-worker DevTools. Private/hidden values must be absent; displayed evidence must remain text.

10. Decline optional website permission: the toggle must revert and background scanning must stay off. Grant it, then revoke it in browser settings; existing observers and registrations must stop. Test a second unrelated hostname so an earlier permission cannot mask this behavior.
11. Use **Disable automatic scanning everywhere** in Settings. Reload enabled sites and insert instructions: no background scan. Website permission can remain granted; browser settings provide separate revocation.
12. Close/restart the browser: enabled-site settings should persist; previous results should not. Terminate/restart the worker in DevTools and verify a fresh manual scan and enabled-site automatic scan. Upgrade/reload and repeat; no stale token should remain.

For arbitrary websites, clicking the actual browser action grants `activeTab`; opening popup.html as a normal tab is not an equivalent permission test. The shipped manifest has **no required host permissions**. Automated UI tests explicitly add loopback host access to a temporary copy because they open popup.html in a test tab. Test real action access and host prompts manually in both browsers using the unmodified package.
