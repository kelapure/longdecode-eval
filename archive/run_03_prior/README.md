# run_03_prior: Dry Run (Placeholder Data)

This directory contains outputs from a **dry run** of `eval_long_decode_v2.py --dry-run`.

## Evidence This Is a Dry Run

1. **Round token numbers**: The benchmark_results.md shows:
   - OpenAI: 295,000 uncached / 580,000 cached input tokens
   - Anthropic: 285,000 uncached / 490,000 cached input tokens
   - Gemini: 250,000 uncached / 0 cached input tokens

   These are hardcoded values from the dry-run mode in `eval_long_decode_v2.py` (lines 368-370):
   ```python
   telemetry.uncached_input_tokens = 250_000 + 45_000
   telemetry.cached_input_tokens = 580_000
   telemetry.billed_output_tokens = 310_000
   ```

2. **Tiny raw output files**: Each raw_output file is ~1,000 characters (951-1,058 chars), containing only 4 stub files with placeholder code like:
   ```python
   # TODO: migrate remaining legacy LDAP validation rules
   ```

3. **High costs from fake token counts**: The $16.38 cost for OpenAI reflects the fake dry-run token counts, not real API usage.

## Why It's Preserved

This directory is kept for completeness and transparency. It shows the intermediate step before the actual 22-module benchmark run in `new_run/`.

## Do Not Use for Analysis

The metrics in this directory are placeholder values. Use `new_run/` for the actual benchmark results.
