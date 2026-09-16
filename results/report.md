# Jev vs LLM on PhishNChips v5.2

Generated 2026-09-16T21:55:04.792101+00:00. Dataset: 2000 emails (1 000 phishing, 1 000 legitimate). Jev model served behind `jev-latest`: jev-1.13.0. Jev answered 2000 emails, 0 API errors out of 2000 calls.

## Headline comparison

| Metric | Jev (jev-1.13.0) |
|---|---|
| Accuracy (95% CI) | 62.6% [60.5%, 64.7%] |
| Recall on phishing | 43.2% [40.2%, 46.3%] |
| False positive rate | 18.0% [15.7%, 20.5%] |
| Precision | 70.6% |
| F1 | 53.6% [50.5%, 56.6%] |
| AUROC | 0.689 [0.667, 0.711] |
| ECE (10 bins, lower is better) | 0.154 [0.137, 0.176] |
| Brier score (lower is better) | 0.252 |
| Latency p50 / p95 (from France) | 239 ms / 331 ms |
| Network floor, warm connection p50 | 163 ms |
| Input / output tokens per email | 915 / 225 |
| List price in / out per M tokens | $0.042 / not published |
| Cost per 1 000 emails (list price) | $0.0384 |
| Format errors | 0 (typed output) |

Jev tokens include the nine questions sent with every email (verdict, mirror noul, five signals, two alternative wordings). The LLM prompt carries the same email plus the system prompt. Latency is wall-clock from the benchmark machine in France, sequential calls on a reused connection; the network floor row is the round trip of a tiny request on the same connection.

## Auto-decision curve

Share of emails decided without a human when acting only above a probability threshold, and accuracy on those emails.

| Threshold | Jev coverage | Jev accuracy |
|---|---|---|
| 0.50 | 100.0% | 62.6% (748 errors) |
| 0.55 | 92.3% | 63.5% (673 errors) |
| 0.60 | 83.9% | 64.5% (595 errors) |
| 0.65 | 75.0% | 66.9% (496 errors) |
| 0.70 | 66.2% | 68.6% (416 errors) |
| 0.75 | 59.1% | 68.9% (368 errors) |
| 0.80 | 51.6% | 69.2% (318 errors) |
| 0.85 | 42.3% | 70.1% (253 errors) |
| 0.90 | 30.8% | 73.9% (161 errors) |
| 0.95 | 16.4% | 85.4% (48 errors) |
| 0.98 | 7.0% | 97.8% (3 errors) |
| 0.99 | 3.8% | 98.7% (1 errors) |

## Calibration bins (predicted class confidence vs accuracy)

| Bin | Jev n | Jev confidence | Jev accuracy |
|---|---|---|---|
| 0.50 to 0.55 | 154 | 52.4% | 51.3% |
| 0.55 to 0.60 | 168 | 56.9% | 53.6% |
| 0.60 to 0.65 | 179 | 62.1% | 44.7% |
| 0.65 to 0.70 | 175 | 67.0% | 54.3% |
| 0.70 to 0.75 | 142 | 71.9% | 66.2% |
| 0.75 to 0.80 | 150 | 77.1% | 66.7% |
| 0.80 to 0.85 | 217 | 82.3% | 65.4% |
| 0.85 to 0.90 | 199 | 87.6% | 58.8% |
| 0.90 to 0.95 | 287 | 92.1% | 60.6% |
| 0.95 to 1.00 | 329 | 97.1% | 85.4% |

Probability shape. Jev: mean p(phishing) 45.6% on phishing, 25.9% on legitimate, 12.3% of answers below 0.05 or above 0.95, 101 distinct values.

## Stability of probabilities across passes

| Comparison | n | mean abs diff | p95 abs diff | max abs diff | diff > 0.05 | identical | label flips | Pearson r |
|---|---|---|---|---|---|---|---|---|
| Jev pass 1 vs pass 2 (choice p) | 219 | 0.0168 | 0.0510 | 0.0800 | 5.5% | 27.4% | 3.2% | 0.9963 |
| Jev pass 1 vs pass 3 (choice p, next day) | 0 | not run | | | | | | |
| Jev pass 1 vs pass 2 (noul) | 219 | 0.0095 | 0.0300 | 0.0400 | 0.0% | 36.5% | 3.2% | 0.9975 |

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

## Accuracy by URL category of the dataset

| Category | Class | n | Jev accuracy |
|---|---|---|---|
| firebase | phishing | 101 | 45.5% [36.2%, 55.2%] |
| github_pages | phishing | 227 | 17.2% [12.8%, 22.6%] |
| google_docs | phishing | 196 | 1.5% [0.5%, 4.4%] |
| hosting_platform | phishing | 17 | 100.0% [81.6%, 100.0%] |
| ipfs | phishing | 102 | 60.8% [51.1%, 69.7%] |
| other_https | phishing | 13 | 53.8% [29.1%, 76.8%] |
| short_clean_https | phishing | 190 | 83.2% [77.2%, 87.8%] |
| url_shortener | phishing | 154 | 64.9% [57.1%, 72.0%] |
| cross_domain_legitimate | legitimate | 333 | 55.0% [49.6%, 60.2%] |
| legitimate | legitimate | 667 | 95.5% [93.7%, 96.8%] |

## Method notes

- Same 2 000 emails for both systems, seeded fixed order, one call per email, no concurrency.
- Jev state is the email as a JSON object; the LLM receives the same JSON string inside the authors' balanced prompt.
- Jev verdict is the choice with the highest probability. The LLM verdict is its click decision; its probability is the verbalized phishing_probability.
- Confidence intervals: Wilson for proportions, percentile bootstrap (2 000 resamples) for AUROC, ECE, Brier and F1.
- Costs use list prices even when the run used a free tier. Jev has no published output price, so its output tokens are billed at zero.
