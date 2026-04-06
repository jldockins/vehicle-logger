---
description: Run all quality checks before committing — linting, formatting, and tests
user_invocable: true
---

# Pre-Commit Checks

Run all quality checks and report results. Fix any issues found.

## Steps

1. **Lint:** `ruff check .`
2. **Format:** `ruff format --check .`
3. **Tests:** `pytest tests/ -v`

If any check fails:
- Fix the issue automatically if it's straightforward (formatting, simple lint fixes)
- Explain the issue and ask the user if it requires a judgment call

Report a summary at the end:
- Lint: pass/fail
- Format: pass/fail
- Tests: X passed, Y failed
