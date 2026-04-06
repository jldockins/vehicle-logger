---
description: Start a new feature — creates a branch, implements, tests, and prepares a PR
user_invocable: true
---

# New Feature Workflow

The user wants to build a new feature: $ARGUMENTS

## Steps

1. **Create a branch** from `main` using the naming convention `feat/<short-description>`
2. **Read the project brief** (`vehicle-logger.md`) and `CLAUDE.md` to understand the architecture and conventions
3. **Plan the implementation** — explain what you'll build, which files you'll create or modify, and why. Get user confirmation before writing code.
4. **Implement the feature** following the code standards in `CLAUDE.md`
5. **Write tests** in `tests/` with mocked hardware interfaces
6. **Run the checks:**
   - `ruff check .` (linting)
   - `ruff format --check .` (formatting)
   - `pytest tests/` (tests)
7. **Fix any issues** found by the checks
8. **Commit** using Conventional Commits format: `feat(scope): description`
9. **Ask if the user wants to push** and open a PR
