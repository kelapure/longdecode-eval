
## Verified Scorecard (n=1, single run per model)

All metrics recomputed from committed raw outputs via `python3 verify_scorecard.py`.

| Metric | OpenAI GPT-6 Astra (128K Harness) | Anthropic Claude Fable (64K-per-turn Harness) | Gemini 4 Argon (1M Native) |
| :--- | :--- | :--- | :--- |
| **1. Files Emitted (src + test)** | 23 + 23 (48 total) | 22 + 22 (44 total) | 22 + 22 (44 total) |
| **2. Legacy Procedure Recall** | 176/176 (semantic mapping) | 176/176 | 176/176 |
| **3. Non-test Functions** | 198 | 374 | 374 |
| **4. Test Functions (test_*)** | 135 | 990 | 220 |
| **5. Lazy Placeholders** | 0 | 0 | 0 |
| **6. Pytest Pass Rate** | 135/135 (100%) | 990/990 (100%) | 202/220 (92%) |
| **7. Raw Code Volume** | 164,327 chars | 292,063 chars | 247,096 chars |
| **8. Uncached / Cached Input Tokens** | 3 / 46,516 | 465,417 / 562 | 187,309 / 0 |
| **9. Output Tokens (turns)** | 49,996 (1t) | 144,184 (3t) | 93,475 (1t) |
| **10. Cost** | $2.51 | $3.56 | $1.31 |

### Notes

- **n=1**: These are single-run results. Variance is not measured.
- **Anthropic 64K-per-turn**: The harness caps per-turn output at 64K tokens (line 245: `min(max_tokens, 64000)`), not 128K.
- **Astra semantic mapping**: GPT-6 Astra renamed 4 procedure types (`init_module`→`initialize`, etc.). Recall is verified via deterministic mapping.
- **Gemini failures**: 18 pytest failures are float precision mismatches, not structural errors.
