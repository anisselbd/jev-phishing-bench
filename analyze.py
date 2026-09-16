"""Compute every benchmark metric from the raw run files and write results/metrics.json and results/report.md.

Inputs: data/emails.jsonl, results/raw/jev_pass*.jsonl, results/raw/llm_pass*.jsonl, results/net_floor.json,
data/phishnchips/reference_results.csv. The LLM side is optional: the report is produced for Jev alone if no
LLM run exists.

Usage: uv run analyze.py [--raw-dir results/raw] [--out-dir results] [--bootstrap 2000]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from bench.common import DATA_DIR, RAW_DIR, RESULTS_DIR, SEED, env, env_float, load_emails, read_jsonl, wilson

JEV_PRICE_IN = 0.042  # USD per million input tokens, typesafe.ai homepage, 16 Sept 2026
JEV_PRICE_OUT = 0.0  # no output price published
THRESHOLDS = [round(0.5 + 0.05 * i, 2) for i in range(10)] + [0.98, 0.99]
SIGNALS = ["sig_domain_mismatch", "sig_free_hosting", "sig_lure", "sig_urgency", "sig_generic_sender"]


# ----------------------------------------------------------------------------- loading


def jev_model_name(path: Path) -> str:
    names = {r.get("model") for r in read_jsonl(path) if r.get("ok") and r.get("model")}
    return ", ".join(sorted(names)) or "jev-latest"


def load_jev(path: Path) -> dict[str, dict]:
    rows = {}
    for r in read_jsonl(path):
        if not r.get("ok"):
            continue
        a = r["answers"]
        v = a["verdict"]
        rows[r["id"]] = {
            "y": r["y"],
            "p": float(v["probabilities"]["phishing"]),
            "pred": 1 if v["choice"] == "phishing" else 0,
            "conf": float(v["confidence"]),
            "noul": float(a["is_phishing"]["noul"]),
            "alt_click": 1 if a["verdict_alt_click"]["choice"] == "do_not_click" else 0,
            "alt_click_p": float(a["verdict_alt_click"]["probabilities"]["do_not_click"]),
            "alt_min": 1 if a["verdict_alt_minimal"]["choice"] == "phishing" else 0,
            "alt_min_p": float(a["verdict_alt_minimal"]["probabilities"]["phishing"]),
            "signals": {s: float(a[s]["noul"]) for s in SIGNALS if s in a},
            "latency": r["latency_s"],
            "tok_in": int(r.get("usage", {}).get("input_tokens", 0) or 0),
            "tok_out": int(r.get("usage", {}).get("output_tokens", 0) or 0),
        }
    return rows


def load_llm(path: Path) -> tuple[dict[str, dict], dict]:
    rows, meta = {}, {"api_errors": 0, "format_errors": 0, "attempted": 0, "model": None}
    for r in read_jsonl(path):
        meta["attempted"] += 1
        meta["model"] = meta["model"] or r.get("model")
        if not r.get("ok"):
            meta["api_errors"] += 1
            continue
        if "answer" not in r:
            meta["format_errors"] += 1
            # still count latency and tokens: the call happened and was billed
            rows[r["id"]] = {
                "y": r["y"], "p": None, "pred": None, "latency": r["latency_s"],
                "tok_in": int(r["usage"].get("input_tokens", 0) or 0), "tok_out": int(r["usage"].get("output_tokens", 0) or 0),
            }
            continue
        ans = r["answer"]
        rows[r["id"]] = {
            "y": r["y"],
            "p": float(ans["phishing_probability"]),
            "pred": 1 if ans["click"] == 0 else 0,
            "latency": r["latency_s"],
            "tok_in": int(r["usage"].get("input_tokens", 0) or 0),
            "tok_out": int(r["usage"].get("output_tokens", 0) or 0),
        }
    return rows, meta


def count_errors(path: Path) -> tuple[int, int]:
    rows = read_jsonl(path)
    return len(rows), sum(1 for r in rows if not r.get("ok"))


# ----------------------------------------------------------------------------- metrics


def auroc(y: np.ndarray, p: np.ndarray) -> float:
    """Rank-based AUROC (Mann-Whitney), ties get half credit."""
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order))
    all_p = np.concatenate([pos, neg])[order]
    i = 0
    while i < len(all_p):
        j = i
        while j + 1 < len(all_p) and all_p[j + 1] == all_p[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def ece(y: np.ndarray, p: np.ndarray, pred: np.ndarray, bins: int = 10) -> tuple[float, list[dict]]:
    """ECE on the confidence of the predicted class (max(p, 1-p)), 10 equal-width bins."""
    conf = np.where(pred == 1, p, 1 - p)
    correct = (pred == y).astype(float)
    edges = np.linspace(0.5, 1.0, bins + 1)
    total, out = 0.0, []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (conf >= lo) & (conf < hi) if hi < 1.0 else (conf >= lo) & (conf <= hi)
        n = int(mask.sum())
        if n == 0:
            out.append({"lo": float(lo), "hi": float(hi), "n": 0})
            continue
        acc, c = float(correct[mask].mean()), float(conf[mask].mean())
        total += n / len(y) * abs(acc - c)
        out.append({"lo": float(lo), "hi": float(hi), "n": n, "accuracy": acc, "confidence": c})
    return float(total), out


def reliability_phish(y: np.ndarray, p: np.ndarray, bins: int = 10) -> list[dict]:
    """Observed phishing rate per bin of predicted phishing probability (for the reliability diagram)."""
    edges = np.linspace(0.0, 1.0, bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi) if hi < 1.0 else (p >= lo) & (p <= hi)
        n = int(mask.sum())
        if n == 0:
            out.append({"lo": float(lo), "hi": float(hi), "n": 0})
        else:
            out.append({"lo": float(lo), "hi": float(hi), "n": n, "observed": float(y[mask].mean()), "predicted": float(p[mask].mean())})
    return out


def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def classification(y: np.ndarray, pred: np.ndarray) -> dict:
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    n = len(y)
    acc = wilson(tp + tn, n)
    rec = wilson(tp, tp + fn)
    fpr = wilson(fp, fp + tn)
    prec = tp / (tp + fp) if tp + fp else float("nan")
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else float("nan")
    return {
        "n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "accuracy": acc[0], "accuracy_ci": [acc[1], acc[2]],
        "recall": rec[0], "recall_ci": [rec[1], rec[2]],
        "fpr": fpr[0], "fpr_ci": [fpr[1], fpr[2]],
        "precision": prec, "f1": f1,
    }


def bootstrap_ci(fn, y: np.ndarray, p: np.ndarray, pred: np.ndarray, n_boot: int, rng: np.random.Generator) -> list[float]:
    vals = []
    n = len(y)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        vals.append(fn(y[idx], p[idx], pred[idx]))
    return [float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))]


def auto_decision(y: np.ndarray, p: np.ndarray, pred: np.ndarray) -> list[dict]:
    conf = np.where(pred == 1, p, 1 - p)
    correct = pred == y
    out = []
    for t in THRESHOLDS:
        mask = conf >= t
        n = int(mask.sum())
        acc = float(correct[mask].mean()) if n else float("nan")
        out.append({"threshold": t, "coverage": n / len(y), "n": n, "accuracy": acc, "errors": int((~correct[mask]).sum())})
    return out


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value. b = only system A correct, c = only system B correct."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / 2**n
    return min(1.0, 2 * tail)


def latency_stats(values: list[float]) -> dict:
    if not values:
        return {}
    v = sorted(values)
    return {
        "n": len(v),
        "p50_s": statistics.median(v),
        "p95_s": v[min(len(v) - 1, int(0.95 * len(v)))],
        "mean_s": statistics.fmean(v),
        "min_s": v[0],
        "max_s": v[-1],
    }


def stability(a: dict[str, dict], b: dict[str, dict], key: str = "p", pred_key: str = "pred") -> dict:
    ids = [i for i in a if i in b and a[i].get(key) is not None and b[i].get(key) is not None]
    if len(ids) < 2:
        return {"n": len(ids)}
    pa = np.array([a[i][key] for i in ids])
    pb = np.array([b[i][key] for i in ids])
    d = np.abs(pa - pb)
    flips = sum(1 for i in ids if a[i][pred_key] != b[i][pred_key])
    return {
        "n": len(ids),
        "mean_abs_diff": float(d.mean()),
        "p95_abs_diff": float(np.percentile(d, 95)),
        "max_abs_diff": float(d.max()),
        "frac_diff_over_0_05": float((d > 0.05).mean()),
        "identical_frac": float((d == 0).mean()),
        "label_flip_rate": flips / len(ids),
        "pearson_r": float(np.corrcoef(pa, pb)[0, 1]) if pa.std() > 0 and pb.std() > 0 else float("nan"),
    }


def logistic_fit(X: np.ndarray, y: np.ndarray, iters: int = 200, l2: float = 1e-2) -> np.ndarray:
    """Plain Newton-Raphson logistic regression with a small ridge penalty. X already has a bias column."""
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        z = X @ w
        pr = 1 / (1 + np.exp(-z))
        grad = X.T @ (pr - y) + l2 * w
        H = (X * (pr * (1 - pr))[:, None]).T @ X + l2 * np.eye(X.shape[1])
        step = np.linalg.solve(H, grad)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w


def composite_signals(rows: dict[str, dict], rng: np.random.Generator, folds: int = 5) -> dict:
    """Exploratory: can code combine Jev's atomic signals better than Jev's own verdict?

    Two rules. (a) A single fixed rule decided before looking at the labels: phishing if the free-hosting signal is
    at least 0.5. (b) A 5-fold cross-validated logistic regression on the five signals plus the verdict probability,
    so every email is scored by a model that never saw its label.
    """
    ids = sorted(i for i in rows if len(rows[i]["signals"]) == len(SIGNALS))
    y = np.array([rows[i]["y"] for i in ids])
    S = np.array([[rows[i]["signals"][s] for s in SIGNALS] for i in ids])
    pv = np.array([rows[i]["p"] for i in ids])
    out = {"n": len(ids)}
    rule = (S[:, SIGNALS.index("sig_free_hosting")] >= 0.5).astype(int)
    out["rule_free_hosting"] = classification(y, rule)
    X = np.column_stack([np.ones(len(ids)), S, pv])
    order = rng.permutation(len(ids))
    cv_p = np.zeros(len(ids))
    for k in range(folds):
        test = order[k::folds]
        train = np.setdiff1d(order, test)
        w = logistic_fit(X[train], y[train])
        cv_p[test] = 1 / (1 + np.exp(-(X[test] @ w)))
    cv_pred = (cv_p >= 0.5).astype(int)
    d = classification(y, cv_pred)
    d["auroc"] = auroc(y, cv_p)
    d["ece"] = ece(y, cv_p, cv_pred)[0]
    d["brier"] = brier(y, cv_p)
    d["auto_decision"] = auto_decision(y, cv_p, cv_pred)
    w_full = logistic_fit(X, y)
    d["weights_full_fit"] = {name: float(v) for name, v in zip(["bias"] + SIGNALS + ["verdict_p"], w_full)}
    out["cv_logistic"] = d
    return out


def by_category(rows: dict[str, dict], emails: dict[str, dict]) -> dict:
    out: dict[str, dict] = {}
    for i, r in rows.items():
        if r.get("pred") is None:
            continue
        cat = emails[i]["url_category"]
        d = out.setdefault(cat, {"n": 0, "correct": 0, "y": emails[i]["y"]})
        d["n"] += 1
        d["correct"] += int(r["pred"] == r["y"])
    for cat, d in out.items():
        p, lo, hi = wilson(d["correct"], d["n"])
        d["accuracy"] = p
        d["accuracy_ci"] = [lo, hi]
    return out


def evaluate(rows: dict[str, dict], n_boot: int, rng: np.random.Generator) -> dict:
    valid = {i: r for i, r in rows.items() if r.get("p") is not None and r.get("pred") is not None}
    ids = sorted(valid)
    y = np.array([valid[i]["y"] for i in ids])
    p = np.array([valid[i]["p"] for i in ids])
    pred = np.array([valid[i]["pred"] for i in ids])
    ece_val, ece_bins = ece(y, p, pred)
    out = classification(y, pred)
    out.update(
        {
            "auroc": auroc(y, p),
            "auroc_ci": bootstrap_ci(lambda yy, pp, pr: auroc(yy, pp), y, p, pred, n_boot, rng),
            "ece": ece_val,
            "ece_ci": bootstrap_ci(lambda yy, pp, pr: ece(yy, pp, pr)[0], y, p, pred, n_boot, rng),
            "ece_bins": ece_bins,
            "reliability": reliability_phish(y, p),
            "brier": brier(y, p),
            "brier_ci": bootstrap_ci(lambda yy, pp, pr: brier(yy, pp), y, p, pred, n_boot, rng),
            "f1_ci": bootstrap_ci(lambda yy, pp, pr: classification(yy, pr)["f1"], y, p, pred, n_boot, rng),
            "auto_decision": auto_decision(y, p, pred),
            "prob_summary": {
                "mean_p_on_phishing": float(p[y == 1].mean()),
                "mean_p_on_legit": float(p[y == 0].mean()),
                "frac_extreme": float(((p < 0.05) | (p > 0.95)).mean()),
                "distinct_values": int(len(np.unique(np.round(p, 3)))),
            },
        }
    )
    lat = [r["latency"] for r in rows.values()]
    out["latency"] = latency_stats(lat)
    out["tokens"] = {
        "input": int(sum(r["tok_in"] for r in rows.values())),
        "output": int(sum(r["tok_out"] for r in rows.values())),
        "calls": len(rows),
    }
    return out


def cost(tokens: dict, price_in: float, price_out: float) -> dict:
    total = tokens["input"] / 1e6 * price_in + tokens["output"] / 1e6 * price_out
    per_1000 = total / tokens["calls"] * 1000 if tokens["calls"] else float("nan")
    return {"price_in_per_m": price_in, "price_out_per_m": price_out, "total_usd": total, "per_1000_emails_usd": per_1000}


def reference_row(model: str | None) -> dict | None:
    path = DATA_DIR / "phishnchips" / "reference_results.csv"
    if not model or not path.exists():
        return None
    wanted = env("LLM_GRID_MODEL", "") or model
    norm = lambda s: s.lower().split("/")[-1].replace("-preview", "").replace(".", "-")
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["strategy"] == "balanced" and norm(row["model"]) == norm(wanted):
                return {"model": row["model"], "recall": float(row["recall"]), "fpr": float(row["fpr"]), "safetility": float(row["safetility"])}
    return None


# ----------------------------------------------------------------------------- report


def f(x, digits=1):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100*x:.{digits}f}%"


def ci(v, digits=1):
    return f"[{f(v[0], digits)}, {f(v[1], digits)}]" if v else ""


def ms(x):
    return "n/a" if x is None else f"{1000*x:.0f} ms"


def usd(x, digits=4):
    return "n/a" if x is None or math.isnan(x) else f"${x:.{digits}f}"


def write_report(m: dict, out: Path) -> None:
    jev, llm = m["jev"], m.get("llm")
    llm_name = m.get("llm_model") or "LLM"
    L = []
    L.append("# Jev vs LLM on PhishNChips v5.2")
    L.append("")
    L.append(f"Generated {m['generated_at']}. Dataset: {m['n_emails']} emails (1 000 phishing, 1 000 legitimate). "
             f"Jev model served behind `jev-latest`: {m.get('jev_model')}. Jev answered {jev['n']} emails, {m['jev_errors']['api_errors']} API errors out of {m['jev_errors']['attempted']} calls.")
    if llm:
        L.append(f"{llm_name} answered {llm['n']} emails with a valid JSON, {m['llm_errors']['format_errors']} format errors and "
                 f"{m['llm_errors']['api_errors']} API errors out of {m['llm_errors']['attempted']} calls.")
    L.append("")
    L.append("## Headline comparison")
    L.append("")
    cols = ["Metric", f"Jev ({m.get('jev_model', 'jev-latest')})"] + ([llm_name] if llm else [])
    L.append("| " + " | ".join(cols) + " |")
    L.append("|" + "---|" * len(cols))

    def row(name, jv, lv=""):
        L.append(f"| {name} | {jv} |" + (f" {lv} |" if llm else ""))

    row("Accuracy (95% CI)", f"{f(jev['accuracy'])} {ci(jev['accuracy_ci'])}", f"{f(llm['accuracy'])} {ci(llm['accuracy_ci'])}" if llm else "")
    row("Recall on phishing", f"{f(jev['recall'])} {ci(jev['recall_ci'])}", f"{f(llm['recall'])} {ci(llm['recall_ci'])}" if llm else "")
    row("False positive rate", f"{f(jev['fpr'])} {ci(jev['fpr_ci'])}", f"{f(llm['fpr'])} {ci(llm['fpr_ci'])}" if llm else "")
    row("Precision", f(jev["precision"]), f(llm["precision"]) if llm else "")
    row("F1", f"{f(jev['f1'])} {ci(jev['f1_ci'])}", f"{f(llm['f1'])} {ci(llm['f1_ci'])}" if llm else "")
    row("AUROC", f"{jev['auroc']:.3f} [{jev['auroc_ci'][0]:.3f}, {jev['auroc_ci'][1]:.3f}]", f"{llm['auroc']:.3f} [{llm['auroc_ci'][0]:.3f}, {llm['auroc_ci'][1]:.3f}]" if llm else "")
    row("ECE (10 bins, lower is better)", f"{jev['ece']:.3f} [{jev['ece_ci'][0]:.3f}, {jev['ece_ci'][1]:.3f}]", f"{llm['ece']:.3f} [{llm['ece_ci'][0]:.3f}, {llm['ece_ci'][1]:.3f}]" if llm else "")
    row("Brier score (lower is better)", f"{jev['brier']:.3f}", f"{llm['brier']:.3f}" if llm else "")
    row("Latency p50 / p95 (from France)", f"{ms(jev['latency'].get('p50_s'))} / {ms(jev['latency'].get('p95_s'))}", f"{ms(llm['latency'].get('p50_s'))} / {ms(llm['latency'].get('p95_s'))}" if llm else "")
    nf = m.get("net_floor", {})
    row("Network floor, warm connection p50", ms(nf.get("typesafe_warm_p50_s")), ms(nf.get("llm_warm_p50_s")) if llm else "")
    row("Input / output tokens per email", f"{jev['tokens']['input']/max(1,jev['tokens']['calls']):.0f} / {jev['tokens']['output']/max(1,jev['tokens']['calls']):.0f}",
        f"{llm['tokens']['input']/max(1,llm['tokens']['calls']):.0f} / {llm['tokens']['output']/max(1,llm['tokens']['calls']):.0f}" if llm else "")
    row("List price in / out per M tokens", f"${JEV_PRICE_IN} / not published", f"${m['llm_cost']['price_in_per_m']} / ${m['llm_cost']['price_out_per_m']}" if llm else "")
    row("Cost per 1 000 emails (list price)", usd(m["jev_cost"]["per_1000_emails_usd"]), usd(m["llm_cost"]["per_1000_emails_usd"]) if llm else "")
    row("Format errors", "0 (typed output)", str(m["llm_errors"]["format_errors"]) if llm else "")
    if llm and m.get("ratios"):
        r = m["ratios"]
        L.append("")
        L.append(f"Ratios: {llm_name} is {r['latency_p50']:.1f}x slower at p50 and {r['cost']:.0f}x more expensive per email at list price. "
                 f"McNemar exact test on the {r['paired_n']} paired emails: p = {r['mcnemar_p']:.4f} "
                 f"(Jev alone correct on {r['jev_only_correct']}, {llm_name} alone correct on {r['llm_only_correct']}).")
    L.append("")
    L.append("Jev tokens include the nine questions sent with every email (verdict, mirror noul, five signals, two alternative wordings). "
             "The LLM prompt carries the same email plus the system prompt. Latency is wall-clock from the benchmark machine in France, "
             "sequential calls on a reused connection; the network floor row is the round trip of a tiny request on the same connection.")

    # auto decision
    L.append("")
    L.append("## Auto-decision curve")
    L.append("")
    L.append("Share of emails decided without a human when acting only above a probability threshold, and accuracy on those emails.")
    L.append("")
    hdr = "| Threshold | Jev coverage | Jev accuracy |" + (f" {llm_name} coverage | {llm_name} accuracy |" if llm else "")
    L.append(hdr)
    L.append("|---|---|---|" + ("---|---|" if llm else ""))
    for k, jd in enumerate(jev["auto_decision"]):
        line = f"| {jd['threshold']:.2f} | {f(jd['coverage'])} | {f(jd['accuracy'])} ({jd['errors']} errors) |"
        if llm:
            ld = llm["auto_decision"][k]
            line += f" {f(ld['coverage'])} | {f(ld['accuracy'])} ({ld['errors']} errors) |"
        L.append(line)

    # reliability
    L.append("")
    L.append("## Calibration bins (predicted class confidence vs accuracy)")
    L.append("")
    L.append("| Bin | Jev n | Jev confidence | Jev accuracy |" + (f" {llm_name} n | {llm_name} confidence | {llm_name} accuracy |" if llm else ""))
    L.append("|---|---|---|---|" + ("---|---|---|" if llm else ""))
    for k, b in enumerate(jev["ece_bins"]):
        line = f"| {b['lo']:.2f} to {b['hi']:.2f} | {b['n']} | {f(b.get('confidence'))} | {f(b.get('accuracy'))} |"
        if llm:
            lb = llm["ece_bins"][k]
            line += f" {lb['n']} | {f(lb.get('confidence'))} | {f(lb.get('accuracy'))} |"
        L.append(line)
    L.append("")
    L.append(f"Probability shape. Jev: mean p(phishing) {f(jev['prob_summary']['mean_p_on_phishing'])} on phishing, "
             f"{f(jev['prob_summary']['mean_p_on_legit'])} on legitimate, {f(jev['prob_summary']['frac_extreme'])} of answers below 0.05 or above 0.95, "
             f"{jev['prob_summary']['distinct_values']} distinct values.")
    if llm:
        L.append(f"{llm_name}: mean p(phishing) {f(llm['prob_summary']['mean_p_on_phishing'])} on phishing, "
                 f"{f(llm['prob_summary']['mean_p_on_legit'])} on legitimate, {f(llm['prob_summary']['frac_extreme'])} extreme, "
                 f"{llm['prob_summary']['distinct_values']} distinct values.")

    # stability
    L.append("")
    L.append("## Stability of probabilities across passes")
    L.append("")
    L.append("| Comparison | n | mean abs diff | p95 abs diff | max abs diff | diff > 0.05 | identical | label flips | Pearson r |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for name, s in m["stability"].items():
        if s.get("n", 0) < 2:
            L.append(f"| {name} | {s.get('n', 0)} | not run | | | | | | |")
        else:
            L.append(f"| {name} | {s['n']} | {s['mean_abs_diff']:.4f} | {s['p95_abs_diff']:.4f} | {s['max_abs_diff']:.4f} | {f(s['frac_diff_over_0_05'])} | {f(s['identical_frac'])} | {f(s['label_flip_rate'])} | {s['pearson_r']:.4f} |")

    # jev internals
    j = m["jev_internals"]
    L.append("")
    L.append("## Jev: primitives and wording sensitivity")
    L.append("")
    L.append("| Question | Accuracy | AUROC | ECE | Agreement with verdict |")
    L.append("|---|---|---|---|---|")
    for name, d in j["variants"].items():
        L.append(f"| {name} | {f(d['accuracy'])} | {d['auroc']:.3f} | {d['ece']:.3f} | {f(d['agreement'])} |")
    L.append("")
    L.append(f"Pearson r between the choice probability and the mirror noul: {j['choice_noul_pearson']:.4f}. "
             f"On a two-option choice, `confidence` is a deterministic function of the probability (r = {j['conf_vs_maxp_pearson']:.4f}), so the auto-decision curve on confidence is the same curve.")
    L.append("")
    L.append("## Jev signals (mean noul by class, AUROC of the signal alone)")
    L.append("")
    L.append("| Signal | Mean on phishing | Mean on legitimate | AUROC |")
    L.append("|---|---|---|---|")
    for s, d in j["signals"].items():
        L.append(f"| {s} | {d['mean_phishing']:.3f} | {d['mean_legit']:.3f} | {d['auroc']:.3f} |")

    c = m.get("jev_composite")
    if c:
        r1, r2 = c["rule_free_hosting"], c["cv_logistic"]
        L.append("")
        L.append("## Exploratory: combining Jev's signals in code")
        L.append("")
        L.append("Not part of the head-to-head comparison. It asks whether the atomic signals carry more than the verdict, "
                 "which is the composition pattern TypeSafe's docs recommend.")
        L.append("")
        L.append("| Rule | Accuracy | Recall | False positive rate | AUROC | ECE |")
        L.append("|---|---|---|---|---|---|")
        L.append(f"| Jev verdict alone | {f(jev['accuracy'])} | {f(jev['recall'])} | {f(jev['fpr'])} | {jev['auroc']:.3f} | {jev['ece']:.3f} |")
        L.append(f"| free-hosting signal >= 0.5, fixed rule | {f(r1['accuracy'])} {ci(r1['accuracy_ci'])} | {f(r1['recall'])} | {f(r1['fpr'])} | | |")
        L.append(f"| 5-fold CV logistic on 5 signals + verdict p | {f(r2['accuracy'])} {ci(r2['accuracy_ci'])} | {f(r2['recall'])} | {f(r2['fpr'])} | {r2['auroc']:.3f} | {r2['ece']:.3f} |")
        L.append("")
        L.append("Full-fit weights of the logistic model, for reading only: " + ", ".join(f"{k} {v:+.2f}" for k, v in r2["weights_full_fit"].items()) + ".")

    # categories
    L.append("")
    L.append("## Accuracy by URL category of the dataset")
    L.append("")
    L.append("| Category | Class | n | Jev accuracy |" + (f" {llm_name} accuracy |" if llm else ""))
    L.append("|---|---|---|---|" + ("---|" if llm else ""))
    for cat, d in sorted(m["by_category"]["jev"].items(), key=lambda kv: (-kv[1]["y"], kv[0])):
        line = f"| {cat} | {'phishing' if d['y'] == 1 else 'legitimate'} | {d['n']} | {f(d['accuracy'])} {ci(d['accuracy_ci'])} |"
        if llm:
            ld = m["by_category"]["llm"].get(cat)
            line += f" {f(ld['accuracy']) + ' ' + ci(ld['accuracy_ci']) if ld else 'n/a'} |"
        L.append(line)

    # reproduction
    ref = m.get("reference")
    if llm:
        L.append("")
        L.append("## Reproduction check against the published PhishNChips grid")
        L.append("")
        if ref:
            L.append(f"Published for {ref['model']} with the balanced prompt: recall {f(ref['recall'])}, false positive rate {f(ref['fpr'])}. "
                     f"Ours with the same system prompt and a JSON answer format: recall {f(llm['recall'])} {ci(llm['recall_ci'])}, "
                     f"false positive rate {f(llm['fpr'])} {ci(llm['fpr_ci'])}.")
        else:
            L.append(f"No row for model {llm_name} with the balanced strategy in reference_results.csv. Set LLM_GRID_MODEL in .env to the grid name if it differs.")
    L.append("")
    L.append("## Method notes")
    L.append("")
    L.append("- Same 2 000 emails for both systems, seeded fixed order, one call per email, no concurrency.")
    L.append("- Jev state is the email as a JSON object; the LLM receives the same JSON string inside the authors' balanced prompt.")
    L.append("- Jev verdict is the choice with the highest probability. The LLM verdict is its click decision; its probability is the verbalized phishing_probability.")
    L.append("- Confidence intervals: Wilson for proportions, percentile bootstrap (2 000 resamples) for AUROC, ECE, Brier and F1.")
    L.append("- Costs use list prices even when the run used a free tier. Jev has no published output price, so its output tokens are billed at zero.")
    out.write_text("\n".join(L) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------------- main


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--out-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--bootstrap", type=int, default=2000)
    args = parser.parse_args()
    rng = np.random.default_rng(SEED)

    emails = {e["id"]: e for e in load_emails()}
    jev1 = load_jev(args.raw_dir / "jev_pass1.jsonl")
    if not jev1:
        raise SystemExit("no successful Jev answers in jev_pass1.jsonl")
    jev2 = load_jev(args.raw_dir / "jev_pass2.jsonl")
    jev3 = load_jev(args.raw_dir / "jev_pass3.jsonl")
    llm_model = env("LLM_MODEL", "")
    llm1, llm_meta = load_llm(args.raw_dir / f"llm_{llm_model}_pass1.jsonl") if llm_model else ({}, {})
    llm2, _ = load_llm(args.raw_dir / f"llm_{llm_model}_pass2.jsonl") if llm_model else ({}, {})

    m: dict = {"generated_at": datetime.now(timezone.utc).isoformat(), "n_emails": len(emails), "seed": SEED}
    m["jev"] = evaluate(jev1, args.bootstrap, rng)
    m["jev_model"] = jev_model_name(args.raw_dir / "jev_pass1.jsonl")
    attempted, errs = count_errors(args.raw_dir / "jev_pass1.jsonl")
    m["jev_errors"] = {"attempted": attempted, "api_errors": errs}
    m["jev_cost"] = cost(m["jev"]["tokens"], JEV_PRICE_IN, JEV_PRICE_OUT)

    # Jev internals: primitives, wording variants, signals
    ids = sorted(jev1)
    y = np.array([jev1[i]["y"] for i in ids])
    p = np.array([jev1[i]["p"] for i in ids])
    pred = np.array([jev1[i]["pred"] for i in ids])
    conf = np.array([jev1[i]["conf"] for i in ids])
    variants = {}
    for name, pk, dk in (("verdict (choice)", "p", "pred"), ("is_phishing (noul)", "noul", None), ("verdict_alt_click", "alt_click_p", "alt_click"), ("verdict_alt_minimal", "alt_min_p", "alt_min")):
        vp = np.array([jev1[i][pk] for i in ids])
        vpred = np.array([jev1[i][dk] for i in ids]) if dk else (vp >= 0.5).astype(int)
        variants[name] = {
            "accuracy": float((vpred == y).mean()),
            "auroc": auroc(y, vp),
            "ece": ece(y, vp, vpred)[0],
            "agreement": float((vpred == pred).mean()),
        }
    signals = {}
    for s in SIGNALS:
        vals = np.array([jev1[i]["signals"].get(s, np.nan) for i in ids])
        ok = ~np.isnan(vals)
        signals[s] = {"mean_phishing": float(vals[ok & (y == 1)].mean()), "mean_legit": float(vals[ok & (y == 0)].mean()), "auroc": auroc(y[ok], vals[ok])}
    maxp = np.maximum(p, 1 - p)
    m["jev_internals"] = {
        "variants": variants,
        "signals": signals,
        "choice_noul_pearson": float(np.corrcoef(p, np.array([jev1[i]["noul"] for i in ids]))[0, 1]),
        "conf_vs_maxp_pearson": float(np.corrcoef(conf, maxp)[0, 1]) if conf.std() > 0 else float("nan"),
    }

    m["jev_composite"] = composite_signals(jev1, rng)

    m["stability"] = {
        "Jev pass 1 vs pass 2 (choice p)": stability(jev1, jev2),
        "Jev pass 1 vs pass 3 (choice p, next day)": stability(jev1, jev3),
        "Jev pass 1 vs pass 2 (noul)": stability(jev1, jev2, key="noul", pred_key="pred"),
    }
    m["by_category"] = {"jev": by_category(jev1, emails)}

    nf_path = args.out_dir / "net_floor.json"
    if nf_path.exists():
        nf = json.loads(nf_path.read_text())
        m["net_floor"] = {
            "typesafe_warm_p50_s": nf["hosts"]["typesafe"]["warm"]["p50_s"],
            "typesafe_cold_p50_s": nf["hosts"]["typesafe"]["cold"]["p50_s"],
            "llm_warm_p50_s": nf["hosts"]["llm"]["warm"]["p50_s"],
            "llm_cold_p50_s": nf["hosts"]["llm"]["cold"]["p50_s"],
            "measured_at": nf["measured_at"],
        }

    if llm1:
        m["llm_model"] = llm_meta["model"]
        m["llm"] = evaluate(llm1, args.bootstrap, rng)
        m["llm_errors"] = llm_meta
        price_in, price_out = env_float("LLM_PRICE_IN", 0.0), env_float("LLM_PRICE_OUT", 0.0)
        m["llm_cost"] = cost(m["llm"]["tokens"], price_in, price_out)
        m["stability"][f"{llm_meta['model']} pass 1 vs pass 2"] = stability(llm1, llm2)
        m["by_category"]["llm"] = by_category(llm1, emails)
        m["reference"] = reference_row(llm_meta["model"])
        paired = [i for i in jev1 if i in llm1 and llm1[i].get("pred") is not None]
        jc = np.array([jev1[i]["pred"] == jev1[i]["y"] for i in paired])
        lc = np.array([llm1[i]["pred"] == llm1[i]["y"] for i in paired])
        b, c = int((jc & ~lc).sum()), int((~jc & lc).sum())
        m["ratios"] = {
            "paired_n": len(paired),
            "jev_only_correct": b,
            "llm_only_correct": c,
            "mcnemar_p": mcnemar_exact(b, c),
            "latency_p50": m["llm"]["latency"]["p50_s"] / m["jev"]["latency"]["p50_s"],
            "latency_p95": m["llm"]["latency"]["p95_s"] / m["jev"]["latency"]["p95_s"],
            "cost": m["llm_cost"]["per_1000_emails_usd"] / m["jev_cost"]["per_1000_emails_usd"] if m["jev_cost"]["per_1000_emails_usd"] else float("nan"),
        }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "metrics.json").write_text(json.dumps(m, indent=2, default=float), encoding="utf-8")
    write_report(m, args.out_dir / "report.md")
    print(f"wrote {args.out_dir / 'metrics.json'} and {args.out_dir / 'report.md'}")
    j = m["jev"]
    print(f"Jev: acc {f(j['accuracy'])} recall {f(j['recall'])} fpr {f(j['fpr'])} auroc {j['auroc']:.3f} ece {j['ece']:.3f} p50 {ms(j['latency'].get('p50_s'))}")
    if m.get("llm"):
        l = m["llm"]
        print(f"{m['llm_model']}: acc {f(l['accuracy'])} recall {f(l['recall'])} fpr {f(l['fpr'])} auroc {l['auroc']:.3f} ece {l['ece']:.3f} p50 {ms(l['latency'].get('p50_s'))}")


if __name__ == "__main__":
    main()
