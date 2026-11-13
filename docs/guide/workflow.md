# Recommended workflow

## Establish a normal baseline

Run the application without an active fault session. Record its useful output and the time/cost constraints you expect recovery to preserve.

## Select a failure hypothesis

For example: if retrieval times out, the application should return an explicit fallback within the allowed duration. Select the specific call site and fault rather than injecting unrelated failures everywhere.

```
agentic-chaos chaos list-faults
agentic-chaos chaos run chaos_quickstart.py --inject token_timeout --save chaos_run.json
```

## Inspect recovery

The recorded event establishes that the fault occurred. Separately check whether the caller retried, switched providers, returned useful fallback content, or surfaced a clear error.

## Make the experiment repeatable

Use explicit fault parameters and seeds when available. Retain normal output, fault settings, the resulting report, and the recovery assertion. Add compound scenarios only after individual failure modes are understood.
