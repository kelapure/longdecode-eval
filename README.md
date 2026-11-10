# Measuring the Continuation-Harness Tax

**What happens when a 22-module legacy rewrite needs more output than a single turn allows?**

This benchmark measures the overhead—in tokens, cost, and correctness—when multi-turn continuation harnesses must break a large code generation task into multiple API calls.

## What This Measures

When an LLM's per-turn output limit is smaller than the required output, a "continuation harness" must:
1. Detect that output was truncated
2. Re-feed prior context into the next turn
3. Stitch chunks together
4. Handle any drift between turns

This benchmark quantifies that tax across three models on a 22-module legacy codebase (176 procedures, ~75,000–95,000 output tokens required).

**Important limitations:**
- **n=1**: Each model ran once. Results show a single point, not variance.
- **Synthetic payload**: The 22-module input was generated, not from a real codebase.
- **List prices on run date**: Costs reflect API pricing at time of run.

---

## Scorecard (Single Run, n=1)

All metrics recomputed from committed raw outputs via `python3 verify_scorecard.py`.

| Metric | OpenAI GPT-6 Astra | Anthropic Claude Fable (64K-per-turn) | Gemini 4 Argon (1M native) |
| :--- | :--- | :--- | :--- |
| **Turns Required** | 1 | 3 (hit 64K ceiling twice) | 1 |
| **Files Emitted** | 48 (44 expected + 4 extras) | 44 | 44 |
| **Legacy Procedure Recall** | 176/176 (semantic mapping) | 176/176 | 176/176 |
| **Non-test Functions** | 198 | 374 | 374 |
| **Test Functions** | 135 | 990 | 220 |
| **Pytest Pass Rate** | 135/135 (100%) | 990/990 (100%) | 202/220 (92%) |
| **Lazy Placeholders** | 0 | 0 | 0 |
| **Raw Code Volume** | 164,327 chars | 292,063 chars | 247,096 chars |
| **Uncached Input Tokens** | 3 | 465,417 | 187,309 |
| **Cached Input Tokens** | 46,516 | 562 | 0 |
| **Output Tokens** | 49,996 | 144,184 | 93,475 |
| **Cost** | $2.51 | $3.56 | $1.31 |

### Reading the Metrics

**Turns Required**: How many API calls to complete the task. More turns = more re-feeding of context.

**Legacy Procedure Recall**: Of the 176 input procedures, how many appear in the output (by name matching)?
- OpenAI Astra renamed procedures (e.g., `INIT_MODULE_00` → `initialize`). The 176/176 count uses a deterministic semantic mapping that covers the 4 renamed procedure types.
- Anthropic and Gemini preserved the original names.

**Non-test vs Test Functions**: The "333/176 (100%)" figures in the original scorecard were misleading—they divided total emitted functions (including test functions) by the 176 legacy procedures. This table separates them.

**Pytest Pass Rate**: The 18 Gemini failures are assertion mismatches on float precision (e.g., `assert 158.12 == 158.125`), not structural or import errors.

---

## The Continuation-Harness Tax

The primary finding: **Anthropic's 3-turn run accumulated 465,417 uncached input tokens** re-feeding prior output back into context. That's the continuation tax.

| Model | Turns | Uncached Input Tokens | Re-fed Context Overhead |
| :--- | :---: | ---: | :--- |
| GPT-6 Astra | 1 | 3 | Negligible (finished in one turn) |
| Claude Fable | 3 | 465,417 | ~270K tokens re-fed across turns |
| Gemini 4 Argon | 1 | 187,309 | None (native 1M streaming) |

The 64K-per-turn ceiling meant Anthropic had to make 3 API calls and re-transmit growing context each time. The cost penalty was 2.7× vs. Gemini.

---

## Verify Without API Keys

The raw API responses are committed. You can recompute every metric locally:

```bash
git clone https://github.com/kelapure/longdecode-eval.git
cd longdecode-eval

# Optional: create a venv
python3 -m venv .venv && source .venv/bin/activate
pip install pytest fastapi httpx

# Run verification
python3 verify_scorecard.py --run-dir ./new_run

# Run tests
python3 verify_scorecard.py --test
```

---

## Run History

| Run | Input | Notes |
| :--- | :--- | :--- |
| **Run 1** | 3 modules (16 procedures) | All models finished in 1 turn. No continuation overhead. |
| **Run 2** | 15 modules (76 procedures) | First pagination cliff. Anthropic hit 8K ceiling 8 times (an earlier per-turn cap). |
| **Run 3 (current)** | 22 modules (176 procedures) | Anthropic hit 64K ceiling twice. Gemini streamed 93K tokens in 1 pass. |

The `archive/run_03_prior/` directory contains outputs from a dry-run (placeholder data with round token numbers like 295,000/580,000). It was a test run, not a live API call. It is preserved for completeness but excluded from analysis.

---

## Repository Structure

```
├── README.md                      # This document
├── verify_scorecard.py            # No-API verification script with tests
├── verify_artifacts.py            # Original verification script
├── eval_long_decode_v2.py         # Benchmark harness (requires API keys)
├── massive_legacy_sample/         # 22-module input payload
├── new_run/                       # Definitive run: raw outputs + charts
│   ├── raw_output_*.txt           # Committed API responses
│   └── benchmark_*.{html,png,md}  # Visualizations
└── archive/                       # Historical runs
    ├── run_01_baseline/           # 3-module run
    ├── run_02_massive/            # 15-module run
    └── run_03_prior/              # Dry-run (placeholder data)
```

---

## What This Does Not Show

1. **Variance**: With n=1, we cannot say whether Gemini's 18 failed tests are typical or an outlier.
2. **Real codebases**: The 22-module payload is synthetic.
3. **Different prompts**: A different system prompt might change turn boundaries.
4. **Latency**: Wall-clock time is not reported (network variability dominates).
5. **Quality beyond tests**: The tests measure whether code runs, not whether it's idiomatic or maintainable.

---

## Reproducing a Live Run

Requires API keys:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GEMINI_API_KEY="AIzaSy..."

pip install google-genai openai anthropic pytest fastapi uvicorn matplotlib

python3 eval_long_decode_v2.py \
  --input-dir ./massive_legacy_sample \
  --output-dir ./my_run \
  --provider all
```

---

## Technical Notes

**Anthropic's per-turn cap**: The harness uses `max_tokens=min(max_tokens, 64000)` (line 245 of `eval_long_decode_v2.py`). The column header previously said "128K" but the actual per-turn ceiling was 64K. This README and the verification script now label it correctly.

**Astra's function renaming**: GPT-6 Astra renamed 4 of 8 procedure types:
- `INIT_MODULE_XX` → `initialize`
- `AUDIT_SECURITY_LOG_XX` → `audit`
- `RECONCILE_MODULE_BALANCES_XX` → `reconcile`
- `COMPUTE_FEE_SURCHARGE_XX` → `compute_surcharge`

The verification script includes a deterministic semantic mapping to count these as matches.

**Gemini's float failures**: The 18 failing tests all involve float comparison assertions like `assert 158.12 == 158.125`. These are precision mismatches in test expectations, not code generation errors.
