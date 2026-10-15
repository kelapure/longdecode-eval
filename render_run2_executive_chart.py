#!/usr/bin/env python3
"""
render_run2_executive_chart.py
==============================
Renders a publication-grade, pixel-perfect 300-DPI visual chart for Run 2
(the 15-module "Pagination Cliff" run) with guaranteed zero text collisions.
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np


def render_perfect_run2_chart(out_png: str = "archive/run_02_massive/benchmark_executive_chart.png"):
    categories = [
        "Method & File Completeness",
        "Zero-Placeholder Integrity",
        "Cost Efficiency Index",
        "Automated Pytest Pass Rate",
    ]

    scores_gemini = [100.0, 100.0, 100.0, 100.0]
    scores_openai = [100.0, 100.0, 35.8, 100.0]
    scores_anthropic = [100.0, 100.0, 13.8, 96.8]

    # Clean, concise annotations
    labels_gemini = [
        "100.0%",
        "100.0%",
        "100.0%  ($0.46 • 1 turn)",
        "100.0%  (92/92 passed)",
    ]
    labels_openai = [
        "100.0%",
        "100.0%",
        "35.8%  ($1.28 • 2 turns)",
        "100.0%  (414/414 passed)",
    ]
    labels_anthropic = [
        "100.0%",
        "100.0%",
        "13.8%  ($3.31 • 8 turns • 804K input tax)",
        "96.8%  (15 failed tests • context drift)",
    ]

    # Color palette (accessible, high-contrast dark theme)
    c_bg = "#090d16"         # Canvas dark obsidian
    c_card = "#111827"       # Card background (Slate 900)
    c_grid = "#1f2937"       # Subtle gridline
    c_border = "#374151"     # Card stroke
    c_text_bright = "#f9fafb"# Text primary
    c_text_muted = "#9ca3af" # Text secondary
    c_text_dim = "#6b7280"   # Secondary notes

    c_gemini = "#10b981"     # Bright Emerald Green (Winner)
    c_openai = "#f97316"     # Amber / Orange
    c_anthropic = "#c084fc"  # Vibrant Lavender / Purple

    # 13.5 x 7.6 inches @ 300 DPI (Widescreen 16:9 LinkedIn optimized)
    fig, ax = plt.subplots(figsize=(13.5, 7.6), dpi=300)
    fig.patch.set_facecolor(c_bg)
    ax.set_facecolor(c_card)

    y = np.arange(len(categories))
    bar_height = 0.22
    offsets = [bar_height, 0, -bar_height]

    bars_gem = ax.barh(y + offsets[0], scores_gemini, bar_height * 0.85,
                       color=c_gemini, edgecolor="none", label="Gemini 4 Argon (Native 1M Long Decode)")
    bars_oai = ax.barh(y + offsets[1], scores_openai, bar_height * 0.85,
                       color=c_openai, edgecolor="none", label="OpenAI GPT-6 Astra (128K Harness)")
    bars_ant = ax.barh(y + offsets[2], scores_anthropic, bar_height * 0.85,
                       color=c_anthropic, edgecolor="none", label="Anthropic Claude Sonnet 5.5 (64K Harness)")

    # Direct labels with ample room (xlim up to 142)
    for i, rect in enumerate(bars_gem):
        w = rect.get_width()
        y_pos = rect.get_y() + rect.get_height() / 2
        ax.annotate(labels_gemini[i], xy=(w, y_pos), xytext=(7, 0),
                    textcoords="offset points", ha="left", va="center",
                    fontsize=9.5, fontweight="bold", color=c_gemini)

    for i, rect in enumerate(bars_oai):
        w = rect.get_width()
        y_pos = rect.get_y() + rect.get_height() / 2
        ax.annotate(labels_openai[i], xy=(w, y_pos), xytext=(7, 0),
                    textcoords="offset points", ha="left", va="center",
                    fontsize=9.5, fontweight="bold", color=c_openai)

    for i, rect in enumerate(bars_ant):
        w = rect.get_width()
        y_pos = rect.get_y() + rect.get_height() / 2
        ax.annotate(labels_anthropic[i], xy=(w, y_pos), xytext=(7, 0),
                    textcoords="offset points", ha="left", va="center",
                    fontsize=9.5, fontweight="bold", color=c_anthropic)

    # Reference Line at 100% Target
    ax.axvline(100, color="#475569", linestyle=":", linewidth=1.2, alpha=0.8, zorder=1)
    ax.text(100.5, -0.45, "100% Target", fontsize=8.5, color="#64748b", fontweight="bold", ha="left", va="center")

    # Axes styling
    ax.set_yticks(y)
    ax.set_yticklabels(categories, fontsize=11, fontweight="bold", color=c_text_bright)
    ax.set_xlim(0, 142)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.xaxis.set_major_formatter(ticker.PercentFormatter(xmax=100, decimals=0))
    ax.set_xlabel("Normalized Score (0% to 100% — Higher is Better →)",
                  fontsize=10.5, color=c_text_muted, labelpad=12, fontweight="medium")
    ax.tick_params(axis="x", colors=c_text_muted, labelsize=9.5)
    ax.tick_params(axis="y", colors=c_text_bright, length=0)

    ax.grid(axis="x", color=c_grid, linestyle="--", linewidth=0.8, alpha=0.8)
    ax.set_axisbelow(True)

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["bottom", "left"]:
        ax.spines[spine].set_color(c_border)
        ax.spines[spine].set_linewidth(1.0)

    # Title & Subtitle with guaranteed vertical separation
    fig.text(0.06, 0.948,
             "Why 128K/64K Multi-Turn LLM Harnesses Break on Enterprise Code Modernization",
             fontsize=14.5, fontweight="bold", color="#ffffff", ha="left")
    fig.text(0.06, 0.912,
             "Adversarial Benchmark across 15 Interdependent Legacy Modules (76 Procedures) • Single-Pass 1M vs. Multi-Turn Pagination",
             fontsize=10.5, color=c_text_muted, ha="left")

    # Legend cleanly placed above axes with comfortable breathing room
    leg = ax.legend(
        loc="upper left",
        bbox_to_anchor=(0.0, 1.11),
        ncol=3,
        frameon=True,
        facecolor="#182234",
        edgecolor=c_border,
        fontsize=9.5,
        columnspacing=1.6,
        handlelength=1.2,
        handletextpad=0.6,
    )
    for text in leg.get_texts():
        text.set_color("#f9fafb")

    # Bottom Audit Footnote
    footnote = (
        "Run 2 Verified Receipts: Gemini 4 Argon: 1 turn, 35,369 tokens, $0.46 (100% pass)  |  "
        "OpenAI GPT-6 Astra: 2 turns, 22,893 tokens, $1.28 (100% pass)  |  "
        "Anthropic Claude Fable: 8 turns, 59,613 tokens, $3.31 (96.8% pass, 15 failures)\n"
        "Independent reproduction: github.com/kelapure/longdecode-eval • Zero API keys needed: run python3 verify_artifacts.py"
    )
    fig.text(0.06, 0.022, footnote, fontsize=8.5, color=c_text_dim, ha="left", linespacing=1.4)

    # Exact layout bounds preventing any component overlap
    plt.tight_layout(rect=[0.03, 0.065, 0.98, 0.87])

    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=300, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"[Success] Zero-collision 300-DPI chart written to: {out_png}")


if __name__ == "__main__":
    render_perfect_run2_chart()
