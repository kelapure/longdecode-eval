
## Adversarial-Grade Scorecard: Multi-Turn 128K vs. 1M Native Long Decode

| Metric | 128K Harness (OpenAI GPT-6 Astra) | 128K Harness (Anthropic Claude Fable) | Native 1M Long Decode (Gemini 4 Argon) |
| :--- | :--- | :--- | :--- |
| **1. File Completeness** | 48/44 (100%) | 44/44 (100%) | 44/44 (100%) |
| **2. AST Function/Method Recall** | **333/176 (100%)** | **1364/176 (100%)** | **594/176 (100%)** |
| **3. Lazy Placeholder Stubs (`TODO`/`FIXME`)** | **0 stubs** | **0 stubs** | **0 stubs** |
| **4. Sandbox `pytest` Pass Rate** | **135/135 (100%)** | **990/990 (100%)** | **202/220 (92%)** |
| **5. Raw Code Volume (Characters)** | 164,327 chars (~3,423/file) | 292,063 chars (~6,637/file) | 247,096 chars (~5,615/file) |
| **6. Uncached / Cached Input Tokens** | 3 / 46,516 | 465,417 / 562 | 187,309 / 0 |
| **7. Billed Output + Thinking Tokens** | 49,996 (1t) | 144,184 (3t) | 93,475 (1t) |
| **8. Total Cost (With Cache Discounts)** | **$2.51** | **$3.56** | **$1.31** |
