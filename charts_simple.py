"""Three plain-language charts for a general audience, one message per image, from results/metrics.json.

results/simple_precision.png : who is right more often
results/simple_speed_cost.png : who is faster and cheaper
results/simple_signals.png    : the five-questions trick, against a regex and against Haiku asked the same questions

Usage: uv run charts_simple.py
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bench.common import RESULTS_DIR  # noqa: E402
from charts import JEV, LLM, SURFACE, TEXT, TEXT_2, style  # noqa: E402

GREY = "#c3c2b7"


def fr(v: float, digits: int = 1, unit: str = "") -> str:
    return f"{v:.{digits}f}".replace(".", ",") + unit


def big_bars(ax, labels, values, colors, fmt, title, ylim=None, note=None, note_y=-0.16):
    ax.set_axisbelow(True)
    bars = ax.bar(labels, values, color=colors, width=0.55)
    for bar, v in zip(bars, values):
        ax.annotate(fmt(v), (bar.get_x() + bar.get_width() / 2, bar.get_height()), ha="center", va="bottom",
                    xytext=(0, 8), textcoords="offset points", fontsize=22, fontweight="bold", color=TEXT)
    ax.set_title(title, fontsize=17, fontweight="bold", pad=18)
    ax.tick_params(axis="x", labelsize=13)
    ax.set_yticks([])
    ax.grid(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    if ylim:
        ax.set_ylim(*ylim)
    if note:
        ax.text(0.5, note_y, note, transform=ax.transAxes, ha="center", fontsize=11, color=TEXT_2)


def main() -> None:
    m = json.loads((RESULTS_DIR / "metrics.json").read_text())
    style()
    jev, llm = m["jev"], m["llm"]

    # 1. precision
    fig, ax = plt.subplots(figsize=(9, 6))
    big_bars(ax, ["Jev (TypeSafe)", "Claude Haiku 4.5"], [100 * jev["accuracy"], 100 * llm["accuracy"]], [JEV, LLM],
             lambda v: fr(v, 1, " %"), "Sur 2 000 emails, qui détecte correctement le phishing ?", ylim=(0, 100),
             note="bonne réponse sur 100 emails, phishing et légitimes confondus, même consigne pour les deux")
    fig.text(0.5, 0.02, "Jev se trompe une fois sur trois, Haiku une fois sur cinq.  |  @Lbdev__", ha="center", color=TEXT, fontsize=12)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(RESULTS_DIR / "simple_precision.png", dpi=170)
    plt.close(fig)

    # 2. speed and cost
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    big_bars(axes[0], ["Jev", "Claude Haiku 4.5"], [1000 * jev["latency"]["p50_s"], 1000 * llm["latency"]["p50_s"]], [JEV, LLM],
             lambda v: fr(v, 0, " ms"), "Temps de réponse par email", ylim=(0, 1000 * llm["latency"]["p50_s"] * 1.25),
             note="médiane, mesurée depuis la France")
    big_bars(axes[1], ["Jev", "Claude Haiku 4.5"], [m["jev_cost"]["per_1000_emails_usd"], m["llm_cost"]["per_1000_emails_usd"]], [JEV, LLM],
             lambda v: fr(v, 2, " $"), "Prix pour 1 000 emails", ylim=(0, m["llm_cost"]["per_1000_emails_usd"] * 1.25),
             note="prix catalogue des deux API")
    ratio_t = llm["latency"]["p50_s"] / jev["latency"]["p50_s"]
    ratio_c = m["llm_cost"]["per_1000_emails_usd"] / m["jev_cost"]["per_1000_emails_usd"]
    fig.suptitle(f"Jev est {ratio_t:.0f} fois plus rapide et {ratio_c:.0f} fois moins cher", fontsize=19, fontweight="bold", y=0.99)
    fig.text(0.5, 0.02, "Là, le pitch de TypeSafe ne ment pas.  |  @Lbdev__", ha="center", color=TEXT, fontsize=12)
    fig.tight_layout(rect=(0, 0.08, 1, 0.93))
    fig.savefig(RESULTS_DIR / "simple_speed_cost.png", dpi=170)
    plt.close(fig)

    # 3. the five questions trick
    c = m["controls"]
    vals = [100 * c["heuristic_split"]["logistic"]["accuracy"], 100 * c["jev_signals_split"]["logistic"]["accuracy"], 100 * c["llm_signals_split"]["logistic"]["accuracy"]]
    labels = ["Une simple liste\nd'hébergeurs (sans IA)", "Jev, 5 questions\nsimples combinées", "Haiku, les 5 mêmes\nquestions combinées"]
    fig, ax = plt.subplots(figsize=(11, 6.5))
    big_bars(ax, labels, vals, [GREY, JEV, LLM], lambda v: fr(v, 1, " %"),
             "5 petites questions plutôt qu'une grande : ça marche, pas que pour Jev", ylim=(0, 108),
             note="bonne réponse sur 1 000 emails jamais vus pendant le réglage ; Jev et Haiku : écart non significatif", note_y=-0.24)
    fig.text(0.5, 0.02, f"Jev à {fr(100*jev['accuracy'])} % en une question, {fr(vals[1])} % en cinq. Haiku fait pareil pour 27 fois plus cher.  |  @Lbdev__",
             ha="center", color=TEXT, fontsize=12)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(RESULTS_DIR / "simple_signals.png", dpi=170)
    plt.close(fig)
    print("wrote simple_precision.png, simple_speed_cost.png, simple_signals.png")


if __name__ == "__main__":
    main()
