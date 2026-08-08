# CI Readiness — Pre-push Checklist

Run these checks locally before every push or PR.

## Docs-only shortcut

If your diff only touches `.md` files, skip code checks. Verify with:

```bash
git status --short
```

## Required checks (all code changes)

```bash
make check
```

This runs lint → format-check → typecheck → test in sequence. If any step
fails, fix it before pushing.

Or run steps individually:

1. **Clean tree** — no accidental untracked files, no `.env` or secrets

   ```bash
   git status --short
   ```

2. **Lint**

   ```bash
   make lint
   ```

3. **Format**

   ```bash
   make format-check
   ```

   If it fails: `make format && make format-check`

4. **Type check**

   ```bash
   make typecheck
   ```

5. **Test**

   ```bash
   make test
   ```

## When to run full coverage

Run `make test-cov` instead of `make test` when:

- Core fault classes changed (`chaos/faults.py`, `agents/faults.py`)
- Models or schema extensions changed
- Integration adapter changed
- Cross-cutting refactor

## AgenticLens integration tests

Tests in `tests/test_integrations_agenticlens.py` auto-skip if agenticlens is
not installed. To run the full suite including those:

```bash
uv sync --extra dev --extra agenticlens
uv run pytest
```

## CI parity

The GitHub Actions CI workflow runs two jobs:
- **test-core** — Python 3.10–3.13, no agenticlens (uses `--frozen`)
- **test-agenticlens-integration** — with sibling checkout

If `make check` passes locally, the core CI job should pass too.
