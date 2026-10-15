[Benchmark Starting] Launching pipelines (provider=all, dry_run=False)...
[Concurrent Execution] Launching OpenAI Astra + Anthropic Fable + Gemini Argon in parallel...
  [OpenAI Astra] Launching Turn 1...
  [Anthropic Fable] Launching Turn 1 (Assistant Prefill)...
  [Gemini 4 Argon] Launching single-pass 1M long decode streaming...
  [Gemini 4 Argon] Single-pass complete (17,175 out tokens)
  [OpenAI Astra] Turn 1 done (stop=stop, 17,411 out tokens)
  [Anthropic Fable] Turn 1 done (stop=end_turn, 63,753 out tokens)

## Adversarial-Grade Scorecard: Multi-Turn 128K vs. 1M Native Long Decode

| Metric | 128K Harness (OpenAI GPT-6 Astra) | 128K Harness (Anthropic Claude Fable) | Native 1M Long Decode (Gemini 4 Argon) |
| :--- | :--- | :--- | :--- |
| **1. File Completeness** | 10/6 (100%) | 12/6 (100%) | 6/6 (100%) |
| **2. AST Function/Method Recall** | **115/16 (100%)** | **175/16 (100%)** | **101/16 (100%)** |
| **3. Lazy Placeholder Stubs (`TODO`/`FIXME`)** | **0 stubs** | **0 stubs** | **0 stubs** |
| **4. Sandbox `pytest` Pass Rate** | **133/149 (89%)** | **191/191 (100%)** | **48/48 (100%)** |
| **5. Uncached / Cached Input Tokens** | 3 / 4,455 | 8,208 / 0 | 2,049 / 3,339 |
| **6. Billed Output + Thinking Tokens** | 17,411 (1t) | 63,753 (1t) | 17,175 (1t) |
| **7. Total Cost (With Cache Discounts)** | **$0.87** | **$0.98** | **$0.18** |

[Static Image Saved] High-DPI PNG chart written to: benchmark_executive_chart.png
[Visual Saved] Interactive executive chart written to: benchmark_executive_chart.html
