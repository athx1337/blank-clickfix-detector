# Viva guide

**What is ClickFix?** Social engineering that asks a user to move from a webpage into system command execution, often disguised as verification or repair.

**What does BLANK inspect?** Visible English instruction blocks plus small DOM context flags, not the operating system or universal clipboard. A command may be invisible; the requested action sequence can itself justify concern.

**Why TF-IDF/logistic regression?** It is inexpensive, reproducible, CPU-friendly, and its contributing word features can be inspected. The project tests whether it adds useful evidence to readable rules.

**Why not flag PowerShell?** Legitimate technical documentation uses terminals and copy buttons. Strong rules require combinations and context; uncertainty remains visible.

**Why separate validation and test data?** Validation selects thresholds. Test data estimates behavior on held-out families. Repeated paraphrases across splits can inflate apparent performance.

**What does the context ablation test?** Run the same hybrid policy with DOM context flags ignored. It isolates the contribution of dialog/copy context on identical blocks; it does not measure extraction differences.

**Does the model output infection probability?** No. Logistic scores here are uncalibrated classifier outputs on a small synthetic corpus.

**What is original versus reused?** The project-specific API, extraction pipeline, verdict/evaluation integration and interface are implemented for BLANK. Small credited patterns/helper adaptations and development skills are documented in the reuse ledger.

**What can the current evaluation establish?** That the pipeline runs reproducibly on authored examples and produces measurable comparisons. It cannot establish real-world efficacy. Rules and hybrid may tie; that is a valid result, not a reason to alter the test set.

**How is privacy handled?** Detection runs in the extension using bundled rules and JSON model weights. There is no runtime server or pairing. Structural exclusions, trusted-context session storage, explicit website permission, no telemetry, and no persistent browsing log reduce exposure. Local review uses automated unit, lint, and browser test suites.

**Why keep Python?** It trains and evaluates the classifier and provides a reference implementation. The browser reproduces TF-IDF/logistic inference from exported vocabulary, IDF, weights and thresholds; parity tests compare outputs. Users need only the extension.

**What remains?** Human-reviewed independent data, broader extraction coverage, actual user studies, and external validity. Chrome and endpoint tools already provide ClickFix defenses.
