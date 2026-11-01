# Literature and prior work

Reviewed on 2026-11-01. Research evidence, threat reporting, and source inspection serve different purposes; none establishes BLANK's effectiveness.

1. Arp et al., **Dos and Don'ts of Machine Learning in Computer Security**, USENIX Security 2022. [Primary publication](https://www.usenix.org/conference/usenixsecurity22/presentation/arp). Documents recurring sampling, labeling, leakage, baseline, and measurement pitfalls. Design implication: simple baselines, train-only fitting, real provenance, explicit errors, and no invented accuracy.
2. Pendlebury et al., **TESSERACT: Eliminating Experimental Bias in Malware Classification across Space and Time**, USENIX Security 2019. [Primary publication](https://www.usenix.org/conference/usenixsecurity19/presentation/pendlebury). Studies distribution/time bias in Android malware evaluation. Transfer to BLANK is methodological: preserve family groups and genuine dates, and avoid treating a balanced corpus as representative browsing. It is not a ClickFix webpage result.
3. Sunshine et al., **Crying Wolf: An Empirical Study of SSL Warning Effectiveness**, USENIX Security 2009. [Primary paper](https://www.usenix.org/legacy/events/sec09/tech/full_papers/sunshine.pdf). Examines warning comprehension and effectiveness. Design implication: concise contextual explanations and avoidance of unnecessary repeated warnings. It does not validate BLANK's warning UI or prove infection prevention.
4. Wijaya et al., **Analysis of the ClickFix Social Engineering Technique in Malware Distribution via PowerShell**, ISITIA, July 2026, DOI [10.1109/ISITIA71267.2026.11642283](https://doi.org/10.1109/ISITIA71267.2026.11642283). Bibliographic metadata was verified through DOI/Crossref. Full text and primary abstract were unavailable during review; findings remain unverified and are not used to support experimental claims.

## Primary threat reports and existing defenses

- [Microsoft, Think before you Click(Fix), 2025-08-21](https://www.microsoft.com/en-us/security/blog/2025/08/21/think-before-you-clickfix-analyzing-the-clickfix-social-engineering-technique/): documents verification lures, copied commands, and execution interfaces. It supports testing action sequences without requiring visible payload text. These are documented attack mechanisms, not a benchmark for our model.
- [Microsoft Digital Defense Report 2026](https://www.microsoft.com/en-us/security/security-insider/threat-landscape/2026-digital-defense-report): describes attacker-supplied ClickFix-style commands executing on over 1.1 million unique devices between February and early May 2026. This is execution telemetry, not proof that every device was infected.
- [Google, Our latest defenses against evolving web scams, 2026-10-20](https://blog.google/security/our-latest-defenses-against-evolving-web-scams/): describes ClickFix protection for Chrome Enhanced Protection users. BLANK makes no first-defense or comparative browser-performance claim.

## Official implementation references

- [Chrome cross-origin requests](https://developer.chrome.com/docs/extensions/develop/concepts/network-requests)
- [Chrome scripting](https://developer.chrome.com/docs/extensions/reference/api/scripting)
- [Chrome permissions](https://developer.chrome.com/docs/extensions/reference/api/permissions)
- [Chrome storage and access levels](https://developer.chrome.com/docs/extensions/reference/api/storage)
- [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/)
- [scikit-learn model persistence](https://scikit-learn.org/stable/model_persistence.html)
- [Playwright extension testing](https://playwright.dev/docs/chrome-extensions)
