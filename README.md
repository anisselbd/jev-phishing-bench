# Jev vs LLM: a phishing decision benchmark with a calibration audit

Public, reproducible comparison of **Jev** (TypeSafe AI's System One model, launched 15 September 2026) against a
classic LLM on one security decision: should an email agent click the link in this email?

The question this repo answers with numbers: is Jev accurate enough, are its probabilities calibrated, and how much
faster and cheaper is it than an LLM on the same 2 000 emails?

## Results (17 September 2026, 2 000 emails)

| | Jev (jev-1.13.0) | Claude Haiku 4.5 |
|---|---|---|
| Accuracy | 62.6% [60.5, 64.7] | 81.3% [79.5, 82.9] |
| Recall on phishing | 43.2% | 76.4% |
| False positive rate | 18.0% | 13.8% |
| AUROC | 0.689 | 0.837 |
| ECE (10 bins) | 0.154 | 0.097 |
| Latency p50, from France | 239 ms (network floor 163 ms) | 687 ms (network floor 18 ms) |
| Cost per 1 000 emails, list price | $0.038 | $0.462 |
| Probability change between two passes | 2.2% label flips, mean abs diff 0.017, max 0.15 | 0.7% label flips on 300 emails, 98% identical, max diff 0.65 |

Jev's own verdict loses clearly on accuracy (McNemar p < 0.0001) and wins on speed and cost. The surprise is in the
five signal questions asked in the same call: the free-hosting signal alone reaches AUROC 0.96, a fixed rule on it
gives 89.5% accuracy with no fitting, and a cross-validated logistic regression on the five signals reaches 95.1%,
AUROC 0.988, ECE 0.027. Details, intervals, calibration bins, per-category breakdown and the caveats about the
published grid are in `results/report.md`; the charts are `results/chart.png` and `results/signals.png`.

### Controls added after review (17 September 2026)

The signal result above was challenged on three points: no non-AI baseline, selection and evaluation on the same
emails, and no equivalent decomposition for the LLM. Three controls were added (`bench/heuristics.py`,
`bench/protocol.py`, `run_llm_signals.py`); nothing above was changed. Full tables in `results/report.md`, chart in
`results/controls.png`.

- **Non-AI baseline.** A generic list of shorteners, free hosts, IPFS gateways and document-sharing hosts on the
  link, plus an eTLD+1 comparison between sender and link. The list rule alone: 91.6% accuracy,
  83.5% recall, 0.2% false positives on all 2 000 emails. The dataset largely separates by
  construction.
- **Split.** 1 000 emails (half A) choose the signal, its threshold and the regression weights; the other 1 000
  (half B) give the numbers. On B, Jev's best single signal (`sig_free_hosting` >= 0.70) reaches 89.4%,
  below the regex rule at 91.8% (McNemar p = 0.0032). The logistic regression on Jev's five
  signals reaches 95.0% [93.5%, 96.2%], AUROC 0.982, against 91.8% for the
  regression on the two regex features (p = 0.0018).
- **Same questions to the LLM.** `run_llm_signals.py` asks Claude Haiku 4.5 the five signal questions word for word
  in one JSON call per email (2000 calls, 1 API error, 0 format errors, p50 1199 ms,
  $1.02 per 1 000 emails against $0.04 for Jev), then the same rule and regression are applied on the same split.
  On B, Haiku's best single signal (`sig_generic_sender` >= 0.08) reaches 94.2% [92.6%, 95.5%],
  above Jev's single rule (p < 0.0001) and above the regex. Its regression reaches 93.2% [91.5%, 94.6%],
  AUROC 0.991, against 95.0% and AUROC 0.982 for Jev's: the accuracy gap in Jev's favour is not
  significant (McNemar p = 0.063) and the AUROC gap goes the other way.

Outcome of the controls: Jev's best single signal beats neither the two-line regex (89.4% vs 91.8%, p = 0.003) nor
Haiku asked the same question (89.4% vs 94.2%, p < 0.0001). The regression on Jev's five signals beats the regex
(95.0% vs 91.8%, p = 0.002) but is statistically tied with the regression on Haiku's five signals (95.0% vs 93.2%,
p = 0.063, and Haiku's AUROC is higher). What Jev keeps is the price of the decomposition: about 27 times cheaper and
5 times faster than Haiku for signals of comparable quality, on a dataset that a regex already separates at 91.8%.


## Method in one paragraph

Both systems see the same 2 000 emails of the PhishNChips v5.2 benchmark, in the same seeded order, one call per email,
no concurrency. Jev gets the email as a JSON object and nine typed questions in one request (a verdict Choice, a mirror
Noul, five signal Nouls, two alternative wordings of the verdict). The LLM gets the same JSON string inside the
"balanced" system prompt written by the benchmark authors, with only the answer-format sentence changed so it returns
`{"click": 0|1, "phishing_probability": 0..1}`. The baseline model is Claude Haiku 4.5 through the native Messages API,
no thinking, temperature 0. We then compare accuracy, recall, false positive rate, AUROC,
calibration (ECE, Brier, reliability diagram), an auto-decision curve, latency, cost at list price, format errors, and
the stability of probabilities across repeated passes. Every proportion carries a 95% Wilson interval; AUROC, ECE,
Brier and F1 carry a bootstrap interval; the accuracy gap is tested with an exact McNemar test on paired emails.

## Dataset

[PhishNChips v5.2](https://huggingface.co/datasets/AreLit/PhishNChips), April 2026. 1 000 phishing emails built
around real malicious URLs (PhishTank, OpenPhish, GitHub Phishing Database) and 1 000 legitimate workplace emails built
around Tranco domains, 333 of them designed as cross-domain false-positive traps. The email bodies are LLM-generated by
the dataset authors. The release ships a grid of 220 000 evaluations (11 models x 10 system prompts), which lets us
check that our LLM pipeline reproduces a published number.

Why this dataset and not the usual Kaggle corpus: it postdates the training data of the LLMs we compare against, no
model saturates it (published recall runs from 27% to 96% depending on the system prompt), and it has a clean license
story (MIT for the synthetic content, attributed third-party URL sources, see the dataset's `SOURCE_LICENSES.md`).

The data is downloaded at runtime into `data/`, verified against the SHA-256 values of the release manifest, and never
committed.

## Reproduce

Requirements: Python 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env            # then fill in the keys (baseline used: claude-haiku-4-5, Anthropic Messages API)
uv run prepare_data.py          # download + checksum + data/emails.jsonl
uv run net_floor.py             # network round-trip floor to each API host
uv run run_jev.py --limit 10    # smoke test, prints raw answers
uv run run_jev.py               # pass 1, all 2 000 emails
uv run run_jev.py --pass 2      # pass 2, stability
uv run run_jev.py --pass 3 --sample 200   # next day, 200-email subset
uv run run_llm.py --limit 10
uv run run_llm.py               # sequential, resumable; LLM_RPM paces free tiers
uv run run_llm.py --pass 2 --sample 300
uv run analyze.py               # results/metrics.json + results/report.md
uv run charts.py                # results/chart.png + results/signals.png
```

Every run appends to `results/raw/*.jsonl` and skips emails already answered, so an interrupted run resumes without
paying twice. Raw files contain the full emails and are not committed; `results/report.md`, `metrics.json` and the
charts are.

## What Jev is asked

One request per email, `state` = the email object, questions:

| id | type | question |
|---|---|---|
| `verdict` | choice | phishing or legitimate, wording mirrors the authors' balanced prompt |
| `is_phishing` | noul | the same question as a yes/no probability |
| `sig_domain_mismatch` | noul | sender domain differs from the link's domain |
| `sig_free_hosting` | noul | link points to a shortener or free hosting platform |
| `sig_lure` | noul | asks to sign in, verify an account, or open a document |
| `sig_urgency` | noul | pressure, deadline or threat |
| `sig_generic_sender` | noul | webmail address presenting as an organization |
| `verdict_alt_click` | choice | "Should the user click the link?" |
| `verdict_alt_minimal` | choice | "Classify this email." with bare option names |

The exact text is in `run_jev.py`.

### Every verdict wording, not just the chosen one

All four verdict formulations travel in the same call. `verdict` was fixed as the headline before any answer was read;
the others are reported so that nobody can suspect a wording picked after the fact. Numbers on all 2 000 emails:

| Question | Accuracy | AUROC | ECE | Agreement with `verdict` |
|---|---|---|---|---|
| verdict (choice) | 62.6% | 0.689 | 0.154 | 100.0% |
| is_phishing (noul) | 60.6% | 0.684 | 0.172 | 83.2% |
| verdict_alt_click | 63.2% | 0.700 | 0.115 | 80.1% |
| verdict_alt_minimal | 58.4% | 0.635 | 0.241 | 79.2% |

Pearson r between the choice probability and the mirror noul: 0.959. None of the alternatives changes
the conclusion: the best wording gains 0.6 points of accuracy, the worst loses 4.

### What the questions knew about the dataset

The verdict question contains no example and no hint about the dataset. The five signal questions do not name the
dataset either, but they were written after reading its URL-evasion taxonomy (shorteners, IPFS gateways, Firebase,
GitHub Pages, Google Docs), so they target the way this dataset was built. The same knowledge written as two regex
features is the non-AI baseline in `bench/heuristics.py`; that is the fair floor for any signal result.

## Limits, stated up front

- The email bodies are synthetic. The phishing signal lives mostly in the URL, the sender and their consistency, which
  is realistic for 2026 phishing but is not human-written mail.
- Ground truth comes from URL reputation feeds, not from a human reading each email.
- One prompt per system. The published grid shows that LLM recall moves from 27% to 96% with the system prompt alone.
  Jev's own sensitivity is measured with two alternative wordings, in the same call.
- Latency is wall-clock from a machine in France to US-hosted services. `net_floor.py` measures the round trip of a
  tiny request to each host so inference time can be separated from network time.
- Jev publishes an input price only (42 dollars per billion input tokens). The TypeSafe dashboard confirmed it: our two
  passes consumed 4 561 792 tokens (3.66M input, 0.90M output) and were billed 0.15 dollars, which matches input only.
- Costs use list prices even when a run used a free tier.
- The baseline is Claude Haiku 4.5 without thinking, the cheap and fast end of its family. A Gemini 3 Flash run on the
  free tier was attempted first and abandoned: 10 requests per minute plus 503 bursts meant a 14-hour run.

## Layout

```
bench/common.py     shared helpers: env, JSONL, retries, Wilson interval
prepare_data.py     download, checksum, emails.jsonl
run_jev.py          Jev runner, one request per email, nine questions
run_llm.py          OpenAI-compatible LLM runner, authors' balanced prompt
net_floor.py        network floor per host
analyze.py          metrics, intervals, stability, report.md
charts.py           chart.png and signals.png
CLAUDE.md           design decisions and rules for the coding agent
```

## Sources

- TypeSafe docs: https://docs.typesafe.ai (index: https://docs.typesafe.ai/llms.txt)
- PhishNChips: https://huggingface.co/datasets/AreLit/PhishNChips
- Every, "Mini vibe check: TypeSafe's Jev", the only independent test published before this one
