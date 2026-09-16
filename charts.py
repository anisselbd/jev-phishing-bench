"""Draw results/chart.png (4 panels) and results/signals.png from results/metrics.json, dark theme for X.

Usage: uv run charts.py [--out-dir results]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from bench.common import RESULTS_DIR, read_jsonl, RAW_DIR  # noqa: E402

# Palette: two fixed categorical hues validated for the dark surface (dataviz reference palette, dark column).
SURFACE = "#1a1a19"
TEXT = "#ffffff"
TEXT_2 = "#c3c2b7"
GRID = "#383835"
JEV = "#3987e5"
LLM = "#d95926"


def style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": GRID,
            "axes.labelcolor": TEXT_2,
            "xtick.color": TEXT_2,
            "ytick.color": TEXT_2,
            "text.color": TEXT,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "axes.grid": True,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "legend.frameon": False,
            "font.family": "DejaVu Sans",
        }
    )


def panel_reliability(ax, m: dict, llm_name: str) -> None:
    ax.plot([0, 1], [0, 1], color=TEXT_2, lw=1, ls="--", label="perfect calibration")
    for key, color, name in (("jev", JEV, "Jev"), ("llm", LLM, llm_name)):
        if key not in m:
            continue
        bins = [b for b in m[key]["reliability"] if b["n"] > 0]
        x = [b["predicted"] for b in bins]
        y = [b["observed"] for b in bins]
        sizes = [max(8, min(80, b["n"] / 8)) for b in bins]
        ax.plot(x, y, color=color, lw=2, label=f"{name} (ECE {m[key]['ece']:.3f})")
        ax.scatter(x, y, s=sizes, color=color, edgecolor=SURFACE, linewidth=1.5, zorder=3)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("predicted probability of phishing")
    ax.set_ylabel("observed share of phishing")
    ax.set_title("Calibration")
    ax.legend(loc="upper left")


def panel_auto_decision(ax, m: dict, llm_name: str) -> None:
    for key, color, name in (("jev", JEV, "Jev"), ("llm", LLM, llm_name)):
        if key not in m:
            continue
        pts = [d for d in m[key]["auto_decision"] if d["n"] > 0]
        cov = [100 * d["coverage"] for d in pts]
        acc = [100 * d["accuracy"] for d in pts]
        ax.plot(cov, acc, color=color, lw=2, label=name)
        ax.scatter(cov, acc, s=18, color=color, edgecolor=SURFACE, linewidth=1, zorder=3)
        dy = 7 if key == "jev" else -11
        for d in pts:
            if d["threshold"] in (0.5, 0.9):
                ax.annotate(f"p ≥ {d['threshold']:.2f}", (100 * d["coverage"], 100 * d["accuracy"]), textcoords="offset points",
                            xytext=(-4, dy), fontsize=8, color=TEXT_2, ha="right")
    ax.set_xlabel("emails decided without a human (%)")
    ax.set_ylabel("accuracy on those emails (%)")
    ax.set_title("Auto-decision: coverage vs accuracy")
    ax.set_xlim(0, 104)
    lo = min(50, ax.get_ylim()[0])
    ax.set_ylim(lo, 101)
    ax.legend(loc="lower left")


def panel_latency(ax, m: dict, llm_name: str, raw_dir: Path) -> None:
    data, labels, colors = [], [], []
    for key, color, name, fname in (("jev", JEV, "Jev", "jev_pass1.jsonl"), ("llm", LLM, llm_name, f"llm_{m.get('llm_model')}_pass1.jsonl")):
        if key not in m:
            continue
        lat = [r["latency_s"] * 1000 for r in read_jsonl(raw_dir / fname) if r.get("ok")]
        if lat:
            data.append(lat)
            labels.append(name)
            colors.append(color)
    parts = ax.violinplot(data, showmedians=False, showextrema=False, widths=0.8)
    for body, color in zip(parts["bodies"], colors):
        body.set_facecolor(color)
        body.set_edgecolor(color)
        body.set_alpha(0.55)
    for i, (lat, color) in enumerate(zip(data, colors), 1):
        p50, p95 = np.median(lat), np.percentile(lat, 95)
        ax.hlines(p50, i - 0.3, i + 0.3, color=TEXT, lw=2)
        ax.annotate(f"p50 {p50:.0f} ms\np95 {p95:.0f} ms", (i + 0.42, p50), fontsize=9, color=TEXT, va="center")
    nf = m.get("net_floor", {})
    for i, (key, lab) in enumerate((("typesafe_warm_p50_s", "network floor"), ("llm_warm_p50_s", "network floor")), 1):
        if key in nf and i <= len(data):
            ax.hlines(nf[key] * 1000, i - 0.4, i + 0.4, color=TEXT_2, lw=1, ls=":")
            ax.annotate(lab, (i - 0.4, nf[key] * 1000), fontsize=8, color=TEXT_2, va="bottom")
    ax.set_yscale("log")
    ax.set_xticks(range(1, len(labels) + 1), labels)
    ax.set_ylabel("latency per email (ms, log scale)")
    ax.set_title("Latency, sequential calls from France")
    ax.grid(True, axis="y", which="both")
    ax.grid(False, axis="x")


def panel_cost(ax, m: dict, llm_name: str) -> None:
    names, vals, colors = ["Jev"], [m["jev_cost"]["per_1000_emails_usd"]], [JEV]
    if "llm" in m:
        names.append(llm_name)
        vals.append(m["llm_cost"]["per_1000_emails_usd"])
        colors.append(LLM)
    bars = ax.bar(names, vals, color=colors, width=0.55)
    for bar, v in zip(bars, vals):
        ax.annotate(f"${v:.4f}" if v < 0.01 else f"${v:.3f}", (bar.get_x() + bar.get_width() / 2, v), ha="center", va="bottom",
                    xytext=(0, 4), textcoords="offset points", fontsize=10, color=TEXT)
    ax.set_yscale("log")
    ax.set_ylabel("USD per 1 000 emails (log scale)")
    ax.set_title("Cost at list price")
    ax.grid(True, axis="y", which="both")
    ax.grid(False, axis="x")
    if len(vals) == 2 and vals[0] > 0:
        ax.text(0.5, 0.95, f"{vals[1] / vals[0]:.0f}x", transform=ax.transAxes, ha="center", va="top", fontsize=16, fontweight="bold", color=TEXT)


def draw_chart(m: dict, out_dir: Path, raw_dir: Path) -> None:
    llm_name = m.get("llm_model") or "LLM"
    fig, axes = plt.subplots(2, 2, figsize=(13, 10))
    for row in axes:
        for ax in row:
            ax.set_axisbelow(True)
    panel_reliability(axes[0][0], m, llm_name)
    panel_auto_decision(axes[0][1], m, llm_name)
    panel_latency(axes[1][0], m, llm_name, raw_dir)
    panel_cost(axes[1][1], m, llm_name)
    n = m["jev"]["n"]
    jev, llm = m["jev"], m.get("llm")
    sub = f"Jev accuracy {100*jev['accuracy']:.1f}%, AUROC {jev['auroc']:.3f}"
    if llm:
        sub += f"  |  {llm_name} accuracy {100*llm['accuracy']:.1f}%, AUROC {llm['auroc']:.3f}"
    fig.suptitle(f"Jev vs {llm_name} on PhishNChips v5.2 ({n} emails, 1 000 phishing / 1 000 legitimate)", fontsize=15, fontweight="bold", y=0.985)
    fig.text(0.5, 0.945, sub, ha="center", color=TEXT_2, fontsize=11)
    fig.text(0.5, 0.01, "same emails, same task framing, one call per email, list prices  |  @Lbdev__", ha="center", color=TEXT_2, fontsize=9)
    fig.tight_layout(rect=(0, 0.02, 1, 0.93))
    fig.savefig(out_dir / "chart.png", dpi=170)
    plt.close(fig)


def draw_signals(m: dict, out_dir: Path) -> None:
    sig = m["jev_internals"]["signals"]
    names = list(sig)
    labels = [s.replace("sig_", "").replace("_", " ") for s in names]
    ph = [sig[s]["mean_phishing"] for s in names]
    lg = [sig[s]["mean_legit"] for s in names]
    x = np.arange(len(names))
    w = 0.38
    fig, ax = plt.subplots(figsize=(11, 5.8))
    ax.set_axisbelow(True)
    b1 = ax.bar(x - w / 2, ph, w, color=LLM, label="phishing emails")
    b2 = ax.bar(x + w / 2, lg, w, color=JEV, label="legitimate emails")
    for bars in (b1, b2):
        for bar in bars:
            ax.annotate(f"{bar.get_height():.2f}", (bar.get_x() + bar.get_width() / 2, bar.get_height()), ha="center", va="bottom",
                        xytext=(0, 3), textcoords="offset points", fontsize=9, color=TEXT)
    for i, s in enumerate(names):
        ax.text(i, 1.02, f"AUROC {sig[s]['auroc']:.2f}", ha="center", fontsize=9, color=TEXT_2)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("mean noul probability")
    ax.set_title("Jev signal questions, asked in the same call as the verdict")
    ax.grid(True, axis="y")
    ax.grid(False, axis="x")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2)
    fig.tight_layout()
    fig.savefig(out_dir / "signals.png", dpi=170)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    args = parser.parse_args()
    m = json.loads((args.out_dir / "metrics.json").read_text())
    style()
    draw_chart(m, args.out_dir, args.raw_dir)
    draw_signals(m, args.out_dir)
    print(f"wrote {args.out_dir / 'chart.png'} and {args.out_dir / 'signals.png'}")


if __name__ == "__main__":
    main()
