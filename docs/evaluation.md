# Evaluation protocol

Research question: does context + lightweight NLP + explicit rules improve ClickFix instruction detection compared with rules alone without excessive alerts on technical documentation?

The four configurations are rules, text ML, hybrid, and hybrid without DOM context. All use the same frozen held-out blocks. The ML vectorizer is fit only on training text. Grouped train/validation/test IDs and the dataset SHA-256 are saved before fitting. Validation selects high-score thresholds independently for ML/hybrid/ablation from 0.50–0.95 in increments of 0.05: precision >=90%, at least five alerts, then highest recall, precision, and threshold as tie-breakers. Hybrid selection evaluates the complete suspicious-decision policy, including unavoidable strong-rule false positives. If no threshold qualifies it stays null and ML remains advisory. These are engineering choices on small data, not validated production confidence.

ML scores >=0.5 below the qualifying high threshold produce uncertainty; 0.5 is the classifier's default boundary, not a calibrated probability claim. Direct strong rules remain active regardless of model output.

`python -m ml.evaluate` checks dataset/model/split hashes and never retrains. Strict confusion matrices use suspicious as detection; uncertain attack blocks count as misses. A separate all-warnings matrix includes uncertainty as a user-facing alert. Uncertain rate and coverage are shown explicitly. This prevents silently improving precision by hiding abstentions.

Reports include precision, recall, F1, false-positive rate, confusion matrices, error examples, median/p95 warm per-block latency, split/model metadata, and synthetic/sourced counts. Dataset text in evaluation reports is intentionally supplied research data, not live browsing capture. The measured results and machine-readable snapshot are recorded after verification in `seed-evaluation.json`.

The small synthetic seed is expected to be easy for its author-defined rules. Identical performance for rules and hybrid establishes no improvement. The context ablation may also be identical; this must be reported. A balanced authored corpus cannot estimate ordinary-browsing precision, population prevalence, or prevention of infection. No user study is included, and successful browser integration is separate from classifier performance.

## Measured seed snapshot

The test partition contains only **14 blocks: 6 clickfix and 8 legitimate**. This is a pipeline check, not a meaningful population accuracy estimate.

| Configuration | Strict precision / recall / F1 | Strict matrix [[TN,FP],[FN,TP]] | Uncertain | Median / p95 ms |
|---|---|---|---|---|
| Rules | 1.000 / 1.000 / 1.000 | [[8,0],[0,6]] | 0/14 | 0.038 / 0.098 |
| ML | 0.667 / 0.667 / 0.667 | [[6,2],[2,4]] | 0/14 | 0.283 / 0.707 |
| Hybrid | 1.000 / 1.000 / 1.000 | [[8,0],[0,6]] | 2/14 | 0.266 / 0.575 |
| Hybrid without DOM context | 1.000 / 1.000 / 1.000 | [[8,0],[0,6]] | 2/14 | 0.259 / 0.549 |

Including uncertain warnings gives hybrid **two legitimate alerts**, compared with zero for rules on this seed. Thus it showed no detection improvement and added caution alerts here. No context-ablation benefit was established. Latencies are warm per-block detector measurements on this machine, not extension end-to-end timings; values vary by run.

Do not optimize against the seed's test errors and subsequently present them as independent evidence. Any later improvement needs newly collected, human-reviewed, held-out families and, where genuine timestamps permit, a forward-in-time evaluation. The target 150–250 reviewed examples remains a follow-up requiring human annotation.
