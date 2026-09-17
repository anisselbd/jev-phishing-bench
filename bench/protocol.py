"""Control 2: a selection / evaluation split shared by every signal source.

The 2 000 emails are cut into two stratified halves with a fixed seed. Everything that involves a choice (which
single signal to use, the threshold of the fixed rule, the weights of the logistic regression) is decided on half A
only. Every published number comes from half B. The same function runs on Jev's five signals, on the two heuristic
features and on Haiku's five signals, so the three sources get exactly the same treatment.
"""

from __future__ import annotations

import numpy as np

from bench.common import SEED, wilson

SPLIT_SEED = SEED + 1


def stratified_halves(ids: list[str], y: dict[str, int], seed: int = SPLIT_SEED) -> tuple[set[str], set[str]]:
    rng = np.random.default_rng(seed)
    a: set[str] = set()
    b: set[str] = set()
    for label in (0, 1):
        group = sorted(i for i in ids if y[i] == label)
        perm = rng.permutation(len(group))
        half = len(group) // 2
        a.update(group[k] for k in perm[:half])
        b.update(group[k] for k in perm[half:])
    return a, b


def best_threshold(y: np.ndarray, s: np.ndarray) -> float:
    """Threshold on a single score that maximises accuracy on the selection half. Ties go to the lowest threshold."""
    values = np.unique(s)
    if len(values) == 1:
        return 0.5
    candidates = [0.5] + [float((values[k] + values[k + 1]) / 2) for k in range(len(values) - 1)]
    best_t, best_acc = 0.5, -1.0
    for t in sorted(candidates):
        acc = float(((s >= t).astype(int) == y).mean())
        if acc > best_acc:
            best_t, best_acc = t, acc
    return best_t


def evaluate_signal_source(
    feats: dict[str, list[float]],
    names: list[str],
    y_all: dict[str, int],
    split_a: set[str],
    split_b: set[str],
    n_boot: int,
    rng: np.random.Generator,
    fns: dict,
) -> dict:
    """Select on A, evaluate on B. `feats` maps email id to a feature vector in the order of `names`.

    `fns` carries the metric functions of analyze.py (auroc, bootstrap_ci, brier, classification, ece, logistic_fit).
    """
    auroc, bootstrap_ci, brier = fns["auroc"], fns["bootstrap_ci"], fns["brier"]
    classification, ece, logistic_fit = fns["classification"], fns["ece"], fns["logistic_fit"]

    ids_a = sorted(i for i in feats if i in split_a)
    ids_b = sorted(i for i in feats if i in split_b)
    XA = np.array([feats[i] for i in ids_a])
    XB = np.array([feats[i] for i in ids_b])
    yA = np.array([y_all[i] for i in ids_a])
    yB = np.array([y_all[i] for i in ids_b])
    out = {"n_a": len(ids_a), "n_b": len(ids_b), "features": names}

    # single feature: chosen on A by AUROC, threshold chosen on A by accuracy
    auc_a = {name: auroc(yA, XA[:, k]) for k, name in enumerate(names)}
    best = max(auc_a, key=auc_a.get)
    k = names.index(best)
    t = best_threshold(yA, XA[:, k])
    predB = (XB[:, k] >= t).astype(int)
    single = classification(yB, predB)
    single.update({"feature": best, "threshold": t, "auroc_a_all_features": auc_a, "auroc_b": auroc(yB, XB[:, k])})
    single["auroc_b_ci"] = bootstrap_ci(lambda yy, pp, pr: auroc(yy, pp), yB, XB[:, k], predB, n_boot, rng)
    single["accuracy_a"] = float(((XA[:, k] >= t).astype(int) == yA).mean())
    out["single_rule"] = single

    # logistic regression on all features, trained on A, scored on B
    w = logistic_fit(np.column_stack([np.ones(len(ids_a)), XA]), yA)
    pB = 1 / (1 + np.exp(-(np.column_stack([np.ones(len(ids_b)), XB]) @ w)))
    predB = (pB >= 0.5).astype(int)
    logit = classification(yB, predB)
    logit["auroc"] = auroc(yB, pB)
    logit["auroc_ci"] = bootstrap_ci(lambda yy, pp, pr: auroc(yy, pp), yB, pB, predB, n_boot, rng)
    logit["ece"] = ece(yB, pB, predB)[0]
    logit["brier"] = brier(yB, pB)
    logit["weights"] = {n: float(v) for n, v in zip(["bias"] + names, w)}
    pA = 1 / (1 + np.exp(-(np.column_stack([np.ones(len(ids_a)), XA]) @ w)))
    logit["accuracy_a"] = float(((pA >= 0.5).astype(int) == yA).mean())
    out["logistic"] = logit

    # paired correctness on B, for McNemar tests between sources
    out["correct_b"] = {i: bool(c) for i, c in zip(ids_b, predB == yB)}
    out["single_correct_b"] = {i: bool(c) for i, c in zip(ids_b, (XB[:, k] >= t).astype(int) == yB)}
    return out
