
## Adversarial-Grade Scorecard: Multi-Turn 128K vs. 1M Native Long Decode

| Metric | 128K Harness (OpenAI GPT-6 Astra) | 128K Harness (Anthropic Claude Fable) | Native 1M Long Decode (Gemini 4 Argon) |
| :--- | :--- | :--- | :--- |
| **1. File Completeness** | 4/4 (100%) | 4/4 (100%) | 4/4 (100%) |
| **2. AST Function/Method Recall** | **5/6 (83%)** | **7/6 (100%)** | **7/6 (100%)** |
| **3. Lazy Placeholder Stubs (`TODO`/`FIXME`)** | **1 stubs** | **0 stubs** | **0 stubs** |
| **4. Sandbox `pytest` Pass Rate** | **1/2 (50%)** | **1/2 (50%)** | **2/2 (100%)** |
| **5. Raw Code Volume (Characters)** | 951 chars (~237/file) | 1,056 chars (~264/file) | 1,058 chars (~264/file) |
| **6. Uncached / Cached Input Tokens** | 295,000 / 580,000 | 285,000 / 490,000 | 250,000 / 0 |
| **7. Billed Output + Thinking Tokens** | 310,000 (3t) | 265,000 (2t) | 240,000 (1t) |
| **8. Total Cost (With Cache Discounts)** | **$16.38** | **$4.98** | **$2.90** |
