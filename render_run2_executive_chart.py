#!/usr/bin/env python3
"""
render_run2_executive_chart.py
==============================
Renders a publication-grade, pixel-perfect 300-DPI visual chart for Run 2
(the 15-module "Pagination Cliff" run) with mathematically exact alignments,
balanced whitespace, and professional executive styling.
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np


def render_perfect_run2_chart(out_png: str = "archive/run_02_massive/benchmark_executive_chart.png"):
    # 1. Top-to-Bottom Ordered Dimensions (Failure Modes First!)
    categories = [
        "Automated Pytest Pass Rate",
        "Cost Efficiency Index",
        "Zero-Placeholder Integrity",
        "Method & File Completeness",
    ]

    # Data corresponding to the top-to-bottom order:
    # [Pytest Pass Rate, Cost Efficiency, Zero-Stub, Completeness]
    scores_gemini = [100.0, 100.0, 100.0, 100.0]
    scores_openai = [100.0, 35.8, 100.0, 100.0]
    scores_anthropic = [96.8, 13.8, 100.0, 100.0]

    # Precise, clean annotations for each row
    labels_gemini = [
        "100.0%  (92/92 passed)",
        "100.0%  ($0.46 • 1 turn)",
        "100.0%  (0 stubs)",
        "100.0%  (32/32 files)",
    ]
    labels_openai = [
        "100.0%  (414/414 passed)",
        "35.8%  ($1.28 • 2 turns)",
        "100.0%  (0 stubs)",
        "100.0%  (37/32 files)",
    ]
    labels_anthropic = [
        "96.8%  (15 failed tests • context drift)",
        "13.8%  ($3.31 • 8 turns • 804K input tax)",
        "100.0%  (0 stubs)",
        "100.0%  (32/32 files)",
    ]

    # Executive Dark Theme Palette (Linear / Stripe inspired)
    c_bg = "#0b0f19"         # Deep Slate Canvas
    c_card = "#0b0f19"       # Seamless matching plot area
    c_grid = "#1e293b"       # Subtle horizontal/vertical grid
    c_spine = "#334155"      # Crisp axis spine
    c_text_bright = "#f8fafc"# Primary text
    c_text_muted = "#94a3b8" # Secondary text
    c_text_dim = "#64748b"   # Muted footnotes & targets

    # High-Contrast Brand Palette
    c_gemini = "#10b981"     # Bright Emerald Green (Winner)
    c_openai = "#f97316"     # Amber / Orange
    c_anthropic = "#c084fc"  # Vibrant Lavender / Purple

    # 2. Strict Grid Sizing: 13.6 x 7.2 inches @ 300 DPI (Widescreen 16:9)
    fig = plt.figure(figsize=(13.6, 7.2), dpi=300)
    fig.patch.set_facecolor(c_bg)

    # Master Left & Right Grid Margins
    X_LEFT = 0.055
    X_RIGHT = 0.955

    # Dedicated Axes Geometry (leaves exact room for y-labels and right callouts)
    # [left, bottom, width, height]
    ax = fig.add_axes([0.235, 0.095, 0.715, 0.725])
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

    # Direct bar labels with guaranteed breathing room
    for i in range(len(categories)):
        # Gemini
        w_g = bars_gem[i].get_width()
        y_g = bars_gem[i].get_y() + bars_gem[i].get_height() / 2
        ax.annotate(labels_gemini[i], xy=(w_g, y_g), xytext=(7, 0),
                    textcoords="offset points", ha="left", va="center",
                    fontsize=9.2, fontweight="bold", color=c_gemini)

        # OpenAI
        w_o = bars_oai[i].get_width()
        y_o = bars_oai[i].get_y() + bars_oai[i].get_height() / 2
        ax.annotate(labels_openai[i], xy=(w_o, y_o), xytext=(7, 0),
                    textcoords="offset points", ha="left", va="center",
                    fontsize=9.2, fontweight="bold", color=c_openai)

        # Anthropic
        w_a = bars_ant[i].get_width()
        y_a = bars_ant[i].get_y() + bars_ant[i].get_height() / 2
        ax.annotate(labels_anthropic[i], xy=(w_a, y_a), xytext=(7, 0),
                    textcoords="offset points", ha="left", va="center",
                    fontsize=9.2, fontweight="bold", color=c_anthropic)

    # 3. Reference Line at 100% Target
    ax.axvline(100, color="#475569", linestyle=":", linewidth=1.2, alpha=0.8, zorder=1)
    ax.text(100.5, -0.42, "100% Target", fontsize=8.5, color=c_text_dim, fontweight="bold", ha="left", va="center")

    # 4. Axes & Spine Formatting
    ax.set_yticks(y)
    ax.set_yticklabels(categories, fontsize=10.8, fontweight="bold", color=c_text_bright, ha="right")
    ax.invert_yaxis()  # Puts Failure Modes (Tests & Cost) at the very top!
    ax.set_xlim(0, 138)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.xaxis.set_major_formatter(ticker.PercentFormatter(xmax=100, decimals=0))

    ax.set_xlabel("Normalized Score (0% to 100% — Higher is Better →)",
                  fontsize=10.2, color=c_text_muted, labelpad=10, fontweight="medium")
    ax.tick_params(axis="x", colors=c_text_muted, labelsize=9.2, pad=6)
    ax.tick_params(axis="y", colors=c_text_bright, length=0, pad=8)

    ax.grid(axis="x", color=c_grid, linestyle="--", linewidth=0.8, alpha=0.8)
    ax.set_axisbelow(True)

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["bottom", "left"]:
        ax.spines[spine].set_color(c_spine)
        ax.spines[spine].set_linewidth(1.1)

    # 5. Header Block: Title, Subtitle, and Legend all snap to EXACT X_LEFT!
    fig.text(X_LEFT, 0.945,
             "Why 128K/64K Multi-Turn LLM Harnesses Break on Enterprise Code Modernization",
             fontsize=14.5, fontweight="bold", color="#ffffff", ha="left")
    fig.text(X_LEFT, 0.910,
             "Adversarial Benchmark across 15 Interdependent Legacy Modules (76 Procedures) • Single-Pass 1M vs. Multi-Turn Pagination",
             fontsize=10.2, color=c_text_muted, ha="left")

    leg = fig.legend(
        loc="upper left",
        bbox_to_anchor=(X_LEFT, 0.880),
        ncol=3,
        frameon=False,
        fontsize=9.5,
        handlelength=1.2,
        handletextpad=0.5,
        columnspacing=2.2,
    )
    for text in leg.get_texts():
        text.set_color("#f9fafb")
        text.set_fontweight("medium")

    # 6. Render High-DPI Output
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=300, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"[Success] Clean, footer-free 300-DPI chart written to: {out_png}")


if __name__ == "__main__":
    render_perfect_run2_chart()
