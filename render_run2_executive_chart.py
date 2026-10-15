#!/usr/bin/env python3
"""
render_run2_executive_chart.py
==============================
Renders a publication-grade, pixel-perfect 300-DPI visual chart for Run 2
(the 15-module "Pagination Cliff" run) optimized for LinkedIn and executive decks.
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patches as patches
import numpy as np


def render_perfect_run2_chart(out_png: str = "archive/run_02_massive/benchmark_executive_chart.png"):
    # 1. Exact Run 2 Data
    # Dimensions ordered logically: Functional Correctness -> Cost -> Integrity -> Completeness
    categories = [
        "Method & File Completeness",
        "Zero-Placeholder Integrity (No TODOs)",
        "Cost Efficiency Index (Cheapest = 100%)",
        "Automated Unit Test Pass Rate (Pytest)",
    ]

    # Data per model for each category:
    # [Completeness, Zero-Stub, Cost Efficiency, Pytest Pass Rate]
    scores_gemini = [100.0, 100.0, 100.0, 100.0]
    scores_openai = [100.0, 100.0, 35.8, 100.0]
    scores_anthropic = [100.0, 100.0, 13.8, 96.8]

    # Details for callout annotations
    notes_gemini = ["32/32 files", "0 stubs", "$0.46 (1 turn)", "92/92 passed (100%)"]
    notes_openai = ["37/32 files", "0 stubs", "$1.28 (2 turns)", "414/414 passed (100%)"]
    notes_anthropic = ["32/32 files", "0 stubs", "$3.31 (8 turns)", "454/469 passed (15 failed)"]

    # Colors
    c_bg = "#090d16"         # Canvas dark obsidian
    c_card = "#111827"       # Card background (Tailwind Gray 900)
    c_grid = "#1f2937"       # Subtle gridline
    c_border = "#374151"     # Card stroke
    c_text_bright = "#f9fafb"# Headings
    c_text_muted = "#9ca3af" # Subtitles
    c_text_dim = "#6b7280"   # Secondary notes

    # Distinct Brand Colors:
    c_gemini = "#10b981"     # Bright Emerald Green (Winner)
    c_openai = "#f97316"     # Amber / Orange
    c_anthropic = "#c084fc"  # Vibrant Lavender / Purple (readable on dark)

    # 2. Setup Figure (16:9 widescreen layout at 300 DPI)
    fig, ax = plt.subplots(figsize=(13.2, 7.4), dpi=300)
    fig.patch.set_facecolor(c_bg)
    ax.set_facecolor(c_card)

    y = np.arange(len(categories))
    bar_height = 0.22
    offsets = [bar_height, 0, -bar_height]  # Top to bottom within each group: Gemini, OpenAI, Anthropic

    # Plot bars
    bars_gem = ax.barh(y + offsets[0], scores_gemini, bar_height * 0.88,
                       color=c_gemini, edgecolor="none", label="Gemini 4 Argon (Native 1M Long Decode)")
    bars_oai = ax.barh(y + offsets[1], scores_openai, bar_height * 0.88,
                       color=c_openai, edgecolor="none", label="OpenAI GPT-6 Astra (128K Harness)")
    bars_ant = ax.barh(y + offsets[2], scores_anthropic, bar_height * 0.88,
                       color=c_anthropic, edgecolor="none", label="Anthropic Claude Sonnet 5.5 (64K Harness)")

    # 3. Direct Bar Value Labels with Contextual Annotations
    for i, rect in enumerate(bars_gem):
        w = rect.get_width()
        y_pos = rect.get_y() + rect.get_height() / 2
        ax.annotate(
            f"{w:.1f}%",
            xy=(w, y_pos),
            xytext=(7, 0),
            textcoords="offset points",
            ha="left", va="center",
            fontsize=9.5, fontweight="bold", color=c_gemini
        )

    for i, rect in enumerate(bars_oai):
        w = rect.get_width()
        y_pos = rect.get_y() + rect.get_height() / 2
        extra = "  ($1.28)" if i == 2 else ""
        ax.annotate(
            f"{w:.1f}%{extra}",
            xy=(w, y_pos),
            xytext=(7, 0),
            textcoords="offset points",
            ha="left", va="center",
            fontsize=9.5, fontweight="bold", color=c_openai
        )

    for i, rect in enumerate(bars_ant):
        w = rect.get_width()
        y_pos = rect.get_y() + rect.get_height() / 2
        extra = ""
        if i == 3:
            extra = "  ◄ 15 failed tests (context drift)"
        elif i == 2:
            extra = "  ◄ $3.31 (804K uncached tokens re-fed across 8 turns)"
        ax.annotate(
            f"{w:.1f}%{extra}",
            xy=(w, y_pos),
            xytext=(7, 0),
            textcoords="offset points",
            ha="left", va="center",
            fontsize=9.5, fontweight="bold", color=c_anthropic
        )

    # 4. Styling Axes
    ax.set_yticks(y)
    ax.set_yticklabels(categories, fontsize=11, fontweight="bold", color=c_text_bright)
    ax.set_xlim(0, 116)
    ax.set_xlabel("Normalized Performance Score (0% to 100% — Higher is Better →)",
                  fontsize=10.5, color=c_text_muted, labelpad=12, fontweight="medium")
    ax.xaxis.set_major_formatter(ticker.PercentFormatter(xmax=100, decimals=0))
    ax.tick_params(axis="x", colors=c_text_muted, labelsize=9.5)
    ax.tick_params(axis="y", colors=c_text_bright, length=0)

    # Gridlines
    ax.grid(axis="x", color=c_grid, linestyle="--", linewidth=0.8, alpha=0.9)
    ax.set_axisbelow(True)

    # Border styling: soft rounded appearance
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["bottom", "left"]:
        ax.spines[spine].set_color(c_border)
        ax.spines[spine].set_linewidth(1.0)

    # 5. Header / Titles (Hierarchy & Breathing Room)
    fig.text(0.08, 0.945,
             "Why 128K/64K Multi-Turn LLM Harnesses Break on Enterprise Code Modernization",
             fontsize=14.5, fontweight="bold", color="#ffffff", ha="left")
    fig.text(0.08, 0.915,
             "Adversarial Benchmark across 15 Interdependent Legacy Modules (76 Procedures) • Single-Pass 1M vs. Multi-Turn Pagination",
             fontsize=10.5, color=c_text_muted, ha="left")

    # 6. High-Contrast Legend Positioned Cleanly Under the Subtitle
    leg = ax.legend(
        loc="upper left",
        bbox_to_anchor=(0.0, 1.13),
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
        text.set_fontweight("medium")

    # 7. Bottom Footnote / Audit Metadata
    footnote = (
        "Run 2 Artifact Receipts: Gemini 4 Argon: 1 turn, 35,369 tokens, $0.46 (100% pass)  |  "
        "OpenAI GPT-6 Astra: 2 turns, 22,893 tokens, $1.28 (100% pass)  |  "
        "Anthropic Claude Fable: 8 turns, 59,613 tokens, $3.31 (96.8% pass, 15 failures)\n"
        "Independent forensic reproduction available: github.com/kelapure/longdecode-eval • Run python3 verify_artifacts.py"
    )
    fig.text(0.08, 0.02, footnote, fontsize=8.5, color=c_text_dim, ha="left", linespacing=1.4)

    # 8. Save High-DPI Output
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout(rect=[0.06, 0.06, 0.98, 0.89])
    fig.savefig(out_png, dpi=300, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"[Success] Pixel-perfect 300-DPI chart written to: {out_png}")


if __name__ == "__main__":
    render_perfect_run2_chart()
