# Jev vs LLM on PhishNChips v5.2

Generated 2026-09-17T09:38:32.549939+00:00. Dataset: 2000 emails (1 000 phishing, 1 000 legitimate). Jev model served behind `jev-latest`: jev-1.13.0. Jev answered 2000 emails, 0 API errors out of 2000 calls.
claude-haiku-4-5 answered 2000 emails with a valid JSON, 0 format errors and 0 API errors out of 2000 calls.

## Headline comparison

| Metric | Jev (jev-1.13.0) | claude-haiku-4-5 |
|---|---|---|
| Accuracy (95% CI) | 62.6% [60.5%, 64.7%] | 81.3% [79.5%, 82.9%] |
| Recall on phishing | 43.2% [40.2%, 46.3%] | 76.4% [73.7%, 78.9%] |
| False positive rate | 18.0% [15.7%, 20.5%] | 13.8% [11.8%, 16.1%] |
| Precision | 70.6% | 84.7% |
| F1 | 53.6% [50.5%, 56.6%] | 80.3% [78.3%, 82.2%] |
| AUROC | 0.689 [0.667, 0.711] | 0.837 [0.820, 0.853] |
| ECE (10 bins, lower is better) | 0.154 [0.137, 0.176] | 0.097 [0.081, 0.115] |
| Brier score (lower is better) | 0.252 | 0.163 |
| Latency p50 / p95 (from France) | 239 ms / 331 ms | 687 ms / 980 ms |
| Network floor, warm connection p50 | 163 ms | 18 ms |
| Input / output tokens per email | 915 / 225 | 337 / 25 |
| List price in / out per M tokens | $0.042 / not published | $1.0 / $5.0 |
| Cost per 1 000 emails (list price) | $0.0384 | $0.4622 |
| Format errors | 0 (typed output) | 0 |
| JSON wrapped in a code fence despite 'JSON only' | n/a | 2000 |

Ratios: claude-haiku-4-5 is 2.9x slower at p50 and 12x more expensive per email at list price. McNemar exact test on the 2000 paired emails: p = 0.0000 (Jev alone correct on 85, claude-haiku-4-5 alone correct on 459).

Jev tokens include the nine questions sent with every email (verdict, mirror noul, five signals, two alternative wordings). The LLM prompt carries the same email plus the system prompt. Latency is wall-clock from the benchmark machine in France, sequential calls on a reused connection; the network floor row is the round trip of a tiny request on the same connection.

## Auto-decision curve

Share of emails decided without a human when acting only above a probability threshold, and accuracy on those emails.

| Threshold | Jev coverage | Jev accuracy | claude-haiku-4-5 coverage | claude-haiku-4-5 accuracy |
|---|---|---|---|---|
| 0.50 | 100.0% | 62.6% (748 errors) | 100.0% | 81.3% (374 errors) |
| 0.55 | 92.3% | 63.5% (673 errors) | 100.0% | 81.3% (374 errors) |
| 0.60 | 83.9% | 64.5% (595 errors) | 100.0% | 81.3% (374 errors) |
| 0.65 | 75.0% | 66.9% (496 errors) | 99.2% | 81.2% (374 errors) |
| 0.70 | 66.2% | 68.6% (416 errors) | 99.2% | 81.2% (374 errors) |
| 0.75 | 59.1% | 68.9% (368 errors) | 86.8% | 81.6% (320 errors) |
| 0.80 | 51.6% | 69.2% (318 errors) | 75.6% | 81.8% (275 errors) |
| 0.85 | 42.3% | 70.1% (253 errors) | 75.6% | 81.8% (275 errors) |
| 0.90 | 30.8% | 73.9% (161 errors) | 55.4% | 82.5% (194 errors) |
| 0.95 | 16.4% | 85.4% (48 errors) | 54.2% | 82.3% (192 errors) |
| 0.98 | 7.0% | 97.8% (3 errors) | 0.1% | 100.0% (0 errors) |
| 0.99 | 3.8% | 98.7% (1 errors) | 0.0% | n/a (0 errors) |

## Calibration bins (predicted class confidence vs accuracy)

| Bin | Jev n | Jev confidence | Jev accuracy | claude-haiku-4-5 n | claude-haiku-4-5 confidence | claude-haiku-4-5 accuracy |
|---|---|---|---|---|---|---|
| 0.50 to 0.55 | 154 | 52.4% | 51.3% | 0 | n/a | n/a |
| 0.55 to 0.60 | 168 | 56.9% | 53.6% | 0 | n/a | n/a |
| 0.60 to 0.65 | 179 | 62.1% | 44.7% | 15 | 60.0% | 100.0% |
| 0.65 to 0.70 | 175 | 67.0% | 54.3% | 0 | n/a | n/a |
| 0.70 to 0.75 | 142 | 71.9% | 66.2% | 249 | 70.5% | 78.3% |
| 0.75 to 0.80 | 150 | 77.1% | 66.7% | 223 | 75.0% | 79.8% |
| 0.80 to 0.85 | 217 | 82.3% | 65.4% | 405 | 85.0% | 80.0% |
| 0.85 to 0.90 | 199 | 87.6% | 58.8% | 0 | n/a | n/a |
| 0.90 to 0.95 | 287 | 92.1% | 60.6% | 24 | 92.0% | 91.7% |
| 0.95 to 1.00 | 329 | 97.1% | 85.4% | 1084 | 95.0% | 82.3% |

Probability shape. Jev: mean p(phishing) 45.6% on phishing, 25.9% on legitimate, 12.3% of answers below 0.05 or above 0.95, 101 distinct values.
claude-haiku-4-5: mean p(phishing) 62.6% on phishing, 15.4% on legitimate, 0.1% extreme, 10 distinct values.

## Stability of probabilities across passes

| Comparison | n | mean abs diff | p95 abs diff | max abs diff | diff > 0.05 | identical | label flips | Pearson r |
|---|---|---|---|---|---|---|---|---|
| Jev pass 1 vs pass 2 (choice p) | 2000 | 0.0171 | 0.0500 | 0.1500 | 5.2% | 25.9% | 2.2% | 0.9963 |
| Jev pass 1 vs pass 3 (choice p, 12 h later) | 200 | 0.0176 | 0.0500 | 0.0800 | 6.5% | 23.5% | 1.0% | 0.9965 |
| Jev pass 1 vs pass 2 (noul) | 2000 | 0.0106 | 0.0300 | 0.1000 | 1.0% | 35.4% | 2.2% | 0.9970 |
| claude-haiku-4-5 pass 1 vs pass 2 | 300 | 0.0054 | 0.0000 | 0.6500 | 1.7% | 98.0% | 0.7% | 0.9894 |

## Jev: primitives and wording sensitivity

| Question | Accuracy | AUROC | ECE | Agreement with verdict |
|---|---|---|---|---|
| verdict (choice) | 62.6% | 0.689 | 0.154 | 100.0% |
| is_phishing (noul) | 60.6% | 0.684 | 0.172 | 83.2% |
| verdict_alt_click | 63.2% | 0.700 | 0.115 | 80.1% |
| verdict_alt_minimal | 58.4% | 0.635 | 0.241 | 79.2% |

Pearson r between the choice probability and the mirror noul: 0.9586. On a two-option choice, `confidence` is a deterministic function of the probability (r = 0.9997), so the auto-decision curve on confidence is the same curve.

## Jev signals (mean noul by class, AUROC of the signal alone)

| Signal | Mean on phishing | Mean on legitimate | AUROC |
|---|---|---|---|
| sig_domain_mismatch | 0.752 | 0.375 | 0.680 |
| sig_free_hosting | 0.868 | 0.174 | 0.959 |
| sig_lure | 0.610 | 0.252 | 0.829 |
| sig_urgency | 0.050 | 0.071 | 0.390 |
| sig_generic_sender | 0.496 | 0.028 | 0.935 |

## Exploratory: combining Jev's signals in code

Not part of the head-to-head comparison. It asks whether the atomic signals carry more than the verdict, which is the composition pattern TypeSafe's docs recommend.

| Rule | Accuracy | Recall | False positive rate | AUROC | ECE |
|---|---|---|---|---|---|
| Jev verdict alone | 62.6% | 43.2% | 18.0% | 0.689 | 0.154 |
| free-hosting signal >= 0.5, fixed rule | 89.5% [88.0%, 90.7%] | 88.4% | 9.5% | | |
| 5-fold CV logistic on 5 signals + verdict p | 95.1% [94.1%, 96.0%] | 96.1% | 5.9% | 0.988 | 0.027 |

Full-fit weights of the logistic model, for reading only: bias -5.04, sig_domain_mismatch -4.93, sig_free_hosting +9.27, sig_lure +1.00, sig_urgency -0.77, sig_generic_sender +12.24, verdict_p +3.53.

## Controls added after review (17 September 2026)

The section above on combining Jev's signals was flagged as not publishable as is: no non-AI baseline, selection and evaluation on the same emails, and no equivalent decomposition for the LLM. The controls below add those checks. Nothing above was changed.

### Control 1: a baseline with no AI

Two features computed from the email text alone (`bench/heuristics.py`): `hosting_or_shortener`, the link's registered domain or host is in a generic list of URL shorteners, free hosting and static-site platforms, IPFS gateways and document-sharing hosts; `etld1_mismatch`, the registered domain (public suffix list) of the sender differs from the link's. No fitting, no labels. Evaluated on all 2 000 emails.

| Rule | Accuracy (95% CI) | Recall | False positive rate | AUROC |
|---|---|---|---|---|
| link on a shortener or free host | 91.6% [90.4%, 92.8%] | 83.5% [81.1%, 85.7%] | 0.2% [0.1%, 0.7%] | 0.916 |
| sender eTLD+1 differs from link eTLD+1 | 79.2% [77.4%, 81.0%] | 93.1% [91.4%, 94.5%] | 34.6% [31.7%, 37.6%] | 0.792 |
| either of the two | 79.2% [77.4%, 80.9%] | 93.2% [91.5%, 94.6%] | 34.8% [31.9%, 37.8%] |  |
| both | 91.7% [90.4%, 92.8%] | 83.4% [81.0%, 85.6%] | 0.0% [0.0%, 0.4%] |  |
| ordinal score 2 x hosting + mismatch | | | | 0.937 [0.927, 0.948] |

### Control 2: selection on half A, evaluation on half B

Stratified split, seed 20260917: half A has 1000 emails (500 phishing), half B has 1000 (500 phishing). On A only: the single feature with the highest AUROC is chosen, its threshold is the one that maximises accuracy on A, and a logistic regression on all features of the source is fitted (features only, no verdict probability). Every number below is measured on B. The earlier 5-fold cross-validation stays above as a secondary result.

| Source | Single rule chosen on A | Rule accuracy on B (95% CI) | Rule recall / FPR on B | Rule AUROC on B | Logistic accuracy on B (95% CI) | Logistic recall / FPR | Logistic AUROC on B | Logistic ECE |
|---|---|---|---|---|---|---|---|---|
| Jev, five signal nouls | `sig_free_hosting` >= 0.70 | 89.4% [87.3%, 91.2%] | 86.4% / 7.6% | 0.958 [0.948, 0.969] | 95.0% [93.5%, 96.2%] | 97.0% / 7.0% | 0.982 [0.975, 0.989] | 0.024 |
| heuristic, two regex features | `hosting_or_shortener` >= 0.50 | 91.8% [89.9%, 93.3%] | 83.8% / 0.2% | 0.918 [0.900, 0.934] | 91.8% [89.9%, 93.3%] | 83.8% / 0.2% | 0.937 [0.922, 0.952] | 0.006 |
| claude-haiku-4-5, same five questions | `sig_generic_sender` >= 0.08 | 94.2% [92.6%, 95.5%] | 88.8% / 0.4% | 0.949 [0.935, 0.962] | 93.2% [91.5%, 94.6%] | 91.8% / 5.4% | 0.991 [0.987, 0.994] | 0.031 |

Paired comparisons on half B:
- Jev single rule vs heuristic single rule: first alone correct on 19, second alone correct on 43, McNemar p = 0.0032 (n = 1000).
- Jev logistic vs heuristic logistic: first alone correct on 66, second alone correct on 34, McNemar p = 0.0018 (n = 1000).
- Jev single rule vs claude-haiku-4-5 single rule: first alone correct on 34, second alone correct on 82, McNemar p = 0.0000 (n = 1000).
- Jev logistic vs claude-haiku-4-5 logistic: first alone correct on 51, second alone correct on 33, McNemar p = 0.0630 (n = 1000).
- claude-haiku-4-5 logistic vs heuristic logistic: first alone correct on 65, second alone correct on 51, McNemar p = 0.2273 (n = 1000).

Jev logistic weights fitted on A: bias -4.60, sig_domain_mismatch -6.20, sig_free_hosting +10.62, sig_lure +3.96, sig_urgency +1.33, sig_generic_sender +10.73. AUROC of each feature on A: sig_domain_mismatch 0.686, sig_free_hosting 0.960, sig_lure 0.843, sig_urgency 0.390, sig_generic_sender 0.941.
heuristic logistic weights fitted on A: bias -2.29, hosting_or_shortener +7.16, etld1_mismatch +1.10. AUROC of each feature on A: hosting_or_shortener 0.915, etld1_mismatch 0.799.
claude-haiku-4-5 logistic weights fitted on A: bias -5.34, sig_domain_mismatch -2.30, sig_free_hosting +1.20, sig_lure +6.85, sig_urgency +3.94, sig_generic_sender +13.15. AUROC of each feature on A: sig_domain_mismatch 0.923, sig_free_hosting 0.935, sig_lure 0.867, sig_urgency 0.802, sig_generic_sender 0.956.

### Control 3: the same five questions asked to the LLM

claude-haiku-4-5 received the five signal questions of `run_jev.py` word for word in one JSON call per email (`run_llm_signals.py`), temperature 0, no thinking. 2000 calls, 1 API errors, 0 format errors, 1999 answers wrapped in a code fence. Latency p50 1199 ms, p95 1537 ms. 616 input and 80 output tokens per email, $1.016 per 1 000 emails at list price. The split results are in the table above.

| Signal | claude-haiku-4-5 mean on phishing | mean on legitimate | Jev mean on phishing | Jev mean on legitimate |
|---|---|---|---|---|
| sig_domain_mismatch | 0.825 | 0.213 | 0.752 | 0.375 |
| sig_free_hosting | 0.829 | 0.153 | 0.868 | 0.174 |
| sig_lure | 0.536 | 0.228 | 0.610 | 0.252 |
| sig_urgency | 0.126 | 0.051 | 0.050 | 0.071 |
| sig_generic_sender | 0.720 | 0.002 | 0.496 | 0.028 |

### Control 4: the verdict wordings that were not chosen

All four verdict formulations were sent in the same call from the start; `verdict` was fixed as the headline before any answer was read. Their full-dataset numbers are in the table 'Jev: primitives and wording sensitivity' above.

### Control 5: what the questions knew about the dataset

The verdict question contains no example and no hint about the dataset. The five signal questions do not either in their text, but they were written after reading the dataset's URL-evasion taxonomy (shorteners, IPFS, Firebase, GitHub Pages, Google Docs), so they target the way this dataset was built. That is why control 1 exists: the same knowledge, expressed as a regex, is the fair floor for the signals.

## Accuracy by URL category of the dataset

| Category | Class | n | Jev accuracy | claude-haiku-4-5 accuracy |
|---|---|---|---|---|
| firebase | phishing | 101 | 45.5% [36.2%, 55.2%] | 100.0% [96.3%, 100.0%] |
| github_pages | phishing | 227 | 17.2% [12.8%, 22.6%] | 84.6% [79.3%, 88.7%] |
| google_docs | phishing | 196 | 1.5% [0.5%, 4.4%] | 3.1% [1.4%, 6.5%] |
| hosting_platform | phishing | 17 | 100.0% [81.6%, 100.0%] | 100.0% [81.6%, 100.0%] |
| ipfs | phishing | 102 | 60.8% [51.1%, 69.7%] | 100.0% [96.4%, 100.0%] |
| other_https | phishing | 13 | 53.8% [29.1%, 76.8%] | 100.0% [77.2%, 100.0%] |
| short_clean_https | phishing | 190 | 83.2% [77.2%, 87.8%] | 94.7% [90.6%, 97.1%] |
| url_shortener | phishing | 154 | 64.9% [57.1%, 72.0%] | 99.4% [96.4%, 99.9%] |
| cross_domain_legitimate | legitimate | 333 | 55.0% [49.6%, 60.2%] | 86.8% [82.7%, 90.0%] |
| legitimate | legitimate | 667 | 95.5% [93.7%, 96.8%] | 85.9% [83.1%, 88.3%] |

## Comparison with the published PhishNChips grid

The dataset's `reference_results.csv` reports, for anthropic/claude-haiku-4.5 with the balanced prompt, recall 95.6% and false positive rate 79.9%. Our run with the same system prompt and a JSON answer format gives recall 76.4% [73.7%, 78.9%] and false positive rate 13.8% [11.8%, 16.1%].

We could not use the published grid as a reproduction check. Joining the raw `benchmark_results.csv` rows to the core email labels by sample id gives every one of the 11 models the same 5.7% recall, which is impossible and points to an id or label mismatch in that file; its `true_label` column mixes `0`, `0.0`, `1` and `1.0` and does not sum to 1 000 per class. For Claude Haiku 4.5 the raw rows contain exactly 1 000 'don't click' answers while the published recall and false positive rate imply about 1 755. Our numbers therefore stand on their own; the published ones are quoted as context only.

## Method notes

- Same 2 000 emails for both systems, seeded fixed order, one call per email, no concurrency.
- Jev state is the email as a JSON object; the LLM receives the same JSON string inside the authors' balanced prompt.
- Jev verdict is the choice with the highest probability. The LLM verdict is its click decision; its probability is the verbalized phishing_probability.
- Confidence intervals: Wilson for proportions, percentile bootstrap (2 000 resamples) for AUROC, ECE, Brier and F1.
- Costs use list prices. Jev has no published output price; the TypeSafe dashboard billed our two passes (4 561 792 tokens, 0.90M of them output) 0.15 dollars, which matches input-only billing, so output tokens are counted at zero.
